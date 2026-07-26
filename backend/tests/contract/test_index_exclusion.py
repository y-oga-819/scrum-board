"""層3: インデックス除外パスが実サービスで実際に効いていること（B-11・D-19）。

除外パスの効果（書き込み RU 削減）は実サービス／エミュレータでしか出ない。
まずは **provisioning が意図した除外パスを実サービス側の実効ポリシーに残せているか**
を裏取りする（フェイクにはインデックスの概念が無く、ここは代替できない）。
書き込み RU の実測（無料枠に収まるか）は B-31 の本番計測に回す。
"""

from __future__ import annotations

import pytest

from app.data.documents import DocumentType
from app.data.provisioning import INDEX_EXCLUDED_PATHS

pytestmark = pytest.mark.cosmos


def test_excluded_paths_are_applied_on_the_service(cosmos_container) -> None:
    """コンテナの実効インデックスポリシーに除外パスが載っていること。"""
    policy = cosmos_container.read()["indexingPolicy"]
    excluded = {entry["path"] for entry in policy.get("excludedPaths", [])}
    for path in INDEX_EXCLUDED_PATHS:
        assert path in excluded, f"除外パス {path} が実効ポリシーに無い（除外: {excluded}）"


def test_long_text_field_write_records_request_charge(repo, product_id, cosmos_container) -> None:
    """除外対象の長文フィールドを持つ文書を書けること＋RU を観測できること。

    しきい値でのアサートはせず（RU は環境で揺れる）、RU を**観測できる**導線が
    あることだけを確認する。B-31 の実測はこの導線に載せる。
    """
    repo.create(
        product_id=product_id,
        doc_type=DocumentType.PBI,
        data={"title": "長文つき", "description": "あ" * 2000},
        actor="tester",
    )
    charge = cosmos_container.client_connection.last_response_headers.get("x-ms-request-charge")
    assert charge is not None
    assert float(charge) > 0
