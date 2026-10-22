"""SAML 2.0 service provider: redirect login, signed assertion check, metadata."""

from __future__ import annotations

import base64
import datetime
import logging
import zlib
from typing import Any
from urllib.parse import urlencode
from xml.sax.saxutils import escape

import httpx
from lxml import etree
from signxml import SignatureConfiguration, XMLVerifier
from signxml.exceptions import SignXMLException

SAML = "urn:oasis:names:tc:SAML:2.0:assertion"
SAMLP = "urn:oasis:names:tc:SAML:2.0:protocol"
MD = "urn:oasis:names:tc:SAML:2.0:metadata"
DS = "http://www.w3.org/2000/09/xmldsig#"
logger = logging.getLogger(__name__)
NS = {"saml": SAML, "samlp": SAMLP, "md": MD, "ds": DS}
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


class SamlError(Exception):
    def __init__(self, code: str = "failed"):
        super().__init__(code)
        self.code = code


def _reject(code: str, reason: str) -> None:
    logger.warning("SAML rejected (%s): %s", code, reason)
    raise SamlError(code)


def normalize_cert_pem(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("Identity provider certificate is required")
    if "BEGIN CERTIFICATE" not in text:
        body = "".join(text.split())
        lines = "\n".join(body[index : index + 64] for index in range(0, len(body), 64))
        text = f"-----BEGIN CERTIFICATE-----\n{lines}\n-----END CERTIFICATE-----\n"
    try:
        from cryptography import x509

        x509.load_pem_x509_certificate(text.encode())
    except Exception as exc:
        raise ValueError("Identity provider certificate is not a valid PEM certificate") from exc
    return text if text.endswith("\n") else text + "\n"


def _instant(moment: datetime.datetime | None = None) -> str:
    current = moment or datetime.datetime.now(datetime.timezone.utc)
    return current.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError as exc:
        raise SamlError("invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def authn_redirect(*, sso_url: str, sp_entity_id: str, acs_url: str, request_id: str, relay_state: str) -> str:
    issued = _instant()
    xml = (
        f'<samlp:AuthnRequest xmlns:samlp="{SAMLP}" xmlns:saml="{SAML}"'
        f' ID="{escape(request_id)}" Version="2.0" IssueInstant="{issued}"'
        f' Destination="{escape(sso_url)}"'
        f' AssertionConsumerServiceURL="{escape(acs_url)}"'
        ' ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">'
        f"<saml:Issuer>{escape(sp_entity_id)}</saml:Issuer>"
        "</samlp:AuthnRequest>"
    )
    compressor = zlib.compressobj(wbits=-15)
    deflated = compressor.compress(xml.encode()) + compressor.flush()
    request = base64.b64encode(deflated).decode("ascii")
    join = "&" if "?" in sso_url else "?"
    return sso_url + join + urlencode({"SAMLRequest": request, "RelayState": relay_state})


def metadata_xml(*, entity_id: str, acs_url: str) -> str:
    return (
        f'<md:EntityDescriptor xmlns:md="{MD}" entityID="{escape(entity_id)}">'
        '<md:SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true"'
        f' protocolSupportEnumeration="{SAMLP}">'
        '<md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"'
        f' Location="{escape(acs_url)}" index="1" isDefault="true"/>'
        "</md:SPSSODescriptor></md:EntityDescriptor>"
    )


def parse_idp_metadata(xml: bytes) -> dict[str, str]:
    if len(xml) > 1_000_000:
        raise ValueError("Metadata is too large")
    try:
        root = etree.fromstring(xml, _PARSER)
    except etree.XMLSyntaxError as exc:
        raise ValueError("Metadata is not valid XML") from exc
    entity_id = root.get("entityID") or ""
    sso = root.find(
        ".//md:SingleSignOnService[@Binding='urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect']",
        NS,
    )
    if sso is None:
        sso = root.find(".//md:SingleSignOnService", NS)
    cert = root.find(".//md:KeyDescriptor[@use='signing']//ds:X509Certificate", NS)
    if cert is None:
        cert = root.find(".//ds:X509Certificate", NS)
    if not entity_id or sso is None or not sso.get("Location") or cert is None or not (cert.text or "").strip():
        raise ValueError("Metadata is missing the entity ID, sign-in URL, or signing certificate")
    return {
        "saml_idp_entity_id": entity_id.strip(),
        "saml_idp_sso_url": sso.get("Location", "").strip(),
        "saml_idp_x509_cert": normalize_cert_pem(cert.text or ""),
    }


def fetch_idp_metadata(url: str) -> dict[str, str]:
    from openrecognition.auth.oidc import require_http_url

    target = require_http_url(url, name="Metadata URL")
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True, max_redirects=3) as client:
            response = client.get(target)
    except httpx.HTTPError as exc:
        raise ValueError("Could not download metadata") from exc
    if response.status_code >= 400:
        raise ValueError("Could not download metadata")
    return parse_idp_metadata(response.content)


def _text(element: etree._Element, path: str) -> str:
    found = element.find(path, NS)
    if found is None or not (found.text or "").strip():
        return ""
    return found.text.strip()


def _within(moment: datetime.datetime | None, *, not_after: bool, now: datetime.datetime) -> None:
    if moment is None:
        return
    skew = datetime.timedelta(seconds=120)
    if not_after and now - skew > moment:
        _reject("invalid", f"expired {moment.isoformat()}")
    if not not_after and now + skew < moment:
        _reject("invalid", f"not yet valid {moment.isoformat()}")


def _assertion_from(signed: etree._Element) -> etree._Element:
    if etree.QName(signed).localname == "Assertion":
        return signed
    found = signed.find(".//saml:Assertion", NS)
    if found is None:
        _reject("invalid", "signed node has no assertion")
    return found


def verify_response(
    xml: bytes,
    *,
    cert_pem: str,
    idp_entity_id: str,
    sp_entity_id: str,
    acs_url: str,
    request_id: str,
    username_attr: str,
    groups_attr: str,
) -> dict[str, Any]:
    if len(xml) > 200_000:
        _reject("invalid", "response too large")
    try:
        root = etree.fromstring(xml, _PARSER)
    except etree.XMLSyntaxError as exc:
        _reject("invalid", f"xml: {exc}")
    status = root.find(".//samlp:StatusCode", NS)
    success = "urn:oasis:names:tc:SAML:2.0:status:Success"
    if status is None or status.get("Value") != success:
        _reject("denied", "status")
    cert = normalize_cert_pem(cert_pem)
    signed: etree._Element | None = None
    for location in (
        "./{urn:oasis:names:tc:SAML:2.0:assertion}Assertion/",
        "./",
    ):
        try:
            result = XMLVerifier().verify(
                root,
                x509_cert=cert,
                expect_config=SignatureConfiguration(location=location),
            )
        except SignXMLException as exc:
            logger.debug("SAML signature at %s rejected: %s", location, exc)
            continue
        signed_xml = result.signed_xml if not isinstance(result, list) else result[0].signed_xml
        if isinstance(signed_xml, etree._Element):
            signed = signed_xml
            break
    if signed is None:
        _reject("invalid", "signature")
    assertion = _assertion_from(signed)
    issuer = _text(assertion, "saml:Issuer")
    if idp_entity_id and issuer and issuer != idp_entity_id:
        _reject("invalid", f"issuer {issuer}")
    now = datetime.datetime.now(datetime.timezone.utc)
    conditions = assertion.find("saml:Conditions", NS)
    if conditions is not None:
        _within(_parse_time(conditions.get("NotBefore")), not_after=False, now=now)
        _within(_parse_time(conditions.get("NotOnOrAfter")), not_after=True, now=now)
        audiences = [item.text.strip() for item in conditions.findall(".//saml:Audience", NS) if item.text]
        if audiences and sp_entity_id not in audiences:
            _reject("invalid", f"audience {audiences} != {sp_entity_id}")
    confirmation = assertion.find(".//saml:SubjectConfirmationData", NS)
    if confirmation is not None:
        recipient = confirmation.get("Recipient")
        if recipient and recipient != acs_url:
            _reject("invalid", f"recipient {recipient} != {acs_url}")
        in_response = confirmation.get("InResponseTo")
        if request_id and in_response and in_response != request_id:
            _reject("invalid", "in response to")
        _within(_parse_time(confirmation.get("NotOnOrAfter")), not_after=True, now=now)
    username = ""
    if username_attr:
        for attr in assertion.findall(".//saml:Attribute", NS):
            if attr.get("Name") == username_attr or attr.get("FriendlyName") == username_attr:
                username = _text(attr, "saml:AttributeValue")
                break
    if not username:
        username = _text(assertion, ".//saml:NameID")
    if not username:
        _reject("invalid", "username")
    groups: list[str] = []
    if groups_attr:
        for attr in assertion.findall(".//saml:Attribute", NS):
            if attr.get("Name") == groups_attr or attr.get("FriendlyName") == groups_attr:
                groups = [
                    item.text.strip()
                    for item in attr.findall("saml:AttributeValue", NS)
                    if item.text and item.text.strip()
                ]
    return {"username": username, "groups": groups}
