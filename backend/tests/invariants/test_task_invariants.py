"""不変条件 I-1〜I-7 のテーブル駆動テスト雛形（B-11・D-19）。

提案書 04章の不変条件を **表で列挙する**のがこの雛形の目的である。設計知識
（「どの文書が正で、どれが不正か」）は今まとめられる一方、それを弾く**検証関数
そのもの**は B-20（「I-1〜I-5 のバリデーションが単一の関数に集約」）で実装する。
そのため本モジュールは次の二層に分かれる。

- **表の自己検査**（`test_case_table_*`）: いま走る。表が I-1〜I-7 を漏れなく
  覆い、各ケースが整合しているかを保証する。雛形自身の退行を防ぐ。
- **振る舞い検査**（`test_single_doc_invariant`）: B-20 の検証関数が生えたら
  自動的に有効化される（それまでは理由付きで skip）。表はそのまま受け皿になる。

I-1〜I-4 は**単一文書**で判定できる（B-20 の関数の入力そのもの）。I-5〜I-7 は
複数文書・操作をまたぐため、判定は各操作エンドポイント側に閉じる（下表 `enforced_by`）。
表には7つすべてを載せ、単一文書で表せないものは `single_doc=False` で明示する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

# B-20 が「I-1〜I-4 を集約する単一のタスク検証関数」を置いた先。既存の
# ``app/data/<エンティティ>.py`` 規約（PBI のドメイン規則が ``app.data.pbis`` に
# あるのと同じ）に合わせ、タスクの検証関数は ``app.data.tasks.check_invariants``
# に実装した。この1行がそこを指すことで下の振る舞い検査が有効化される。
VALIDATOR_MODULE = "app.data.tasks"


@dataclass(frozen=True)
class InvariantCase:
    """不変条件1件に対する1ケース。

    ``valid=False`` のケースは ``invariant`` の違反ちょうど1つを表す（他の不変条件は
    満たしている）。``valid=True`` は対照群で、すべての不変条件を満たす。
    """

    invariant: str  # "I-1" 〜 "I-7"
    name: str  # 何を表すケースかの短い説明
    doc: dict[str, Any]  # task/pbi 文書（提案書 04章のフィールド）
    valid: bool  # True=全不変条件を満たす / False=`invariant` に違反する
    single_doc: bool = True  # 単一文書で判定できるか（False は操作・集約側で担保）
    enforced_by: str = "B-20"  # この不変条件を実装で担保する PBI


def _task(**overrides: Any) -> dict[str, Any]:
    """不変条件をすべて満たす最小の task 文書。ケースは必要な差分だけ上書きする。"""
    base: dict[str, Any] = {
        "type": "task",
        "taskType": "team",
        "pbiId": None,
        "sprintId": None,
        "status": "todo",
        "completedAt": None,
        "isBlocked": False,
    }
    base.update(overrides)
    return base


# --- I-1〜I-4: 単一文書で判定できる（B-20 の検証関数の担当領域） -----------------

SINGLE_DOC_CASES: list[InvariantCase] = [
    # I-1: status != 'done' のとき completedAt は必ず null。
    InvariantCase(
        "I-1",
        "未完了なのに completedAt が入っている",
        _task(status="doing", completedAt="2026-08-03T09:00:00Z"),
        valid=False,
    ),
    InvariantCase(
        "I-1",
        "未完了で completedAt が null（対照）",
        _task(status="doing", completedAt=None),
        valid=True,
    ),
    # I-2: done にした時点で completedAt を記録する（取り消し時は null に戻す）。
    InvariantCase(
        "I-2",
        "done なのに completedAt が空",
        _task(status="done", completedAt=None),
        valid=False,
    ),
    InvariantCase(
        "I-2",
        "done で completedAt が記録済み（対照）",
        _task(status="done", completedAt="2026-08-03T09:00:00Z"),
        valid=True,
    ),
    # I-3: taskType='pbi' のとき pbiId は必須。
    InvariantCase(
        "I-3",
        "pbi タスクなのに pbiId が無い",
        _task(taskType="pbi", pbiId=None),
        valid=False,
    ),
    InvariantCase(
        "I-3",
        "pbi タスクで pbiId を持つ（対照）",
        _task(taskType="pbi", pbiId="pbi_01H..."),
        valid=True,
    ),
    # I-4: taskType='team' のとき pbiId は null。判別はフィールドの有無ではなく taskType。
    InvariantCase(
        "I-4",
        "team タスクなのに pbiId が付いている",
        _task(taskType="team", pbiId="pbi_01H..."),
        valid=False,
    ),
    InvariantCase(
        "I-4",
        "team タスクで pbiId が null（対照）",
        _task(taskType="team", pbiId=None),
        valid=True,
    ),
]


# --- I-5〜I-7: 複数文書・操作をまたぐ（各操作エンドポイント側で担保） --------------
#
# 単一文書では表せないため、ここでは「どの操作で・何が守られるべきか」を宣言だけ
# 残す。実データを組んだ振る舞いテストは各 PBI（下記 enforced_by）で本モジュールの
# 表を土台に足す。single_doc=False なので下の振る舞い検査の対象からは外れる。
CROSS_DOC_CASES: list[InvariantCase] = [
    InvariantCase(
        "I-5",
        "スプリント終了で完了タスクの sprintId は動かさない",
        _task(status="done", sprintId="spr_closing", completedAt="2026-08-03T09:00:00Z"),
        valid=True,
        single_doc=False,
        enforced_by="B-25",
    ),
    InvariantCase(
        "I-6",
        "配下 PBI タスクが全部 done でない限り PBI を done にしない（警告に留める）",
        {"type": "pbi", "status": "inProgress"},
        valid=True,
        single_doc=False,
        enforced_by="B-23/B-24",
    ),
    InvariantCase(
        "I-7",
        "PBI 完了時 completedSprintId は最後に完了した配下タスクの sprintId",
        {"type": "pbi", "status": "done", "completedSprintId": None},
        valid=True,
        single_doc=False,
        enforced_by="B-25/B-30",
    ),
]

ALL_CASES: list[InvariantCase] = SINGLE_DOC_CASES + CROSS_DOC_CASES
ALL_INVARIANTS = tuple(f"I-{n}" for n in range(1, 8))


# --- 表の自己検査（いま走る。雛形自身の退行を防ぐ） ----------------------------


def test_case_table_covers_every_invariant() -> None:
    """I-1〜I-7 すべてが表に載っていること（漏れると退行に気づけない）。"""
    covered = {c.invariant for c in ALL_CASES}
    assert covered == set(ALL_INVARIANTS), f"未カバーの不変条件: {set(ALL_INVARIANTS) - covered}"


def test_single_doc_invariants_have_reject_and_control() -> None:
    """単一文書の不変条件は、違反ケースと対照（valid）ケースの両方を持つ。"""
    for inv in ("I-1", "I-2", "I-3", "I-4"):
        cases = [c for c in SINGLE_DOC_CASES if c.invariant == inv]
        assert any(not c.valid for c in cases), f"{inv}: 違反ケースが無い"
        assert any(c.valid for c in cases), f"{inv}: 対照（valid）ケースが無い"


def test_single_doc_cases_are_marked_single_doc() -> None:
    assert all(c.single_doc for c in SINGLE_DOC_CASES)
    assert all(not c.single_doc for c in CROSS_DOC_CASES)


# --- 振る舞い検査（B-20 の検証関数が生えたら有効化される） --------------------


@pytest.mark.parametrize("case", SINGLE_DOC_CASES, ids=lambda c: f"{c.invariant}:{c.name}")
def test_single_doc_invariant(case: InvariantCase) -> None:
    """B-20 の検証関数に各ケースを通し、違反が正しく検出されることを確認する。

    検証関数がまだ無い間（M3 時点）は理由付きで skip する。B-20 が
    ``VALIDATOR_MODULE`` に ``check_invariants(doc) -> list[str]``（違反した
    不変条件ID の列）を実装したら、ここが自動的に有効化される。
    """
    validation = pytest.importorskip(
        VALIDATOR_MODULE,
        reason=f"I-1〜I-5 を集約する検証関数は B-20 で {VALIDATOR_MODULE} に実装する",
    )
    violations = set(validation.check_invariants(case.doc))
    if case.valid:
        assert not violations, f"正しい文書が弾かれた: {violations}"
    else:
        assert case.invariant in violations, (
            f"{case.invariant} 違反を検出できていない（検出: {violations}）"
        )
