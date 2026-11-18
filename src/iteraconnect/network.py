"""HTTP transport with no redirect or credential forwarding to a second host."""

from __future__ import annotations

import http.client
import json
import ssl
from urllib.parse import urlsplit

from .config import ConnectError

MAX_JSON = 16 * 1024 * 1024


def request(
    method: str, url: str, headers: dict[str, str], body: bytes | None = None, timeout: float = 180
) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
    p = urlsplit(url)
    if not p.hostname:
        raise ConnectError("Upstream URL requires a host")
    conn: http.client.HTTPConnection
    if p.scheme == "https":
        conn = http.client.HTTPSConnection(
            p.hostname, p.port, timeout=timeout, context=ssl.create_default_context()
        )
    else:
        conn = http.client.HTTPConnection(p.hostname, p.port, timeout=timeout)
    path = p.path or "/"
    if p.query:
        path += "?" + p.query
    try:
        conn.request(method, path, body=body, headers=headers)
        return conn, conn.getresponse()
    except (OSError, http.client.HTTPException, ValueError):
        conn.close()
        raise ConnectError("Upstream connection failed or timed out") from None


def json_request(method: str, url: str, key: str = "", payload=None, timeout=180):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    body = json.dumps(payload).encode() if payload is not None else None
    conn, response = request(method, url, headers, body, timeout)
    try:
        if not 200 <= response.status < 300:
            raise ConnectError(f"Endpoint returned HTTP {response.status}")
        raw = response.read(MAX_JSON + 1)
        if len(raw) > MAX_JSON:
            raise ConnectError("JSON response exceeds 16 MiB")
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise ConnectError("Endpoint returned invalid JSON") from None
    finally:
        conn.close()
