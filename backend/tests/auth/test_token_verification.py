"""V-1〜V-4 の検証テスト（提案書 08章・B-04 完了条件）。

実テナントに繋がず、テスト鍵ペア＋JWKS スタブで回す（D-19）。
"""

from __future__ import annotations

import pytest

from app.auth.errors import InvalidTokenError
from app.auth.token import verify_token

from .keys import TEST_OID, TEST_SETTINGS, SigningKeypair, static_jwks


def _verify(token: str, keypair: SigningKeypair):
    return verify_token(token, settings=TEST_SETTINGS, jwks=static_jwks(keypair))


# --- 妥当なトークンは通る（基準ケース） --------------------------------------


def test_valid_token_passes_and_exposes_claims() -> None:
    kp = SigningKeypair()

    verified = _verify(kp.mint(), kp)

    assert verified.claims["oid"] == TEST_OID
    assert verified.claims["name"] == "テスト ユーザー"


# --- V-1 署名検証 ------------------------------------------------------------


def test_v1_rejects_token_signed_by_another_key() -> None:
    # 攻撃者の鍵で署名し正規の kid を詐称しても、正規の公開鍵では検証に失敗する。
    legit = SigningKeypair()
    attacker = SigningKeypair()
    forged = attacker.mint(kid=legit.kid)

    with pytest.raises(InvalidTokenError):
        _verify(forged, legit)


def test_v1_rejects_tampered_payload() -> None:
    # 署名後にペイロードを 1 文字書き換えると署名が合わなくなる（改ざん → 401 相当）。
    kp = SigningKeypair()
    header, payload, signature = kp.mint().split(".")
    tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    tampered = ".".join([header, tampered_payload, signature])

    with pytest.raises(InvalidTokenError):
        _verify(tampered, kp)


def test_v1_rejects_unknown_kid() -> None:
    kp = SigningKeypair()

    with pytest.raises(InvalidTokenError):
        _verify(kp.mint(kid="some-other-kid"), kp)


def test_v1_rejects_garbage_token() -> None:
    kp = SigningKeypair()

    with pytest.raises(InvalidTokenError):
        _verify("not-a-jwt", kp)


# --- V-2 aud / V-3 iss / V-4 scp / oid（テーブル駆動） ------------------------


@pytest.mark.parametrize(
    ("mint_kwargs", "rule"),
    [
        ({"audience": "99999999-wrong-aud"}, "V-2 aud 不一致"),
        ({"audience": None}, "V-2 aud 欠落"),
        (
            {"issuer": "https://login.microsoftonline.com/other-tenant/v2.0"},
            "V-3 iss 不一致",
        ),
        ({"issuer": None}, "V-3 iss 欠落"),
        ({"scope": "openid profile"}, "V-4 scp に access_as_user なし"),
        ({"scope": None}, "V-4 scp 欠落"),
        ({"oid": None}, "oid 欠落"),
    ],
)
def test_rejects_invalid_claims(mint_kwargs: dict, rule: str) -> None:
    kp = SigningKeypair()

    with pytest.raises(InvalidTokenError):
        _verify(kp.mint(**mint_kwargs), kp)


def test_v4_accepts_access_scope_among_several() -> None:
    kp = SigningKeypair()

    verified = _verify(kp.mint(scope="openid profile access_as_user"), kp)

    assert "access_as_user" in str(verified.claims["scp"]).split()


# --- 期限（exp） -------------------------------------------------------------


def test_rejects_expired_token() -> None:
    kp = SigningKeypair()

    with pytest.raises(InvalidTokenError):
        _verify(kp.mint(expires_in=-10), kp)  # 10 秒前に失効


def test_rejects_token_without_exp() -> None:
    # exp の無い（無期限）トークンは require で弾く。
    kp = SigningKeypair()

    with pytest.raises(InvalidTokenError):
        _verify(kp.mint(expires_in=None), kp)
