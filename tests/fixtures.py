"""Deterministic vendor fixture. Never contacts a real model service."""

import copy
import json
import os
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from iteraconnect.config import DEFAULT
from iteraconnect.gateway import Gateway

LOCAL_KEY = "fixture-local-key-with-at-least-24-characters"
VENDOR_KEY = "fixture-vendor-credential"
MODEL = "fixture-model"
TEXT = "ITERACONNECT_OK"


def chat_object(tool=False):
    message = {"role": "assistant", "content": TEXT}
    if tool:
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_fixture",
                    "type": "function",
                    "function": {"name": "echo_code", "arguments": json.dumps({"code": TEXT})},
                }
            ],
        }
    return {
        "id": "chatcmpl-fixture",
        "object": "chat.completion",
        "created": 1700000000,
        "model": MODEL,
        "choices": [
            {"index": 0, "message": message, "finish_reason": "tool_calls" if tool else "stop"}
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
    }


def response_object(tool=False, status="completed"):
    item = {
        "id": "msg_fixture",
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": TEXT, "annotations": []}],
    }
    if tool:
        item = {
            "id": "fc_fixture",
            "type": "function_call",
            "call_id": "call_fixture",
            "name": "echo_code",
            "arguments": json.dumps({"code": TEXT}),
            "status": "completed",
        }
    return {
        "id": "resp_fixture",
        "object": "response",
        "created_at": 1700000000,
        "status": status,
        "model": MODEL,
        "output": [item],
        "error": None,
        "usage": {
            "input_tokens": 12,
            "output_tokens": 4,
            "total_tokens": 16,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


def message_object(tool=False):
    return {
        "id": "msg_fixture",
        "type": "message",
        "role": "assistant",
        "model": MODEL,
        "content": (
            [
                {
                    "type": "tool_use",
                    "id": "call_fixture",
                    "name": "echo_code",
                    "input": {"code": TEXT},
                }
            ]
            if tool
            else [{"type": "text", "text": TEXT}]
        ),
        "stop_reason": "tool_use" if tool else "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 12, "output_tokens": 4},
    }


def stream_frames(protocol):
    if protocol == "chat":
        common = {
            "id": "chatcmpl-fixture",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": MODEL,
        }
        return [
            {
                **common,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": ""},
                        "finish_reason": None,
                    }
                ],
            },
            {
                **common,
                "choices": [{"index": 0, "delta": {"content": TEXT}, "finish_reason": None}],
            },
            {
                **common,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
            },
            "[DONE]",
        ]
    if protocol == "anthropic":
        initial = message_object()
        initial.update(content=[], stop_reason=None, usage={"input_tokens": 12, "output_tokens": 0})
        return [
            {"type": "message_start", "message": initial},
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": TEXT},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": 4},
            },
            {"type": "message_stop"},
        ]
    result = response_object()
    initial = {**result, "output": [], "status": "in_progress", "usage": None}
    item = result["output"][0]
    part = item["content"][0]
    frames = [
        {"type": "response.created", "response": initial},
        {"type": "response.in_progress", "response": initial},
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {**item, "status": "in_progress", "content": []},
        },
        {
            "type": "response.content_part.added",
            "output_index": 0,
            "item_id": item["id"],
            "content_index": 0,
            "part": {**part, "text": ""},
        },
        {
            "type": "response.output_text.delta",
            "output_index": 0,
            "item_id": item["id"],
            "content_index": 0,
            "delta": TEXT,
        },
        {
            "type": "response.output_text.done",
            "output_index": 0,
            "item_id": item["id"],
            "content_index": 0,
            "text": TEXT,
        },
        {
            "type": "response.content_part.done",
            "output_index": 0,
            "item_id": item["id"],
            "content_index": 0,
            "part": part,
        },
        {"type": "response.output_item.done", "output_index": 0, "item": item},
        {"type": "response.completed", "response": result},
    ]
    return [{**event, "sequence_number": i} for i, event in enumerate(frames)]


class VendorHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, value):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.server.requests.append(("GET", self.path, dict(self.headers), None))
        self.reply(
            200,
            {"object": "list", "data": [{"id": MODEL, "object": "model", "owned_by": "fixture"}]},
        )

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        choice = body.get("tool_choice")
        tool = (
            isinstance(choice, dict)
            and (choice.get("name") or choice.get("function", {}).get("name")) == "echo_code"
        )
        self.server.requests.append(("POST", self.path, dict(self.headers), body))
        if self.server.status != 200:
            self.reply(
                self.server.status, {"error": {"message": VENDOR_KEY + " private upstream detail"}}
            )
            return
        route = self.path.split("?", 1)[0]
        if route.endswith("count_tokens"):
            self.reply(200, {"input_tokens": 12})
            return
        protocol = (
            "chat"
            if route.endswith("chat/completions")
            else "responses"
            if route.endswith("responses")
            else "anthropic"
        )
        if self.server.chat_only and protocol != "chat":
            self.reply(404, {"error": "fixture only speaks Chat"})
            return
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            frames = stream_frames(protocol)
            if protocol == "chat" and tool:
                common = {
                    "id": "chatcmpl-fixture",
                    "object": "chat.completion.chunk",
                    "created": 1700000000,
                    "model": MODEL,
                }
                frames = [
                    {
                        **common,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call_fixture",
                                            "type": "function",
                                            "function": {
                                                "name": "echo_code",
                                                "arguments": json.dumps({"code": TEXT}),
                                            },
                                        }
                                    ],
                                },
                                "finish_reason": None,
                            }
                        ],
                    },
                    {
                        **common,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                        "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
                    },
                    "[DONE]",
                ]
            if self.server.truncated:
                frames = frames[:-1]
            for frame in frames:
                data = frame if isinstance(frame, str) else json.dumps(frame)
                event = (
                    ("event: " + frame["type"] + "\n")
                    if protocol != "chat" and isinstance(frame, dict)
                    else ""
                )
                self.wfile.write((event + "data: " + data + "\n\n").encode())
                self.wfile.flush()
            return
        value = {"chat": chat_object, "responses": response_object, "anthropic": message_object}[
            protocol
        ](tool)
        self.reply(200, value)


@contextmanager
def stack(chat_only=False):
    vendor = ThreadingHTTPServer(("127.0.0.1", 0), VendorHandler)
    vendor.requests, vendor.status, vendor.truncated, vendor.chat_only = [], 200, False, chat_only
    upstream = f"http://127.0.0.1:{vendor.server_port}"
    config = copy.deepcopy(DEFAULT)
    config["providers"]["iteracompute"].update(key_env="FIXTURE_VENDOR_KEY", default_model=MODEL)
    config["providers"]["iteracompute"]["endpoints"] = {"chat": upstream + "/v1"}
    if not chat_only:
        config["providers"]["iteracompute"]["endpoints"].update(
            responses=upstream + "/v1", anthropic=upstream
        )
    gateway = Gateway(config, LOCAL_KEY, ("127.0.0.1", 0))
    config["gateway"]["port"] = gateway.server_port
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (vendor, gateway)]
    for thread in threads:
        thread.start()
    with patch.dict(
        os.environ, {"FIXTURE_VENDOR_KEY": VENDOR_KEY, "ITERACONNECT_GATEWAY_KEY": LOCAL_KEY}
    ):
        try:
            yield config, vendor, gateway
        finally:
            for s in (vendor, gateway):
                s.shutdown()
                s.server_close()
            for t in threads:
                t.join(timeout=2)
