"""デイリーノートのドメイン規則とデータアクセスのテスト（B-27・D-27）。

決定的 ID による「1日1件」の担保・ポイントリード・get-or-create（無ければ作る・冪等・
409 握りつぶし）と、生成がポート契約（共通フィールド付与・論理削除除外・型の防波堤）に
乗っていることを確かめる。
"""

from __future__ import annotations

from app.data.daily_notes import (
    daily_note_id,
    ensure_daily_note,
    get_daily_note,
    new_daily_note_data,
)
from app.data.documents import DocumentType
from app.data.fake import InMemoryRepository
from app.data.sprints import create_sprint

PRODUCT = "prd_sandbox"
ACTOR = "oid-author"
SPRINT = "spr_01ABC"
DATE = "2026-08-05"


# --- 決定的 ID（1日1件の鍵） --------------------------------------------------


def test_daily_note_id_is_deterministic_from_sprint_and_date() -> None:
    assert daily_note_id(SPRINT, DATE) == f"dly_{SPRINT}_{DATE}"


def test_daily_note_id_differs_by_date_and_sprint() -> None:
    assert daily_note_id(SPRINT, "2026-08-05") != daily_note_id(SPRINT, "2026-08-06")
    assert daily_note_id("spr_a", DATE) != daily_note_id("spr_b", DATE)


# --- new_daily_note_data（ドメインフィールド） --------------------------------


def test_new_daily_note_data_starts_empty() -> None:
    data = new_daily_note_data(sprint_id=SPRINT, date=DATE)
    assert data["sprintId"] == SPRINT
    assert data["date"] == DATE
    assert data["agenda"] == []
    assert data["minutes"] == ""


# --- get_daily_note ----------------------------------------------------------


def test_get_daily_note_missing_is_none() -> None:
    repo = InMemoryRepository()
    assert get_daily_note(repo, product_id=PRODUCT, sprint_id=SPRINT, date=DATE) is None


def test_get_daily_note_rejects_non_daily_note_id() -> None:
    # 別型（sprint）が偶然同じ id を占めていても掴まない（型の防波堤）。
    repo = InMemoryRepository()
    repo.create(
        product_id=PRODUCT,
        doc_type=DocumentType.SPRINT,
        data={"number": 1},
        actor=ACTOR,
        doc_id=daily_note_id(SPRINT, DATE),
    )
    assert get_daily_note(repo, product_id=PRODUCT, sprint_id=SPRINT, date=DATE) is None


# --- ensure_daily_note（get-or-create） --------------------------------------


def test_ensure_creates_note_when_absent() -> None:
    repo = InMemoryRepository()
    doc = ensure_daily_note(repo, product_id=PRODUCT, sprint_id=SPRINT, date=DATE, actor=ACTOR)
    assert doc["id"] == daily_note_id(SPRINT, DATE)
    assert doc["type"] == "dailyNote"
    assert doc["productId"] == PRODUCT
    assert doc["sprintId"] == SPRINT
    assert doc["date"] == DATE
    assert doc["agenda"] == []
    assert doc["minutes"] == ""
    assert doc["createdBy"] == ACTOR
    assert doc["_etag"]  # ストアが採番する


def test_ensure_returns_existing_and_does_not_overwrite() -> None:
    repo = InMemoryRepository()
    first = ensure_daily_note(repo, product_id=PRODUCT, sprint_id=SPRINT, date=DATE, actor=ACTOR)
    # 議事録を書き込む（PATCH 相当の直接更新）。
    repo.replace(
        product_id=PRODUCT,
        doc_id=first["id"],
        changes={"minutes": "書いた"},
        actor=ACTOR,
        if_match=first["_etag"],
    )
    # 2回目の ensure は既存を返し、空で上書きしない（冪等）。
    again = ensure_daily_note(repo, product_id=PRODUCT, sprint_id=SPRINT, date=DATE, actor=ACTOR)
    assert again["id"] == first["id"]
    assert again["minutes"] == "書いた"


