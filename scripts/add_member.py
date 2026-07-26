#!/usr/bin/env python3
"""本番プロジェクトへメンバーを登録する（B-10・D-21）。

サンドボックス（``prd_sandbox``）はサインインで全員が自動参加するが、本番
（``prd_scrum_board``）は**権限を緩めない**。誰を入れるかはこのスクリプトで
明示的に決める。

    # 自分の oid を引く
    az ad signed-in-user show --query id -o tsv

    # 本番プロジェクトへ admin として登録（Cosmos の接続情報は環境変数から）
    COSMOS_ENDPOINT=... COSMOS_KEY=... COSMOS_DATABASE=... \
        python scripts/add_member.py --product prd_scrum_board --oid <oid> --role admin

**再実行可能**（D-21）。同じ oid をもう一度渡すと role を更新する（member↔admin の
昇格・降格）。role が同じなら何もしない。メンバーの増加で必ず再実行されるため、
「既にあると失敗する」形にはしない。

``user`` ドキュメントはここでは作らない。それは本人の初回サインインで作られる
（:mod:`app.onboarding`）。membership は user より先に存在してよく、認可は member の
ポイントリードだけを見る（D-21）。

このスクリプトは短命プロセスなので Cosmos クライアントを一括生成してよい
（:func:`app.data.settings.create_repository`。長命なサーバーとは入り口が違う — B-07）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ``app`` を import できるよう backend/ を sys.path に載せる（実行時の cwd に依存しない）。
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.data.members import Role, upsert_member  # noqa: E402
from app.data.products import get_product  # noqa: E402
from app.data.repository import Repository  # noqa: E402


class ProductNotFoundError(Exception):
    """指定した productId のプロダクトが存在しない（typo で無関係な権限を作らせない）。"""


def run(repo: Repository, *, product_id: str, oid: str, role: Role) -> str:
    """メンバーを upsert し、何をしたかの1行サマリを返す（テスト可能な中核）。

    プロダクトの存在を先に確かめる。マイグレーション未適用や productId の typo で
    「存在しないプロダクトのメンバー」を作ってしまう事故を防ぐ。
    """
    if get_product(repo, product_id) is None:
        raise ProductNotFoundError(
            f"プロダクト '{product_id}' が見つかりません。"
            "マイグレーション適用済みか、productId の綴りを確認してください。"
        )
    member = upsert_member(repo, product_id=product_id, oid=oid, role=role)
    return f"registered: product={product_id} oid={oid} role={member['role']}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="本番プロジェクトへメンバーを登録する（再実行可能）。",
    )
    parser.add_argument(
        "--product", required=True, help="登録先の productId（例: prd_scrum_board）"
    )
    parser.add_argument("--oid", required=True, help="対象ユーザーの Entra oid")
    parser.add_argument(
        "--role",
        choices=[r.value for r in Role],
        default=Role.MEMBER.value,
        help="付与する role（既定: member）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # import はここで（arg 解析や --help は Cosmos 設定なしでも動くように）。
    from app.data.settings import cosmos_settings_from_env, create_repository

    settings = cosmos_settings_from_env()
    if not settings.is_configured:
        print(
            "COSMOS_ENDPOINT / COSMOS_KEY / COSMOS_DATABASE を設定してください。",
            file=sys.stderr,
        )
        return 2

    repo = create_repository(settings)
    try:
        summary = run(repo, product_id=args.product, oid=args.oid, role=Role(args.role))
    except ProductNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
