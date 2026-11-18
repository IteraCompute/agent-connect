"""Authenticated loopback relay. Protocol conversion is supplied by Magpie."""

from __future__ import annotations

import hmac
import http.client
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, unquote, urlsplit

from . import __version__
from .config import ConnectError, ProviderConfig, RuntimeConfig, api_key, gateway_key
from .network import MAX_JSON, json_request, request

# Explicit inference routes keep provider administration APIs unreachable.
ROUTES = {
    "/v1/chat/completions": ("chat", "/chat/completions"),
    "/v1/responses": ("responses", "/responses"),
    "/v1/messages": ("anthropic", "/v1/messages"),
    "/v1/messages/count_tokens": ("anthropic", "/v1/messages/count_tokens"),
    "/v1/embeddings": ("chat", "/embeddings"),
    "/v1/images/generations": ("chat", "/images/generations"),
    "/v1/rerank": ("chat", "/rerank"),
}


def provider_models(provider: ProviderConfig, timeout=20) -> list[dict]:
    endpoints = provider["endpoints"]
    if base := endpoints.get("chat") or endpoints.get("responses"):
        url = base + "/models"
    elif base := endpoints.get("anthropic"):
        url = base + "/v1/models"
    else:
        # Gemini-only providers need Google's list shape; Magpie can still select a model by id.
        return [{"id": provider["default_model"], "object": "model"}]
    value = json_request("GET", url, api_key(provider, required=False), timeout=timeout)
    if not isinstance(value, dict) or not isinstance(value.get("data"), list):
        raise ConnectError("Provider returned an invalid model catalog")
    rows = value["data"]
    if any(not isinstance(x, dict) or not isinstance(x.get("id"), str) for x in rows):
        raise ConnectError("Provider returned an invalid model catalog")
    return rows


class Gateway(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, config: RuntimeConfig, key: str | None = None, address=None):
        self.config = config
        self.key = key or gateway_key()
        self.slots = threading.BoundedSemaphore(64)
        self.counters = {"requests": 0, "errors": 0}
        self.counter_lock = threading.Lock()
        g = config["gateway"]
        super().__init__(address or (g["host"], g["port"]), Handler)

    def count(self, field):
        with self.counter_lock:
            self.counters[field] += 1


