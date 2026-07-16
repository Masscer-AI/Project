"""CIMD (Client ID Metadata Document) resolution."""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
from urllib.parse import urlparse

import requests

from api.mcp_oauth.crypto import hash_secret
from api.mcp_oauth.models import OAuthClient

logger = logging.getLogger(__name__)

CIMD_FETCH_TIMEOUT = 5
CIMD_MAX_BYTES = 64_000


def _is_public_https_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    if not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        ):
            return False
    return True


def _same_origin(client_url: str, redirect_uri: str) -> bool:
    c = urlparse(client_url)
    r = urlparse(redirect_uri)
    return (
        c.scheme == r.scheme
        and c.hostname
        and r.hostname
        and c.hostname.lower() == r.hostname.lower()
        and (c.port or (443 if c.scheme == "https" else 80))
        == (r.port or (443 if r.scheme == "https" else 80))
    )


def fetch_cimd_document(client_id_url: str) -> dict | None:
    if not _is_public_https_url(client_id_url):
        return None
    try:
        resp = requests.get(
            client_id_url,
            timeout=CIMD_FETCH_TIMEOUT,
            headers={"Accept": "application/json"},
            allow_redirects=False,
        )
    except requests.RequestException:
        logger.exception("CIMD fetch failed for %s", client_id_url)
        return None
    if resp.status_code != 200:
        return None
    if len(resp.content) > CIMD_MAX_BYTES:
        return None
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def resolve_cimd_client(client_id: str) -> OAuthClient | None:
    """Fetch and cache a CIMD-based OAuth client."""
    if not client_id.startswith("https://"):
        return None
    existing = OAuthClient.objects.filter(
        client_id=client_id, registration_source=OAuthClient.REGISTRATION_CIMD
    ).first()
    if existing and not existing.disabled:
        return existing

    doc = fetch_cimd_document(client_id)
    if not doc:
        return None
    if doc.get("client_id") != client_id:
        return None
    redirect_uris = doc.get("redirect_uris") or []
    if not isinstance(redirect_uris, list) or not redirect_uris:
        return None
    for uri in redirect_uris:
        if not isinstance(uri, str) or not _same_origin(client_id, uri):
            return None
    client_name = doc.get("client_name") or urlparse(client_id).hostname or "MCP Client"
    auth_method = doc.get("token_endpoint_auth_method") or "none"
    if auth_method not in ("none", "client_secret_basic", "client_secret_post"):
        auth_method = "none"

    if existing:
        existing.client_name = client_name[:255]
        existing.redirect_uris = redirect_uris
        existing.token_endpoint_auth_method = auth_method
        existing.cimd_url = client_id
        existing.disabled = False
        existing.save()
        return existing

    return OAuthClient.objects.create(
        client_id=client_id,
        client_secret_hash="",
        client_name=client_name[:255],
        redirect_uris=redirect_uris,
        token_endpoint_auth_method=auth_method,
        grant_types=["authorization_code", "refresh_token"],
        registration_source=OAuthClient.REGISTRATION_CIMD,
        cimd_url=client_id,
    )
