"""Console settings: network, storage, logs, proxy trust, and SSO."""

import base64
import datetime
import json
from urllib.parse import parse_qs, urlparse

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import XMLSigner
from signxml.algorithms import CanonicalizationMethod


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _rsa_material():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": "test-key",
        "use": "sig",
        "alg": "RS256",
        "n": _b64url(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
        "e": _b64url(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
    }
    return key, jwk


def _jwt(key, payload: dict) -> str:
    header = {"alg": "RS256", "kid": "test-key", "typ": "JWT"}
    signing = f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}.{_b64url(json.dumps(payload, separators=(',', ':')).encode())}"
    signature = key.sign(signing.encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
    return f"{signing}.{_b64url(signature)}"


def _cert_and_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "idp.example.test")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=2))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def test_settings_cover_network_language_and_storage(client, auth_headers, tmp_path):
    original = client.get("/v1/admin/settings", headers=auth_headers)
    assert original.status_code == 200
    before = original.json()
    assert before["display_language"] == "en"
    assert before["http_enabled"] is True
    assert "oidc_client_secret" not in before
    models = tmp_path / "models"
    packs = tmp_path / "packs"
    logs = tmp_path / "logs"
    saved = client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={
            "public_url": "https://recognize.example.test",
            "behind_proxy": True,
            "trusted_proxies": "10.0.0.0/8, 127.0.0.1",
            "display_language": "es",
            "host": "0.0.0.0",
            "port": 8088,
            "https_port": 8443,
            "models_dir": str(models),
            "model_packs_dir": str(packs),
            "logs_dir": str(logs),
            "log_level": "warning",
            "log_to_file": True,
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["public_url"] == "https://recognize.example.test"
    assert body["display_language"] == "es"
    assert body["behind_proxy"] is True
    assert "10.0.0.0/8" in body["trusted_proxies"]
    assert body["sso_redirect_uri"] == "https://recognize.example.test/v1/auth/sso/oidc/callback"
    assert "port" in body["restart_pending"] or "models_dir" in body["restart_pending"]
    ui = client.get("/v1/auth/ui")
    assert ui.status_code == 200
    assert ui.json()["display_language"] == "es"
    rejected = client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={"public_url": "javascript:alert(1)"},
    )
    assert rejected.status_code == 400
    both = client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={"http_enabled": False, "https_enabled": False},
    )
    assert both.status_code == 400
    client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={
            "public_url": "",
            "behind_proxy": False,
            "trusted_proxies": "127.0.0.1, ::1",
            "display_language": "en",
            "host": before["host"],
            "port": before["port"],
            "models_dir": before["models_dir"],
            "model_packs_dir": before["model_packs_dir"],
            "logs_dir": "",
            "log_level": "info",
            "log_to_file": True,
        },
    )


def test_self_signed_and_server_log(client, auth_headers):
    import logging

    created = client.post(
        "/v1/admin/tls/self-signed",
        headers=auth_headers,
        json={"hostname": "recognize.local"},
    )
    assert created.status_code == 200
    pem = created.json()
    assert "BEGIN CERTIFICATE" in pem["cert_pem"]
    assert "PRIVATE KEY" in pem["key_pem"]
    saved = client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={
            "https_enabled": True,
            "https_port": 8443,
            "tls_cert_pem": pem["cert_pem"],
            "tls_key_pem": pem["key_pem"],
            "log_to_file": True,
            "log_level": "info",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["tls_readable"] is True
    assert "PRIVATE KEY" not in saved.text
    logging.getLogger("openrecognition").info("settings-log-marker")
    listed = client.get("/v1/admin/server-logs?lines=50", headers=auth_headers)
    assert listed.status_code == 200
    assert any("settings-log-marker" in line for line in listed.json()["lines"])
    client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={"https_enabled": False, "log_level": "info"},
    )


