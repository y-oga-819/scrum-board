"""デイリーノートのドメイン規則とデータアクセス（B-27・D-27）。

``dailyNote`` はデイリースクラムの**その日の**アジェンダと議事録を持つ（提案書 04章・05章）:

    { "type":"dailyNote", "sprintId":"spr_02", "date":"2026-08-05",
      "agenda":[ {"id":"a1","text":"…","done":false} ],
      "minutes":"（markdown）" }

提案書 04章は ``dailyNote`` を「スプリント単位ではなく **1日1ドキュメント**」と定める——
議事録の追記でドキュメントが肥大化し、同時編集の競合が増えるのを避けるため。したがって
**日付が一意鍵**であり、id を **``dly_<sprintId>_<date>``** と (スプリント, 日付) から
決定的に導く（``mbr_<oid>`` / ``usr_<oid>`` と同じ発想 — D-21・D-27）。連番 ULID を振らない
ので、同じ (sprint, date) には**構造的に1件しか作れず**、ポイントリード1件で引ける。

このモジュールが持つのはノート自身のドメイン知識だけに絞る:

* :func:`daily_note_id` — (スプリント, 日付) から決定的な id を導く。
* :func:`new_daily_note_data` — 新規ノートのドメインフィールド（空のアジェンダと議事録）。
* :func:`get_daily_note` — ポイントリード（無ければ ``None``）。
* :func:`ensure_daily_note` — **get-or-create**（無ければ空のノートを作って返す・冪等）。
  同時実行で衝突しても 409 を握りつぶして読み直す（onboarding の ``ensure_bootstrapped`` と
  等価 — D-21・D-27）。パネルが常に編集対象と版（``_etag``）を持てるようにする。

``agenda`` / ``minutes`` の**編集**は単一リソースの汎用 ``PATCH``（``If-Match`` 必須。B-18 の
PBI 詳細と同型）で行うため、このモジュールに書き込み操作は置かない。HTTP への翻訳（404・422・
``ETag``）は API 層（:mod:`app.api.daily_notes`）が担う（データ層は HTTP を知らない）。
"""

from __future__ import annotations

from .documents import Document, DocumentType
from .errors import ConflictError
from .ids import prefix_for
from .repository import Repository


def daily_note_id(sprint_id: str, date: str) -> str:
    """(スプリント, 日付) から決定的なノートの id（``dly_<sprintId>_<date>``）を導く。

    「1日1件」を id の一意性で構造的に担保するための鍵（D-27）。接頭辞は
    :mod:`app.data.ids` の対応表から引き、ID 規約を一元化する。
    """
    return f"{prefix_for(DocumentType.DAILY_NOTE)}_{sprint_id}_{date}"


def new_daily_note_data(*, sprint_id: str, date: str) -> Document:
    """新規ノートの**ドメインフィールド**を組み立てる（共通フィールドは repo が付与）。

    まだ何も書かれていない状態＝空のアジェンダと空の議事録から始める。``agenda`` の各項目
    （``{id, text, done}``）の id はクライアントが採番する（不透明な識別子。B-18 の完了条件
    チェックリストと同じ）ため、ここでは空配列を置く。
    """
    return {
        "sprintId": sprint_id,
        "date": date,
        "agenda": [],
        "minutes": "",
    }


def get_daily_note(
    repo: Repository, *, product_id: str, sprint_id: str, date: str
) -> Document | None:
    """``product_id`` パーティションからその日のノートをポイントリードする。

    未作成・論理削除済みは ``None``（ポート契約どおり存在を漏らさない）。id が dailyNote 以外の
    型を指していた場合も ``None``（``dly_<id>`` 以外を誤って掴まない防波堤 — get_sprint と同型）。
    """
    doc = repo.get(product_id, daily_note_id(sprint_id, date))
    if doc is None or doc.get("type") != DocumentType.DAILY_NOTE.value:
        return None
    return doc


def ensure_daily_note(
    repo: Repository, *, product_id: str, sprint_id: str, date: str, actor: str
) -> Document:
    """その日のノートを取得し、無ければ空のノートを作って返す（**get-or-create**・冪等）。

    パネルは開いてすぐ編集できる（アジェンダのチェック・議事録の入力）のが自然で、そのためには
    最初から「編集対象のノート」と「更新に載せる版（``_etag``）」を持っている必要がある。GET に
    作成の副作用を許すのは、初回サインインの ``GET /api/me`` が user と member を作る
    （:func:`~app.onboarding.ensure_bootstrapped`）のと**同じ既定パターン**（D-21・D-27）。

    id が (sprint, date) から決定的なので、同時に開いた別リクエストが先に作っても二重には
    ならない。その 409（:class:`~app.data.errors.ConflictError`）は握りつぶして読み直す
    （create-if-absent と等価）。
    """
    existing = get_daily_note(repo, product_id=product_id, sprint_id=sprint_id, date=date)
    if existing is not None:
        return existing
    try:
        return repo.create(
            product_id=product_id,
            doc_type=DocumentType.DAILY_NOTE,
            data=new_daily_note_data(sprint_id=sprint_id, date=date),
            actor=actor,
            doc_id=daily_note_id(sprint_id, date),
        )
    except ConflictError:
        # 同時実行で他リクエストが先に作った。id は (sprint, date) から決定的なので同じノートが
        # 1件あるだけ。読み直して返す（create-if-absent と等価。D-27）。
        created = get_daily_note(repo, product_id=product_id, sprint_id=sprint_id, date=date)
        if created is None:  # pragma: no cover — 直前の 409 と矛盾する（論理削除でもない限り）
            raise
        return created
