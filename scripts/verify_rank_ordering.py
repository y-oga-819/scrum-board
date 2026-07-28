#!/usr/bin/env python3
"""実サービスで ``ORDER BY rank, id`` が序数（コードポイント）順と一致するか検証する（B-16・Q-E）。

**これは B-16 の最初の作業であり、実 Cosmos でしか実行できない**（提案書 06章・D-19）。
Cosmos の文字列比較はドキュメント上の明示が薄く、**大文字小文字を区別しない、あるいは
カルチャ依存の比較**だった場合、並びが静かに壊れる。エミュレータと実サービスで照合順序が
違うと「テストは通るのに本番だけ並びが壊れる」最悪の形になるため、**一度きりの独立ゲート**
として実サービスで確認する（CI には載せない）。

やること:

1. 使い捨てパーティション（``prd__rank_verify``）に、:mod:`app.data.ranking` が実際に
   生成する形のランクを撒く。末尾追加（ヘッダ ``a→b→…``）だけでなく、**先頭挿入で
   大文字ヘッダ（``Z``/``Y``…）になるランク**と、**同一ランク＋別 id**（タイブレーカー
   検証）を必ず含める。ranking.py の警告どおり、保存され得る先頭ヘッダは ``0-9A-Za-z``
   にまたがるため、そこを実サービスで踏む。
2. ``SELECT c.id, c.rank FROM c WHERE c.productId=@pid ORDER BY c.rank, c.id`` を実発行する。
3. サーバーが返した順序を、Python の序数比較による ``sorted(key=(rank, id))`` と突き合わせる。
4. 後始末として撒いたドキュメントを物理削除する（検証用パーティションごと使い捨て）。

一致すれば **PASS**（B-16 の完了条件を満たす）。不一致なら **FAIL**——
提案書 06章のとおり ``rank`` を**浮動小数＋定期リバランス**へ切り替える判断に入り、
その結果を docs に記録する。

    COSMOS_ENDPOINT=... COSMOS_KEY=... COSMOS_DATABASE=... \
        python scripts/verify_rank_ordering.py

短命プロセスなので Cosmos クライアントは一括生成してよい（B-07 の入り口の使い分け）。
"""

from __future__ import annotations

import sys
from pathlib import Path

# ``app`` を import できるよう backend/ を sys.path に載せる（実行時の cwd に依存しない）。
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.data.provisioning import ensure_container  # noqa: E402
from app.data.ranking import (  # noqa: E402
    rank_after,
    rank_before,
    rank_between,
)
from app.data.settings import cosmos_settings_from_env, create_client  # noqa: E402

VERIFY_PRODUCT_ID = "prd__rank_verify"
PROBE_TYPE = "rankProbe"


def build_probe_ranks() -> list[str]:
    """検証用のランク集合を作る（末尾追加・先頭挿入・同一隙間への連続挿入を網羅）。

    先頭挿入は fractional-indexing のヘッダを大文字（``Z``/``Y``…）へ降ろすため、
    Base36 が消しきれない「大文字小文字の比較順」を実サービスで踏む。
    """
    ranks: list[str] = []

    # (1) 末尾へ 12 件（ヘッダは a→b… と伸びる。作成時の採番と同じ経路）。
    last: str | None = None
    for _ in range(12):
        last = rank_after(last)
        ranks.append(last)

    # (2) 先頭へ 6 件（ヘッダが a→Z→Y… と大文字へ降りる）。
    first = ranks[0]
    for _ in range(6):
        first = rank_before(first)
        ranks.append(first)

    # (3) 同じ隙間へ 6 件連続挿入（キーが 1 文字ずつ伸びるだけで壊れないこと）。
    lo = ranks[0]
    hi = rank_after(lo)
    for _ in range(6):
        mid = rank_between(lo, hi)
        ranks.append(mid)
        hi = mid

    return ranks