def test_forwarded_proto_requires_trusted_proxy(client, admin_key):
    state = client.app.state.app_state
    previous = (state.settings.behind_proxy, state.settings.trusted_proxies)
    state.settings.behind_proxy = True
    state.settings.trusted_proxies = "127.0.0.1"
    try:
        ignored = client.post(
            "/v1/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
            headers={"x-forwarded-proto": "https"},
        )
        assert ignored.status_code == 200
        assert "Secure" not in ignored.headers["set-cookie"]
        state.settings.trusted_proxies = "testclient"
        trusted = client.post(
            "/v1/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
            headers={"x-forwarded-proto": "https"},
        )
        assert trusted.status_code == 200
        assert "Secure" in trusted.headers["set-cookie"]
    finally:
        state.settings.behind_proxy, state.settings.trusted_proxies = previous


def test_boot_overrides_and_listeners(tmp_path):
    from openrecognition.boot_settings import apply_boot_overrides
    from openrecognition.config import Settings
    from openrecognition.server import plan_listeners
    from openrecognition.tls_material import generate_self_signed

    data = tmp_path / "data"
    data.mkdir()
    models = tmp_path / "custom-models"
    (data / "runtime_settings.json").write_text(
        json.dumps({"models_dir": str(models), "port": 9091, "log_level": "debug", "display_language": "fr"})
    )
    settings = Settings(data_dir=data, models_dir=tmp_path / "original", port=8080, log_level="info")
    apply_boot_overrides(settings)
    assert settings.models_dir == models
    assert settings.port == 9091
    assert settings.log_level == "debug"
    assert settings.display_language == "fr"

    material = generate_self_signed("localhost")
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text(material["cert_pem"])
    key.write_text(material["key_pem"])
    settings.https_enabled = True
    settings.https_port = 8443
    settings.http_enabled = True
    settings.tls_cert_file = str(cert)
    settings.tls_key_file = str(key)
    specs = plan_listeners(settings)
    assert [spec.port for spec in specs] == [8443, 9091]
    assert specs[0].ssl_certfile
    settings.tls_cert_file = str(tmp_path / "missing.pem")
    fallback = plan_listeners(settings)
    assert len(fallback) == 1
    assert fallback[0].ssl_certfile is None


def test_saml_metadata_parser():
    from openrecognition.auth.saml import parse_idp_metadata

    xml = """
    <md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
        xmlns:ds="http://www.w3.org/2000/09/xmldsig#" entityID="https://idp.example.test/saml">
      <md:IDPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
        <md:KeyDescriptor use="signing"><ds:KeyInfo><ds:X509Data><ds:X509Certificate>
        MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAw==
        </ds:X509Certificate></ds:X509Data></ds:KeyInfo></md:KeyDescriptor>
        <md:SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            Location="https://idp.example.test/sso"/>
      </md:IDPSSODescriptor>
    </md:EntityDescriptor>
    """.replace("MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAw==", "")
    cert_pem, _key = _cert_and_key()
    b64 = "".join(cert_pem.decode().splitlines()[1:-1])
    xml = xml.replace("</ds:X509Certificate>", b64 + "</ds:X509Certificate>")
    parsed = parse_idp_metadata(xml.encode())
    assert parsed["saml_idp_entity_id"] == "https://idp.example.test/saml"
    assert parsed["saml_idp_sso_url"] == "https://idp.example.test/sso"
    assert "BEGIN CERTIFICATE" in parsed["saml_idp_x509_cert"]


