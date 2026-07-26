"""データ層の例外。

HTTP からは切り離しておく（データ層は FastAPI を知らない）。各例外は D-20 の
ステータスコードに対応する ``http_status`` を持ち、API 層（B-12）が RFC 9457 の
``application/problem+json`` に翻訳する。

  | 例外                     | HTTP | 意味                                   |
  |:-------------------------|:----:|:---------------------------------------|
  | ReservedProductIdError   | 422  | 予約語を productId に使おうとした（``_system``） |
  | NotFoundError            | 404  | 存在しない／論理削除済み（存在を漏らさない） |
  | ConflictError            | 409  | ドメイン競合（id 重複など）             |
  | PreconditionFailedError  | 412  | 楽観排他の失敗（``If-Match`` 不一致）    |
  | PreconditionRequiredError| 428  | ``If-Match`` 欠落（無条件更新を許さない） |
"""

from __future__ import annotations


class DataError(Exception):
    """データ層の例外の基底。"""

    http_status = 500


class ReservedProductIdError(DataError):
    """予約語（``_system``）を productId に払い出そうとした（D-21）。

    マイグレーション（B-08）と将来のプロジェクト作成（B-32）が同じ関門で弾く。
    ユーザー入力に由来する場合は D-20 の 422（バリデーション）に対応する。
    """

    http_status = 422


class NotFoundError(DataError):
    """対象が存在しない、または論理削除済み（D-20：存在の有無を漏らさない）。"""

    http_status = 404


class ConflictError(DataError):
    """id 重複などのドメイン競合。初回サインインの同時実行などで起きる（D-21）。"""

    http_status = 409


class PreconditionFailedError(DataError):
    """``If-Match`` が現在の ``_etag`` と一致しない（楽観排他の失敗）。"""

    http_status = 412


class PreconditionRequiredError(DataError):
    """``If-Match`` が渡されなかった（無条件更新の経路を構造的に塞ぐ。D-20）。"""

    http_status = 428