class Handler(BaseHTTPRequestHandler):
    server: Gateway
    protocol_version = "HTTP/1.1"
    server_version = "IteraConnect/" + __version__
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(self.server.config["gateway"]["timeout"])

    def log_message(self, *_):
        # No request paths, prompts, headers, keys or upstream errors in logs.
        pass

    def json(self, status: int, value: dict):
        raw = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(raw)
        except OSError:
            pass

    def fail(self, status, message):
        self.server.count("errors")
        self.json(status, {"type": "error", "error": {"type": "api_error", "message": message}})

    def authenticated(self):
        if self.headers.get("Origin"):
            self.fail(403, "Browser origins are not accepted on the credential relay")
            return False
        bearer = self.headers.get("Authorization", "")
        key = bearer[7:] if bearer.startswith("Bearer ") else ""
        other = self.headers.get("x-api-key", "") or self.headers.get("x-goog-api-key", "")
        if key and other and key != other:
            self.fail(400, "Conflicting gateway credentials")
            return False
        if not hmac.compare_digest((key or other).encode(), self.server.key.encode()):
            self.fail(401, "A valid local gateway key is required")
            return False
        return True

    def split_route(self):
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        if (
            parsed.fragment
            or any(c in path for c in ("\\", "\x00", "\r", "\n", "?", "#", "%"))
            or any(segment in (".", "..") for segment in path.split("/"))
        ):
            raise ConnectError("Invalid inference path")
        self.inference_query = ""
        if parsed.query:
            # Native Anthropic SDKs append beta=true; Gemini's SSE transport uses alt=sse.
            query = parse_qsl(parsed.query, keep_blank_values=True)
            if query == [("beta", "true")] and path.endswith(
                ("/v1/messages", "/v1/messages/count_tokens")
            ):
                self.inference_query = "?beta=true"
            elif query == [("alt", "sse")] and ":streamGenerateContent" in path:
                self.inference_query = "?alt=sse"
            else:
                raise ConnectError(
                    "Only native beta=true and alt=sse transport queries are accepted"
                )
        if path.startswith("/p/"):
            parts = path.split("/", 3)
            if len(parts) != 4 or parts[2] not in self.server.config["providers"]:
                raise ConnectError("Unknown provider route")
            return parts[2], "/" + parts[3]
        return None, path

    def do_GET(self):
        if self.path == "/health":
            self.json(200, {"name": "iteraconnect", "version": __version__})
            return
        if not self.authenticated():
            return
        try:
            pid, path = self.split_route()
            if path != "/v1/models":
                self.fail(404, "Inference route not found")
                return
            rows, errors = [], []
            selected = [pid] if pid else list(self.server.config["providers"])
            for source in selected:
                try:
                    for row in provider_models(self.server.config["providers"][source]):
                        rows.append({**row, "id": row["id"] if pid else source + "/" + row["id"]})
                except ConnectError as e:
                    errors.append({"provider": source, "message": str(e)})
            if not rows and errors:
                self.fail(502, "Model catalog unavailable")
            else:
                self.json(200, {"object": "list", "data": rows, "errors": errors})
        except ConnectError as e:
            self.fail(400, str(e))

    def do_POST(self):
        if not self.authenticated():
            return
        if not self.server.slots.acquire(blocking=False):
            self.fail(429, "Local gateway concurrency limit reached")
            return
        try:
            self.relay()
        except ConnectError as e:
            self.fail(400, str(e))
        except (OSError, http.client.HTTPException):
            # A closed stream remains closed: never replay a possibly executed tool request.
            self.close_connection = True
        finally:
            self.server.slots.release()

    def relay(self):
        pid, path = self.split_route()
        gemini = re.fullmatch(
            r"/v1beta/models/([^:]+):(generateContent|streamGenerateContent)", path
        )
        if path not in ROUTES and not gemini:
            self.fail(404, "Inference route not found")
            return
        if self.headers.get("Transfer-Encoding"):
            raise ConnectError("Use Content-Length for request bodies")
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            raise ConnectError("Invalid Content-Length") from None
        if not 0 < length <= MAX_JSON:
            self.fail(413, "JSON body must be between 1 byte and 16 MiB")
            return
        if self.headers.get_content_type() != "application/json":
            self.fail(415, "Use application/json")
            return
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ConnectError("Incomplete request body")
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ConnectError("Invalid JSON body") from None
        if not isinstance(body, dict):
            raise ConnectError("JSON body must be an object")
        model = gemini[1] if gemini else body.get("model", "")
        if not isinstance(model, str) or not model:
            raise ConnectError("A model id is required")
        providers = self.server.config["providers"]
        prefix, sep, rest = model.partition("/")
        if pid is None and sep and prefix in providers:
            pid, model = prefix, rest
        pid = pid or self.server.config["active_provider"]
        provider = providers[pid]
        protocol, suffix = ("gemini", f"/models/{model}:{gemini[2]}") if gemini else ROUTES[path]
        suffix += self.inference_query
        if protocol not in provider["endpoints"]:
            self.fail(
                501, "Provider has no native endpoint for this protocol; use the Magpie bridge"
            )
            return
        if not gemini:
            body["model"] = model
        key = api_key(provider)
        headers = {"Content-Type": "application/json", "Accept": self.headers.get("Accept", "*/*")}
        # Never forward local Authorization, cookies, Host, or an arbitrary user-supplied header.
        if protocol == "anthropic":
            headers["x-api-key"] = key
            headers["anthropic-version"] = self.headers.get("anthropic-version", "2023-06-01")
            if beta := self.headers.get("anthropic-beta"):
                headers["anthropic-beta"] = beta
        elif protocol == "gemini":
            headers["x-goog-api-key"] = key
        else:
            headers["Authorization"] = "Bearer " + key
        try:
            conn, response = request(
                "POST",
                provider["endpoints"][protocol] + suffix,
                headers,
                json.dumps(body).encode(),
                self.server.config["gateway"]["timeout"],
            )
        except ConnectError:
            self.fail(502, "Upstream connection failed or timed out")
            return
        self.server.count("requests")
        try:
            if not 200 <= response.status < 300:
                # HTTP redirects are deliberately not followed with the vendor credential.
                self.fail(
                    response.status if 400 <= response.status < 600 else 502,
                    f"Provider {pid} returned HTTP {response.status}",
                )
                return
            self.send_response(response.status)
            self.send_header("Content-Type", response.getheader("Content-Type", "application/json"))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            self.close_connection = True
            while chunk := response.read1(65536):
                self.wfile.write(chunk)
                self.wfile.flush()
        finally:
            conn.close()