def test_ensure_is_one_document_per_day() -> None:
    # 同じ (sprint, date) で何度呼んでもパーティションに増えるのは1件だけ（1日1件）。
    repo = InMemoryRepository()
    for _ in range(3):
        ensure_daily_note(repo, product_id=PRODUCT, sprint_id=SPRINT, date=DATE, actor=ACTOR)
    notes = repo.query(product_id=PRODUCT, doc_type=DocumentType.DAILY_NOTE)
    assert len(notes) == 1


def test_ensure_separates_notes_by_date() -> None:
    repo = InMemoryRepository()
    ensure_daily_note(repo, product_id=PRODUCT, sprint_id=SPRINT, date="2026-08-05", actor=ACTOR)
    ensure_daily_note(repo, product_id=PRODUCT, sprint_id=SPRINT, date="2026-08-06", actor=ACTOR)
    notes = repo.query(product_id=PRODUCT, doc_type=DocumentType.DAILY_NOTE)
    assert {n["date"] for n in notes} == {"2026-08-05", "2026-08-06"}


def test_ensure_separates_notes_by_sprint() -> None:
    repo = InMemoryRepository()
    ensure_daily_note(repo, product_id=PRODUCT, sprint_id="spr_a", date=DATE, actor=ACTOR)
    ensure_daily_note(repo, product_id=PRODUCT, sprint_id="spr_b", date=DATE, actor=ACTOR)
    notes = repo.query(product_id=PRODUCT, doc_type=DocumentType.DAILY_NOTE)
    assert {n["sprintId"] for n in notes} == {"spr_a", "spr_b"}


def test_ensure_swallows_conflict_from_concurrent_create() -> None:
    """同時実行で先に作られていても（409）、握りつぶして既存を返す（create-if-absent）。"""

    class _RacyRepo(InMemoryRepository):
        """最初の ``get`` だけ「未作成」に見せ、その裏で他リクエストが作った状態を作る。"""

        def __init__(self) -> None:
            super().__init__()
            self._hid = False

        def get(self, product_id: str, doc_id: str):  # noqa: ANN001, ANN201
            if not self._hid and doc_id == daily_note_id(SPRINT, DATE):
                # 1回目の get（ensure の冒頭）は None を返し、直後に「他リクエストが作った」
                # 状態を仕込む。以後の get は通常どおり。
                self._hid = True
                InMemoryRepository.create(
                    self,
                    product_id=product_id,
                    doc_type=DocumentType.DAILY_NOTE,
                    data=new_daily_note_data(sprint_id=SPRINT, date=DATE),
                    actor="oid-other",
                    doc_id=doc_id,
                )
                return None
            return super().get(product_id, doc_id)

    repo = _RacyRepo()
    doc = ensure_daily_note(repo, product_id=PRODUCT, sprint_id=SPRINT, date=DATE, actor=ACTOR)
    # create は 409 になり、握りつぶして他リクエストが作ったものを読み直して返す。
    assert doc["id"] == daily_note_id(SPRINT, DATE)
    assert doc["createdBy"] == "oid-other"


def test_ensure_excludes_soft_deleted_and_recreates() -> None:
    # 論理削除済みは get から見えない（None）。ensure は新しく作り直す。
    repo = InMemoryRepository()
    first = ensure_daily_note(repo, product_id=PRODUCT, sprint_id=SPRINT, date=DATE, actor=ACTOR)
    repo.soft_delete(product_id=PRODUCT, doc_id=first["id"], actor=ACTOR, if_match=first["_etag"])
    assert get_daily_note(repo, product_id=PRODUCT, sprint_id=SPRINT, date=DATE) is None


def test_note_belongs_to_created_sprint() -> None:
    # 実際のスプリント id で作っても id 規約が一貫している（結合の健全性）。
    repo = InMemoryRepository()
    sprint = create_sprint(repo, product_id=PRODUCT, actor=ACTOR)
    doc = ensure_daily_note(
        repo, product_id=PRODUCT, sprint_id=sprint["id"], date=DATE, actor=ACTOR
    )
    assert doc["id"] == f"dly_{sprint['id']}_{DATE}"
    assert doc["sprintId"] == sprint["id"]
