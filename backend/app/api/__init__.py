"""API ルートのパッケージ。

フロントが話す相手はすべて ``/api`` の下にある。ルートは**関心ごと**に分ける:

* :mod:`.meta` — 横断的ルート（``/api/health`` ``/api/me``）
* :mod:`.pbis` — PBI の CRUD（``/api/products/{pid}/pbis``。B-15）
* :mod:`.tasks` — タスクの CRUD（``/api/products/{pid}/tasks``。B-20）
* :mod:`.sprints` — スプリントの CRUD（``/api/products/{pid}/sprints``。B-21）
* :mod:`.planning` — プランニング（``/sprints/{sid}/pbis/{pbiId}`` 取り込み／外す。B-22）
* :mod:`.sprint_close` — スプリント終了処理（``/sprints/{sid}/close`` プレビュー／確定。B-25）
* :mod:`.daily_notes` — デイリーノート（``/sprints/{sid}/daily/{date}`` の読み書き。B-27）
* :mod:`.backlog` — プロダクトバックログ画面の集約 GET（``/backlog``。B-17）
* :mod:`.board` — スプリント画面のボードの集約 GET（``/sprints/{sid}/board``。B-23）

各モジュールは自分の :class:`~fastapi.APIRouter` を公開し、ここで 1 つの
``routers`` に束ねる。:mod:`app.main` はこれを順に ``include_router`` するだけでよい。
リソースが増える（タスク B-20・スプリント B-21…）たびにモジュールを足し、
1 ファイルが肥大化しないようにする。
"""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter

from . import (
    backlog,
    board,
    daily_notes,
    meta,
    pbis,
    planning,
    sprint_close,
    sprints,
    tasks,
)

# main.py が順に include するルータ群。meta（横断）→ リソース別 → ドメイン操作 → 画面集約の
# 順に並べる。
routers: Sequence[APIRouter] = (
    meta.router,
    pbis.router,
    tasks.router,
    sprints.router,
    planning.router,
    sprint_close.router,
    daily_notes.router,
    backlog.router,
    board.router,
)

__all__ = ["routers"]
