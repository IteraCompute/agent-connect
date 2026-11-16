import copy
import http.client
import json
import unittest

from iteraconnect.config import ConnectError
from iteraconnect.diagnostics import probe, stream_check

from .fixtures import LOCAL_KEY, MODEL, VENDOR_KEY, stack


def call(port, path, payload=None, key=LOCAL_KEY, extra=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    headers.update(extra or {})
    conn.request(
        "POST" if payload is not None else "GET",
        path,
        json.dumps(payload) if payload is not None else None,
        headers,
    )
    response = conn.getresponse()
    value = response.read()
    conn.close()
    return response.status, value


class GatewayTests(unittest.TestCase):
    def test_all_native_contracts_and_tool_roundtrips(self):
        with stack() as (config, vendor, _):
            report = probe(config, "iteracompute", MODEL)
            self.assertTrue(report["passed"], report)
            self.assertEqual(len(report["results"]), 9)
            for method, _, headers, body in vendor.requests:
                self.assertNotIn(LOCAL_KEY, json.dumps(headers))
                if method == "POST":
                    self.assertEqual(body["model"], MODEL)

    def test_unauthenticated_and_browser_requests_never_reach_upstream(self):
        with stack() as (_, vendor, gateway):
            self.assertEqual(call(gateway.server_port, "/v1/models", key="wrong")[0], 401)
            self.assertEqual(
                call(gateway.server_port, "/v1/models", extra={"Origin": "https://evil.test"})[0],
                403,
            )
            self.assertEqual(vendor.requests, [])

    def test_error_and_redirect_are_sanitized(self):
        with stack() as (_, vendor, gateway):
            for status in (401, 429, 500, 302, 307):
                vendor.status = status
                actual, body = call(
                    gateway.server_port, "/v1/responses", {"model": MODEL, "input": "hi"}
                )
                self.assertEqual(actual, status if status >= 400 else 502)
                self.assertNotIn(VENDOR_KEY.encode(), body)
                self.assertNotIn(b"private upstream", body)
            self.assertEqual(len(vendor.requests), 5)  # no retry and no redirected POST

    def test_missing_model_bad_body_unknown_paths(self):
        with stack() as (_, vendor, gateway):
            for path, payload, status in (
                ("/v1/responses", {}, 400),
                ("/v1/responses", [], 400),
                ("/admin/keys", {"model": MODEL}, 404),
                ("/v1/responses?key=bad", {"model": MODEL}, 400),
                ("/p/missing/v1/responses", {"model": MODEL}, 400),
            ):
                self.assertEqual(call(gateway.server_port, path, payload)[0], status)
            self.assertEqual(vendor.requests, [])

    def test_named_provider_routes_and_native_model_slashes(self):
        with stack() as (config, vendor, gateway):
            config["providers"]["other"] = copy.deepcopy(config["providers"]["iteracompute"])
            for path, model, expected in (
                ("/v1/responses", "other/namespace/model", "namespace/model"),
                ("/p/other/v1/responses", "namespace/model", "namespace/model"),
            ):
                self.assertEqual(
                    call(gateway.server_port, path, {"model": model, "input": "hi"})[0], 200
                )
                self.assertEqual(vendor.requests[-1][3]["model"], expected)

    def test_unsupported_protocol_is_explicit(self):
        with stack(chat_only=True) as (_, vendor, gateway):
            status, _ = call(gateway.server_port, "/v1/messages", {"model": MODEL, "messages": []})
            self.assertEqual(status, 501)
            self.assertEqual(vendor.requests, [])

    def test_native_transport_queries_and_gemini_model_paths(self):
        with stack() as (config, vendor, gateway):
            config["providers"]["iteracompute"]["endpoints"]["gemini"] = (
                f"http://127.0.0.1:{vendor.server_port}/v1beta"
            )
            status, _ = call(
                gateway.server_port,
                "/p/iteracompute/v1/messages?beta=true",
                {"model": MODEL, "messages": []},
            )
            self.assertEqual(status, 200)
            self.assertEqual(vendor.requests[-1][1], "/v1/messages?beta=true")
            status, _ = call(
                gateway.server_port,
                "/v1beta/models/iteracompute%2Fnamespace%2Fmodel:streamGenerateContent?alt=sse",
                {"contents": []},
            )
            self.assertEqual(status, 200)
            self.assertEqual(
                vendor.requests[-1][1],
                "/v1beta/models/namespace/model:streamGenerateContent?alt=sse",
            )
            self.assertEqual(vendor.requests[-1][2]["x-goog-api-key"], VENDOR_KEY)

    def test_catalog_prefixes_and_preserves_per_provider_model_id(self):
        with stack() as (_, _, gateway):
            status, body = call(gateway.server_port, "/v1/models")
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["data"][0]["id"], "iteracompute/" + MODEL)
            _, body = call(gateway.server_port, "/p/iteracompute/v1/models")
            self.assertEqual(json.loads(body)["data"][0]["id"], MODEL)

    def test_sse_truncation_is_not_a_success(self):
        with stack() as (config, vendor, _):
            vendor.truncated = True
            result = probe(config, "iteracompute", MODEL, tools=False)
            streams = [r for r in result["results"] if r["case"] == "stream"]
            self.assertTrue(all(r["status"] == "failed" for r in streams))

    def test_stream_error_is_detected(self):
        for raw in (
            b'data: {"type":"error","error":{"message":"failed"}}\n\n',
            b"data: {broken}\n\n",
        ):
            with self.assertRaises(ConnectError):
                stream_check("responses", raw)

    def test_arbitrary_headers_not_forwarded_and_beta_is_preserved(self):
        with stack() as (_, vendor, gateway):
            status, _ = call(
                gateway.server_port,
                "/v1/messages",
                {"model": MODEL, "messages": []},
                extra={
                    "Cookie": "secret-cookie",
                    "X-Secret": "private",
                    "anthropic-beta": "fixture-beta",
                },
            )
            self.assertEqual(status, 200)
            headers = {k.lower(): v for k, v in vendor.requests[-1][2].items()}
            self.assertNotIn("cookie", headers)
            self.assertNotIn("x-secret", headers)
            self.assertEqual(headers["anthropic-beta"], "fixture-beta")
            self.assertEqual(headers["x-api-key"], VENDOR_KEY)
