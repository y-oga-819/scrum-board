#!/usr/bin/env python3
"""FastAPI が生成する OpenAPI スキーマを書き出す（B-12・D-20）。

OpenAPI を**単一の真実**とし、フロントの TypeScript 型はここから生成する
（``make gen-types`` が本スクリプト → ``openapi-typescript`` の順に走らせる）。
手書きにしないのは、Python と TypeScript で 2 つの真実が生まれ、ずれても気づけないため。

``app.openapi()`` はアプリを起動せずにスキーマ dict を返す（lifespan は走らない）ため、
Cosmos などの実接続を一切要さない。CI でも安全に実行できる。

    python scripts/gen_openapi.py [出力先.json]   # 既定は標準出力
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ``app`` を import できるよう backend/ を sys.path に載せる（実行時の cwd に依存しない）。
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.main import app  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    # sort_keys でキー順を決定的にする。並びが揺れると差分検出（CI）が偽陽性になる。
    schema = json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True)
    if args:
        Path(args[0]).write_text(schema + "\n", encoding="utf-8")
    else:
        sys.stdout.write(schema + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
