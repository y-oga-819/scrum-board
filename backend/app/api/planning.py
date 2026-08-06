"""プランニングの専用エンドポイント（B-22・D-15・D-20）。

「どの PBI を今スプリントで回すか」を決める操作を、``sprints/{sid}/pbis/{pbiId}`` の
**取り込み（POST）／外す（DELETE）**として置く。実体は配下タスクの ``sprintId`` の付け外し
で、その規則はデータ層（:mod:`app.data.planning`）に閉じる（D-20。汎用 ``PATCH`` に分解
するとクライアントに規則が漏れる）。この層は認可・実在確認・HTTP への翻訳だけを担う。

規約はこの層に閉じ、ハンドラに書き散らさない（D-20）:

* **認可** — :func:`~app.authz.require_member` に依存するだけで**非メンバーは 403**（B-09）。
  認証・401・DB 未構成 503 もこの依存が担う。
* **実在確認** — 対象スプリント・PBI が無ければ **404**（存在を漏らさない）。
* **``If-Match`` は取らない** — 分割（B-19）と同じく、これは複数タスクを1規則で束ねて動かす
  **サーバー所有のドメイン操作**であり、クライアントが版を持つ単一リソースの更新ではない
  （個々のタスクの楽観排他はデータ層が読み直した ``_etag`` で内部的に満たす）。

応答は **204 No Content**。フロントは操作後にバックログ（``GET /backlog``）を引き直し、
各タスクの ``sprintId`` から「PBI が今スプリントにいるか」を導出する（二重に持たない — D-08）。
DB を触るため各ハンドラは ``def``（同期）で書き、FastAPI がスレッドプールに逃がす。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from ..authz import Membership, get_repository, require_member
from ..data import Repository
from ..data.pbis import get_pbi
from ..data.planning import plan_pbi_into_sprint, unplan_pbi_from_sprint
from ..data.sprints import get_sprint
from ..http import ProblemException, problem_responses

router = APIRouter(
    prefix="/api/products/{product_id}/sprints/{sprint_id}/pbis",
    tags=["planning"],
)


@router.post(
    "/{pbi_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=problem_responses(401, 403, 404, 503),
)
def include(
    sprint_id: str,
    pbi_id: str,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> Response:
    """PBI をスプリントに取り込む。配下の未完了タスクに ``sprintId`` を付ける（0件なら生成）。"""
    _require_sprint(repo, membership.product_id, sprint_id)
    _require_pbi(repo, membership.product_id, pbi_id)
    plan_pbi_into_sprint(
        repo,
        product_id=membership.product_id,
        sprint_id=sprint_id,
        pbi_id=pbi_id,
        actor=membership.oid,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{pbi_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=problem_responses(401, 403, 404, 503),
)
def exclude(
    sprint_id: str,
    pbi_id: str,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> Response:
    """PBI をスプリントから外す。未完了タスクのみ ``sprintId`` を戻す（完了は動かさない — I-5）。"""
    _require_sprint(repo, membership.product_id, sprint_id)
    _require_pbi(repo, membership.product_id, pbi_id)
    unplan_pbi_from_sprint(
        repo,
        product_id=membership.product_id,
        sprint_id=sprint_id,
        pbi_id=pbi_id,
        actor=membership.oid,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- ヘルパ ------------------------------------------------------------------


def _require_sprint(repo: Repository, product_id: str, sprint_id: str) -> None:
    """対象スプリントが実在しなければ 404（論理削除済みも 404）。"""
    if get_sprint(repo, product_id=product_id, sprint_id=sprint_id) is None:
        raise ProblemException(status.HTTP_404_NOT_FOUND, detail="スプリントが見つかりません")


def _require_pbi(repo: Repository, product_id: str, pbi_id: str) -> None:
    """対象 PBI が実在しなければ 404（論理削除済みも 404）。"""
    if get_pbi(repo, product_id=product_id, pbi_id=pbi_id) is None:
        raise ProblemException(status.HTTP_404_NOT_FOUND, detail="PBI が見つかりません")
