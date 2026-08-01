"""マイグレーションの適用機構（B-08・D-21）。

Cosmos DB はスキーマレスなので DDL は要らないが、**初期データの投入**（サンドボックス
と本番の ``product``）と、将来の後方互換なデータ変換は、バージョン管理された仕組みに
載せる。設計は D-21:

* **適用済みバージョンを記録**する。``_system`` パーティションに ``mig_<version>``
  （``version`` / ``appliedAt``）を1件書く。
* 起動時（またはデプロイ時）に**未適用のものだけを順に適用**する。
* **冪等性はバージョン記録で担保**する。個々のマイグレーション本体は冪等でなくてよい。
  ``ensure``（無ければ作る）を毎回走らせる方式ではないのは、**再デプロイのたびに実データを
  設定値で上書きする事故**を防ぐため。一度適用したものは二度と走らない。

``member`` と ``user`` は**作らない**（D-21）。本番の権限はスクリプトで明示的に、
``user`` は初回サインインで作られる。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..clock import Clock, SystemClock, isoformat_utc
from ..documents import SYSTEM_PARTITION, DocumentType
from ..repository import Repository

# マイグレーションの実行者（人ではない）。共通フィールドの ``createdBy`` に載る。
MIGRATION_ACTOR = "system:migration"


class ApplyFn(Protocol):
    """1つのマイグレーションが行うデータ変更。``repo`` を通してのみ書く。"""

    def __call__(self, repo: Repository, *, actor: str) -> None: ...


@dataclass(frozen=True)
class Migration:
    """1つのマイグレーション。``version`` は ``"001"`` のようなゼロ詰め文字列。

    ``version`` が適用順を決める（辞書順 = 数値順になるようゼロ詰めする）。
    ``apply`` は本体、記録用の ``mig_<version>`` はランナーが別に書く。
    """

    version: str
    description: str
    apply: ApplyFn


def applied_versions(repo: Repository) -> set[str]:
    """``_system`` に記録済みの ``migration`` から適用済みバージョン集合を得る。

    **``order_by`` を明示的に空にする。** 既定の ``ORDER BY rank, id``（``DEFAULT_ORDER``）
    は、実 Cosmos では **``rank`` を持たないドキュメントを結果から除外する**。``mig_*`` は
    ``rank`` を持たないため、既定順のままだと**常に空**を返し、適用済みが毎回リセットされて
    マイグレーションを再適用→``create_product`` が 409 で落ちる。集合を作るだけで順序は
    不要なので、``order_by=()`` で除外を避ける（フェイクは missing キーを許容するため
    この差はエミュレータ／実サービスでしか出ない — Q-E と同種）。
    """
    records = repo.query(
        product_id=SYSTEM_PARTITION,
        doc_type=DocumentType.MIGRATION,
        order_by=(),
    )
    return {record["version"] for record in records}


def run_migrations(
    repo: Repository,
    *,
    migrations: tuple[Migration, ...] | None = None,
    actor: str = MIGRATION_ACTOR,
    clock: Clock | None = None,
) -> list[str]:
    """未適用のマイグレーションを **version 昇順**に適用し、適用した version を返す。

    各マイグレーションについて、本体を実行してから ``_system`` に ``mig_<version>``
    を記録する（**適用後に記録** — B-08 完了条件）。既に記録済みのものは飛ばすので、
    再起動・再デプロイでは何も起きない（バージョン記録で冪等）。
    """
    if migrations is None:
        # 具体的なマイグレーション一覧はパッケージが束ねる。循環 import を避けるため
        # 呼び出し時に遅延取得する（この時点で __init__ は読み込み済み）。
        from . import MIGRATIONS

        migrations = MIGRATIONS
    resolved_clock: Clock = clock or SystemClock()

    done = applied_versions(repo)
    newly_applied: list[str] = []
    for migration in sorted(migrations, key=lambda m: m.version):
        if migration.version in done:
            continue
        migration.apply(repo, actor=actor)
        repo.create(
            product_id=SYSTEM_PARTITION,
            doc_type=DocumentType.MIGRATION,
            data={
                "version": migration.version,
                "description": migration.description,
                "appliedAt": isoformat_utc(resolved_clock.now()),
            },
            actor=actor,
            doc_id=f"mig_{migration.version}",
        )
        newly_applied.append(migration.version)
    return newly_applied