def build_probe_items() -> list[dict[str, str]]:
    """撒くドキュメント一覧。id はランクと結びつけて追跡しやすくする。

    最後に**同一ランク＋別 id** を 2 件足し、``ORDER BY rank, id`` が id で
    タイブレークすることも実サービスで確かめる（2 人が同じ位置へ同時挿入した状況）。
    """
    ranks = build_probe_ranks()
    items = [
        {
            "id": f"{PROBE_TYPE}_{i:03d}",
            "productId": VERIFY_PRODUCT_ID,
            "type": PROBE_TYPE,
            "rank": rank,
        }
        for i, rank in enumerate(ranks)
    ]
    # タイブレーカー検証: 同一 rank・別 id（id 昇順で並ぶべき）。
    tie_rank = ranks[len(ranks) // 2]
    for suffix in ("aaa", "bbb"):
        items.append(
            {
                "id": f"{PROBE_TYPE}_tie_{suffix}",
                "productId": VERIFY_PRODUCT_ID,
                "type": PROBE_TYPE,
                "rank": tie_rank,
            }
        )
    return items


def expected_order(items: list[dict[str, str]]) -> list[str]:
    """Python の序数比較による正解順（``ORDER BY rank, id``）。"""
    ordered = sorted(items, key=lambda d: (d["rank"], d["id"]))
    return [d["id"] for d in ordered]


def run() -> int:
    settings = cosmos_settings_from_env()
    if not settings.is_configured:
        print(
            "FAIL: COSMOS_ENDPOINT / COSMOS_KEY / COSMOS_DATABASE が未設定です。\n"
            "      この検証は実サービスでのみ意味を持ちます（エミュレータ不可 — D-19）。",
            file=sys.stderr,
        )
        return 2

    client = create_client(settings)
    try:
        database = client.get_database_client(settings.database)
        container = ensure_container(database)

        items = build_probe_items()
        # upsert で冪等に撒く（前回の失敗で残っていても上書きされる）。
        for item in items:
            container.upsert_item(item)

        query = (
            "SELECT c.id, c.rank FROM c "
            "WHERE c.productId=@pid AND c.type=@type "
            "ORDER BY c.rank, c.id"
        )
        rows = list(
            container.query_items(
                query=query,
                parameters=[
                    {"name": "@pid", "value": VERIFY_PRODUCT_ID},
                    {"name": "@type", "value": PROBE_TYPE},
                ],
                partition_key=VERIFY_PRODUCT_ID,
            )
        )
        server_order = [row["id"] for row in rows]
        want = expected_order(items)

        if server_order == want:
            print(
                f"PASS: {len(items)} 件で ORDER BY rank, id が序数順と一致しました。\n"
                "      文字列ランク（fractional indexing / Base36）を採用してよい（B-16）。"
            )
            return 0

        print("FAIL: サーバーの並びが序数順と一致しません（照合順序が序数比較でない疑い）。")
        print("      → 提案書 06章のとおり rank を浮動小数＋定期リバランスへ切り替える判断に入り、")
        print("        その結果を docs/decisions に記録すること。")
        _print_first_divergence(server_order, want, {d["id"]: d["rank"] for d in items})
        return 1
    finally:
        _cleanup(client, settings)
        client.close()


def _print_first_divergence(got: list[str], want: list[str], rank_of: dict[str, str]) -> None:
    """最初にずれた位置を、rank 付きで示す（原因の当たりを付けやすくする）。"""
    for i, (g, w) in enumerate(zip(got, want, strict=False)):
        if g != w:
            print(f"      最初のズレ: 位置 {i}")
            print(f"        サーバー: {g!r} (rank={rank_of.get(g)!r})")
            print(f"        期待:     {w!r} (rank={rank_of.get(w)!r})")
            return


def _cleanup(client: object, settings: object) -> None:
    """撒いた検証ドキュメントを物理削除する（検証用パーティションは使い捨て）。"""
    try:
        database = client.get_database_client(settings.database)  # type: ignore[attr-defined]
        container = ensure_container(database)
        for item in build_probe_items():
            try:
                container.delete_item(item=item["id"], partition_key=VERIFY_PRODUCT_ID)
            except Exception:  # noqa: BLE001 - 後始末は best-effort（無ければ無視）
                pass
    except Exception as exc:  # noqa: BLE001
        print(f"warning: 検証ドキュメントの後始末に失敗しました: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(run())
