"""アクセストークンの検証（V-1〜V-4）。

提案書 08章「Python 側の検証項目」をそのまま実装する。純粋な検証関数として
切り出し（FastAPI に依存しない）、テスト鍵ペア＋JWKS スタブで単体検証できるように
する（B-04 の完了条件・B-11 を待たない）。

  V-1  署名 — JWKS の公開鍵で RS256 検証（鍵は :mod:`app.auth.jwks` がキャッシュ）
  V-2  ``aud`` がクライアント ID と一致
  V-3  ``iss`` が ``https://login.microsoftonline.com/<tenantId>/v2.0``
  V-4  ``scp`` に ``access_as_user`` が含まれる

いずれかに反する／改ざんされた／期限切れのトークンは :class:`InvalidTokenError`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import jwt

from .errors import InvalidTokenError
from .jwks import JwksProvider
from .settings import AuthSettings

_ALGORITHMS = ["RS256"]


@dataclass(frozen=True)
class VerifiedToken:
    """検証を通過したトークンのクレーム。identity の組み立ては resolver が行う。"""

    claims: Mapping[str, Any]


def verify_token(
    token: str, *, settings: AuthSettings, jwks: JwksProvider
) -> VerifiedToken:
    """トークンを V-1〜V-4 で検証し、通ればクレームを返す。"""
    # ヘッダから kid を取り出し、対応する公開鍵を得る（V-1 の前段）。
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(f"malformed token header: {exc}") from exc

    kid = header.get("kid")
    if not kid:
        raise InvalidTokenError("token header has no 'kid'")

    try:
        signing_key = jwks.get_signing_key(kid)
    except KeyError as exc:
        # 未知の kid。鍵ローテーション直後などにあり得るが、検証はできない。
        raise InvalidTokenError(f"no signing key for kid={kid!r}") from exc

    # V-1（署名 RS256）・V-2（aud）・V-3（iss）・exp を jwt.decode に委ねる。
    # aud/iss を渡すことで不一致は例外になる。exp は require で存在も強制する。
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=_ALGORITHMS,
            audience=settings.audience,
            issuer=settings.issuer,
            options={"require": ["exp", "aud", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(f"token verification failed: {exc}") from exc

    # V-4（scp に access_as_user が含まれる）。scp は空白区切りの文字列。
    scopes = str(claims.get("scp", "")).split()
    if settings.required_scope not in scopes:
        raise InvalidTokenError(
            f"required scope {settings.required_scope!r} not in 'scp'"
        )

    # oid はユーザー識別子（提案書 08章。メールではなく oid をキーにする）。
    # これが無いと誰なのか解決できないので、検証の一部として必須にする。
    if not claims.get("oid"):
        raise InvalidTokenError("token has no 'oid' claim")

    return VerifiedToken(claims=claims)
