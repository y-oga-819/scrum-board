"""API ルートのパッケージ。

フロントが話す相手はすべて ``/api`` の下にある。ルートは**関心ごと**に分ける:

* :mod:`.meta` — 横断的ルート（``/api/health`` ``/api/me``）
* :mod:`.pbis` — PBI の CRUD（``/api/products/{pid}/pbis``。B-15）

各モジュールは自分の :class:`~fastapi.APIRouter` を公開し、ここで 1 つの
``routers`` に束ねる。:mod:`app.main` はこれを順に ``include_router`` するだけでよい。
リソースが増える（タスク B-20・スプリント B-21…）たびにモジュールを足し、
1 ファイルが肥大化しないようにする。
"""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter

from . import meta

# main.py が順に include するルータ群。meta（横断）→ リソース別の順に並べる。
# リソース別モジュール（pbis…）は各 PBI で足す。
routers: Sequence[APIRouter] = (meta.router,)

__all__ = ["routers"]
