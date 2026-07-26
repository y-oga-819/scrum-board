"""``user`` ドメイン（B-10・D-21）。

``user`` は「テナント内で一意の、どのプロダクトにも属さない存在」である。
``member`` が「あるプロダクトでの立場」を表すのに対し、``user`` は表示名・メールの
唯一の置き場になる（各プロダクトに複製しない。更新が全プロダクトに伝播しないため — D-21）。

置き場所は予約パーティション ``_system``、id は **``usr_<oid>``**（決定的）。

``id = usr_<oid>`` にすることの意味（D-21）:

* ``oid`` から **ポイントリード1件**（約1 RU）で引ける。初回サインインの
  「この user は既に居るか」判定がクロスパーティションクエリにならない。
* ``oid`` をキーにする（提案書08章「メールアドレスは変わり得るのでキーにしない」）。

ここが持つのは user の生成・参照と id 規約だけ。初回サインインでの自動作成
（user が無ければ作る・サンドボックスへ member 付与）は :mod:`app.onboarding` が担う。
"""

from __future__ import annotations

from .documents import SYSTEM_PARTITION, Document, DocumentType
from .ids import prefix_for
from .repository import Repository


def user_id(oid: str) -> str:
    """``oid`` から決定的な user の id（``usr_<oid>``）を導く。

    ポイントリード可能にするための鍵（D-21）。接頭辞は :mod:`app.data.ids` の
    対応表から引き、ID 規約を一元化する。
    """
    return f"{prefix_for(DocumentType.USER)}_{oid}"


def get_user(repo: Repository, oid: str) -> Document | None:
    """``_system`` パーティションから ``usr_<oid>`` をポイントリードする。

    未登録（論理削除済みを含む）なら ``None``。初回サインインで「既に居るか」を
    最も安い操作で判定する（D-21）。
    """
    return repo.get(SYSTEM_PARTITION, user_id(oid))


def create_user(
    repo: Repository,
    *,
    oid: str,
    display_name: str | None,
    email: str | None,
    actor: str,
) -> Document:
    """``usr_<oid>`` を1件作成する。

    ``displayName`` / ``email`` はトークンのクレーム由来（:mod:`app.auth`）。id が
    ``oid`` から決定的に決まるため、二重作成は :class:`~app.data.errors.ConflictError`
    （409）。初回サインインの同時実行で起きるこの 409 は :mod:`app.onboarding` が
    握りつぶす（create-if-absent と等価。D-21）。
    """
    return repo.create(
        product_id=SYSTEM_PARTITION,
        doc_type=DocumentType.USER,
        data={"oid": oid, "displayName": display_name, "email": email},
        actor=actor,
        doc_id=user_id(oid),
    )