def test_oidc_login_creates_a_session(client, auth_headers, monkeypatch):
    from openrecognition.auth import oidc as oidc_mod

    oidc_mod.clear_caches()
    key, jwk = _rsa_material()
    issuer = "https://idp.example.test/realms/or"
    holder = {"token": ""}

    class FakeResponse:
        def __init__(self, payload, status=200):
            self.status_code = status
            self.content = json.dumps(payload).encode()

        def json(self):
            return json.loads(self.content)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            if url.endswith("/.well-known/openid-configuration"):
                return FakeResponse(
                    {
                        "issuer": issuer,
                        "authorization_endpoint": f"{issuer}/auth",
                        "token_endpoint": f"{issuer}/token",
                        "jwks_uri": f"{issuer}/jwks",
                    }
                )
            if url.endswith("/jwks"):
                return FakeResponse({"keys": [jwk]})
            raise AssertionError(url)

        def post(self, url, **kwargs):
            return FakeResponse({"id_token": holder["token"], "token_type": "Bearer"})

    monkeypatch.setattr(oidc_mod.httpx, "Client", FakeClient)
    saved = client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={
            "sso_enabled": True,
            "sso_protocol": "oidc",
            "sso_auto_provision": True,
            "sso_default_role": "viewer",
            "oidc_issuer": issuer,
            "oidc_client_id": "or-web",
            "oidc_client_secret": "super-secret",
            "oidc_scopes": "openid profile email",
            "sso_username_claim": "preferred_username",
            "oidc_groups_claim": "groups",
            "public_url": "http://testserver",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["oidc_client_secret_set"] is True
    assert "super-secret" not in saved.text
    start = client.get("/v1/auth/sso/start?next=/settings", follow_redirects=False)
    assert start.status_code == 302
    query = parse_qs(urlparse(start.headers["location"]).query)
    sid = query["state"][0]
    row = client.app.state.app_state.db.fetchone(
        "SELECT payload FROM sso_login_states WHERE id = ?",
        (sid,),
    )
    nonce = json.loads(row["payload"])["nonce"]
    holder["token"] = _jwt(
        key,
        {
            "iss": issuer,
            "aud": "or-web",
            "sub": "subject-ada",
            "preferred_username": "ada",
            "nonce": nonce,
            "exp": 4_102_444_800,
            "groups": ["admin"],
        },
    )
    callback = client.get(
        f"/v1/auth/sso/oidc/callback?code=abc&state={sid}",
        follow_redirects=False,
    )
    assert callback.status_code == 200, callback.text
    assert "or_session" in callback.cookies
    me = client.get("/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["name"] == "ada"
    assert me.json()["role"] == "admin"
    client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={"sso_enabled": False, "public_url": "", "clear_oidc_client_secret": True},
    )


def test_saml_login_rejects_a_bad_signature_and_accepts_a_good_one(client, auth_headers):
    cert_pem, key_pem = _cert_and_key()
    saved = client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={
            "sso_enabled": True,
            "sso_protocol": "saml",
            "sso_auto_provision": True,
            "sso_default_role": "viewer",
            "public_url": "http://testserver",
            "saml_idp_entity_id": "https://idp.example.test/saml",
            "saml_idp_sso_url": "https://idp.example.test/sso",
            "saml_idp_x509_cert": cert_pem.decode(),
            "saml_sp_entity_id": "http://testserver/saml",
            "saml_username_attr": "uid",
            "saml_groups_attr": "groups",
        },
    )
    assert saved.status_code == 200, saved.text
    start = client.get("/v1/auth/sso/start?next=/", follow_redirects=False)
    assert start.status_code == 302
    relay = parse_qs(urlparse(start.headers["location"]).query)["RelayState"][0]
    row = client.app.state.app_state.db.fetchone(
        "SELECT payload FROM sso_login_states WHERE id = ?",
        (relay,),
    )
    request_id = json.loads(row["payload"])["request_id"]
    now = datetime.datetime.now(datetime.timezone.utc)
    before = (now - datetime.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    after = (now + datetime.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assertion = etree.fromstring(
        f"""<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
            ID="_assert1" Version="2.0" IssueInstant="{before}">
          <saml:Issuer>https://idp.example.test/saml</saml:Issuer>
          <saml:Subject>
            <saml:NameID>sam</saml:NameID>
            <saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
              <saml:SubjectConfirmationData NotOnOrAfter="{after}"
                Recipient="http://testserver/v1/auth/sso/saml/acs"
                InResponseTo="{request_id}"/>
            </saml:SubjectConfirmation>
          </saml:Subject>
          <saml:Conditions NotBefore="{before}" NotOnOrAfter="{after}">
            <saml:AudienceRestriction>
              <saml:Audience>http://testserver/saml</saml:Audience>
            </saml:AudienceRestriction>
          </saml:Conditions>
          <saml:AttributeStatement>
            <saml:Attribute Name="uid"><saml:AttributeValue>sam</saml:AttributeValue></saml:Attribute>
            <saml:Attribute Name="groups"><saml:AttributeValue>operator</saml:AttributeValue></saml:Attribute>
          </saml:AttributeStatement>
        </saml:Assertion>""".encode()
    )
    signer = XMLSigner(c14n_algorithm=CanonicalizationMethod.EXCLUSIVE_XML_CANONICALIZATION_1_0)
    signed = signer.sign(assertion, key=key_pem, cert=cert_pem)
    response = etree.Element("{urn:oasis:names:tc:SAML:2.0:protocol}Response")
    response.append(signed)
    payload = base64.b64encode(etree.tostring(response)).decode()
    bad = client.post(
        "/v1/auth/sso/saml/acs",
        data={"SAMLResponse": payload[:-8] + "AAAAAAAA", "RelayState": relay},
        follow_redirects=False,
    )
    assert bad.status_code == 302
    assert "sso_error=" in bad.headers["location"]
    start = client.get("/v1/auth/sso/start?next=/", follow_redirects=False)
    relay = parse_qs(urlparse(start.headers["location"]).query)["RelayState"][0]
    row = client.app.state.app_state.db.fetchone(
        "SELECT payload FROM sso_login_states WHERE id = ?",
        (relay,),
    )
    request_id = json.loads(row["payload"])["request_id"]
    assertion = etree.fromstring(
        f"""<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
            ID="_assert2" Version="2.0" IssueInstant="{before}">
          <saml:Issuer>https://idp.example.test/saml</saml:Issuer>
          <saml:Subject>
            <saml:NameID>sam</saml:NameID>
            <saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
              <saml:SubjectConfirmationData NotOnOrAfter="{after}"
                Recipient="http://testserver/v1/auth/sso/saml/acs"
                InResponseTo="{request_id}"/>
            </saml:SubjectConfirmation>
          </saml:Subject>
          <saml:Conditions NotBefore="{before}" NotOnOrAfter="{after}">
            <saml:AudienceRestriction>
              <saml:Audience>http://testserver/saml</saml:Audience>
            </saml:AudienceRestriction>
          </saml:Conditions>
          <saml:AttributeStatement>
            <saml:Attribute Name="uid"><saml:AttributeValue>sam</saml:AttributeValue></saml:Attribute>
            <saml:Attribute Name="groups"><saml:AttributeValue>operator</saml:AttributeValue></saml:Attribute>
          </saml:AttributeStatement>
        </saml:Assertion>""".encode()
    )
    signed = signer.sign(assertion, key=key_pem, cert=cert_pem)
    response = etree.Element("{urn:oasis:names:tc:SAML:2.0:protocol}Response")
    status = etree.SubElement(response, "{urn:oasis:names:tc:SAML:2.0:protocol}Status")
    code = etree.SubElement(status, "{urn:oasis:names:tc:SAML:2.0:protocol}StatusCode")
    code.set("Value", "urn:oasis:names:tc:SAML:2.0:status:Success")
    response.append(signed)
    payload = base64.b64encode(etree.tostring(response)).decode()
    ok = client.post(
        "/v1/auth/sso/saml/acs",
        data={"SAMLResponse": payload, "RelayState": relay},
        follow_redirects=False,
    )
    assert ok.status_code == 200, ok.text
    me = client.get("/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["name"] == "sam"
    assert me.json()["role"] == "operator"
    client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={"sso_enabled": False, "public_url": "", "sso_protocol": "oidc"},
    )


def test_metadata_endpoint_is_public(client):
    response = client.get("/v1/auth/sso/saml/metadata")
    assert response.status_code == 200
    assert "SPSSODescriptor" in response.text
