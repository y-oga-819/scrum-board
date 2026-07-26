"""層3: トランザクショナルバッチの原子性（B-11・D-19）— 雛形。

複数文書を1操作で更新する場面（スプリント終了処理 B-25 など）では、部分適用が
起きないこと（全成功か全失敗か）が要る。これは Cosmos の実装依存で、フェイクでは
保証できない典型。ただし **バッチ操作自体が Repository ポートにまだ無い**（B-07 は
単一文書の CRUD まで）ため、ここは受け皿だけ用意し、バッチ導入時に本体を足す。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.cosmos


@pytest.mark.skip(reason="バッチ操作は Repository ポート未実装（B-07 拡張／B-25 で追加）")
def test_batch_is_atomic(repo, product_id) -> None:
    """同一パーティションのバッチが全成功か全失敗になること（部分適用しない）。

    バッチ内の1件が条件（例: If-Match 不一致）で失敗したら、他の変更も
    ロールバックされることを確認する。実装が入り次第この本体を書く。
    """
    raise NotImplementedError
