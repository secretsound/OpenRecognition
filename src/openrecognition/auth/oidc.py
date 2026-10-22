"""OpenID Connect authorization-code client."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

_discovery_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_jwks_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_CACHE_SECONDS = 600


class OidcError(Exception):
    def __init__(self, code: str = "failed"):
        super().__init__(code)
        self.code = code


def clear_caches() -> None:
    _discovery_cache.clear()
    _jwks_cache.clear()


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def require_http_url(value: str, *, name: str, allow_path: bool = True) -> str:
    text = value.strip()
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{name} must be an http or https URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"{name} cannot include a user, query, or fragment")
    if not allow_path and parsed.path not in {"", "/"}:
        raise ValueError(f"{name} cannot include a path")
    return text.rstrip("/")


def _get_client() -> httpx.Client:
    return httpx.Client(timeout=10.0, follow_redirects=True, max_redirects=3)


def _json_body(response: httpx.Response) -> dict[str, Any]:
    if response.status_code >= 400 or len(response.content) > 1_000_000:
        raise OidcError("failed")
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise OidcError("failed") from exc
    if not isinstance(data, dict):
        raise OidcError("failed")
    return data


def discover(issuer: str) -> dict[str, Any]:
    base = require_http_url(issuer, name="Issuer URL")
    cached = _discovery_cache.get(base)
    now = time.time()
    if cached and now - cached[0] < _CACHE_SECONDS:
        return cached[1]
    try:
        with _get_client() as client:
            data = _json_body(client.get(f"{base}/.well-known/openid-configuration"))
    except httpx.HTTPError as exc:
        raise OidcError("failed") from exc
    if str(data.get("issuer") or "").rstrip("/") != base:
        raise OidcError("failed")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        parsed = urlsplit(str(data.get(key) or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise OidcError("failed")
    _discovery_cache[base] = (now, data)
    return data


def authorization_redirect(
    *,
    issuer: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    nonce: str,
    verifier: str,
) -> str:
    document = discover(issuer)
    challenge = _b64url_encode(hashlib.sha256(verifier.encode("ascii")).digest())
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{document['authorization_endpoint']}?{query}"


def exchange_code(
    *,
    issuer: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    verifier: str,
) -> str:
    document = discover(issuer)
    try:
        with httpx.Client(timeout=10.0, follow_redirects=False) as client:
            response = client.post(
                str(document["token_endpoint"]),
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code_verifier": verifier,
                },
            )
    except httpx.HTTPError as exc:
        raise OidcError("failed") from exc
    token = _json_body(response).get("id_token")
    if not isinstance(token, str) or token.count(".") != 2:
        raise OidcError("invalid")
    return token


def _jwks(uri: str) -> list[dict[str, Any]]:
    cached = _jwks_cache.get(uri)
    now = time.time()
    if cached and now - cached[0] < _CACHE_SECONDS:
        return cached[1]
    try:
        with _get_client() as client:
            data = _json_body(client.get(uri))
    except httpx.HTTPError as exc:
        raise OidcError("failed") from exc
    keys = data.get("keys")
    if not isinstance(keys, list):
        raise OidcError("failed")
    usable = [key for key in keys if isinstance(key, dict)]
    _jwks_cache[uri] = (now, usable)
    return usable


def _b64_int(value: str) -> int:
    return int.from_bytes(_b64url_decode(value), "big")


def _select_key(keys: list[dict[str, Any]], header: dict[str, Any]) -> dict[str, Any]:
    kid = header.get("kid")
    alg = header.get("alg")
    matches = []
    for key in keys:
        if key.get("use") not in (None, "sig"):
            continue
        if kid and key.get("kid") != kid:
            continue
        if alg and key.get("alg") not in (None, alg):
            continue
        matches.append(key)
    if len(matches) != 1:
        raise OidcError("invalid")
    return matches[0]


def _verify_signature(key: dict[str, Any], signing_input: bytes, signature: bytes, alg: str) -> None:
    try:
        if alg == "RS256" and key.get("kty") == "RSA":
            public = rsa.RSAPublicNumbers(_b64_int(str(key["e"])), _b64_int(str(key["n"]))).public_key()
            public.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
            return
        if alg == "ES256" and key.get("kty") == "EC" and len(signature) == 64:
            public = ec.EllipticCurvePublicNumbers(
                _b64_int(str(key["x"])),
                _b64_int(str(key["y"])),
                ec.SECP256R1(),
            ).public_key()
            raw_r = int.from_bytes(signature[:32], "big")
            raw_s = int.from_bytes(signature[32:], "big")
            public.verify(
                encode_dss_signature(raw_r, raw_s),
                signing_input,
                ec.ECDSA(hashes.SHA256()),
            )
            return
    except OidcError:
        raise
    except Exception as exc:
        raise OidcError("invalid") from exc
    raise OidcError("invalid")


def verify_id_token(token: str, *, issuer: str, client_id: str, nonce: str) -> dict[str, Any]:
    if len(token) > 16_000 or token.count(".") != 2:
        raise OidcError("invalid")
    header_b, payload_b, sig_b = token.split(".")
    try:
        header = json.loads(_b64url_decode(header_b))
        payload = json.loads(_b64url_decode(payload_b))
        signature = _b64url_decode(sig_b)
    except (json.JSONDecodeError, ValueError) as exc:
        raise OidcError("invalid") from exc
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise OidcError("invalid")
    alg = header.get("alg")
    if alg not in {"RS256", "ES256"}:
        raise OidcError("invalid")
    document = discover(issuer)
    key = _select_key(_jwks(str(document["jwks_uri"])), header)
    _verify_signature(key, f"{header_b}.{payload_b}".encode("ascii"), signature, str(alg))
    if str(payload.get("iss") or "").rstrip("/") != issuer.rstrip("/"):
        raise OidcError("invalid")
    audience = payload.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if client_id not in audiences:
        raise OidcError("invalid")
    if payload.get("azp") not in (None, client_id):
        raise OidcError("invalid")
    if payload.get("nonce") != nonce:
        raise OidcError("invalid")
    now = time.time()
    try:
        expires = float(payload["exp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise OidcError("invalid") from exc
    if now > expires + 120:
        raise OidcError("invalid")
    not_before = payload.get("nbf")
    if not_before is not None:
        try:
            if now + 120 < float(not_before):
                raise OidcError("invalid")
        except (TypeError, ValueError) as exc:
            raise OidcError("invalid") from exc
    return payload


def string_claim(payload: dict[str, Any], *names: str) -> str:
    for name in names:
        if not name:
            continue
        value = payload.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise OidcError("invalid")


def group_claim(payload: dict[str, Any], name: str) -> list[str]:
    if not name:
        return []
    value = payload.get(name)
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, (str, int)) and str(item).strip()]
    return []
