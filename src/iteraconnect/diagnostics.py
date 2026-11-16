"""Protocol contract probes, including complete SSE and a real tool-result round trip."""

from __future__ import annotations

import json
import os
import time

from .config import ConnectError, api_key, gateway_key, gateway_url
from .network import MAX_JSON, request

PROMPT = "Reply with exactly ITERACONNECT_OK."
TOOL = {
    "name": "echo_code",
    "description": "Return the code unchanged.",
    "parameters": {
        "type": "object",
        "properties": {"code": {"type": "string"}},
        "required": ["code"],
        "additionalProperties": False,
    },
}


def endpoint(config, pid, protocol, via):
    p = config["providers"][pid]
    if via == "magpie":
        root = os.environ.get("ITERACONNECT_MAGPIE_URL", "http://127.0.0.1:3425").rstrip("/")
        base, key = root + ("/v1" if protocol != "anthropic" else ""), "magpie-iteraconnect-probe"
    else:
        if protocol not in p["endpoints"]:
            raise ConnectError("Provider does not advertise this native protocol")
        if via == "direct":
            base, key = p["endpoints"][protocol], api_key(p)
        else:
            base = gateway_url(config, pid) + ("/v1" if protocol != "anthropic" else "")
            key = gateway_key()
    suffix = {"chat": "/chat/completions", "responses": "/responses", "anthropic": "/v1/messages"}[
        protocol
    ]
    return base + suffix, key


def send(url, key, protocol, payload, timeout):
    headers = {"Content-Type": "application/json"}
    if protocol == "anthropic":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    else:
        headers["Authorization"] = "Bearer " + key
    conn, response = request("POST", url, headers, json.dumps(payload).encode(), timeout)
    try:
        if not 200 <= response.status < 300:
            raise ConnectError(f"Endpoint returned HTTP {response.status}")
        raw = response.read(MAX_JSON + 1)
        if len(raw) > MAX_JSON:
            raise ConnectError("Probe response exceeds limit")
        if payload.get("stream"):
            return stream_check(protocol, raw)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ConnectError("Invalid JSON response") from None
        if not isinstance(result, dict) or result.get("error"):
            raise ConnectError("API returned an error object")
        return result
    except (OSError, ValueError):
        raise ConnectError("Probe connection ended before a complete response") from None
    finally:
        conn.close()


def stream_check(protocol, raw):
    try:
        frames = raw.decode().replace("\r\n", "\n").split("\n\n")
        types, done, text = [], False, ""
        for frame in frames:
            values = [x[5:].lstrip() for x in frame.splitlines() if x.startswith("data:")]
            if not values:
                continue
            data = "\n".join(values)
            if data == "[DONE]":
                done = True
                continue
            event = json.loads(data)
            kind = event.get("type", "")
            if event.get("error") or kind in ("error", "response.failed", "response.incomplete"):
                raise ConnectError("SSE contains an error or incomplete response")
            types.append(kind)
            if protocol == "chat":
                for choice in event.get("choices", []):
                    text += choice.get("delta", {}).get("content") or ""
            elif protocol == "responses" and kind == "response.output_text.delta":
                text += event.get("delta", "")
            elif protocol == "anthropic" and kind == "content_block_delta":
                text += event.get("delta", {}).get("text", "")
        terminal = (
            done
            if protocol == "chat"
            else (
                "response.completed" in types
                if protocol == "responses"
                else "message_stop" in types
            )
        )
        if not terminal or "ITERACONNECT_OK" not in text:
            raise ConnectError("SSE is missing expected output or its terminal event")
        if protocol == "responses" and (not types or types[0] != "response.created"):
            raise ConnectError("Responses SSE must begin with response.created")
        if protocol == "anthropic" and (not types or types[0] != "message_start"):
            raise ConnectError("Messages SSE must begin with message_start")
        return {"complete": True}
    except (ValueError, UnicodeError, TypeError, AttributeError):
        raise ConnectError("Malformed SSE response") from None


def payload(protocol, model, budget, stream=False):
    p = {"model": model, "stream": stream}
    if protocol == "responses":
        p.update(input=PROMPT, max_output_tokens=budget, store=False)
    else:
        p.update(messages=[{"role": "user", "content": PROMPT}], max_tokens=budget)
    return p


def check_text(protocol, response):
    try:
        if protocol == "chat":
            text = response["choices"][0]["message"]["content"]
        elif protocol == "responses":
            if response.get("status") != "completed":
                raise ConnectError("Responses object is not completed")
            text = "".join(
                c.get("text", "") for i in response["output"] for c in i.get("content", [])
            )
        else:
            text = "".join(c.get("text", "") for c in response["content"])
        if not isinstance(text, str) or "ITERACONNECT_OK" not in text:
            raise ConnectError("Response does not contain expected text")
    except (KeyError, IndexError, TypeError):
        raise ConnectError("Response has an invalid protocol shape") from None


def tool_roundtrip(protocol, url, key, model, budget, timeout):
    p = payload(protocol, model, budget)
    prompt = "Call echo_code with code ITERACONNECT_OK, then repeat its result."
    if protocol == "responses":
        p["input"] = prompt
        p["tools"] = [{"type": "function", **TOOL}]
        p["tool_choice"] = {"type": "function", "name": TOOL["name"]}
    elif protocol == "chat":
        p["messages"] = [{"role": "user", "content": prompt}]
        p["tools"] = [{"type": "function", "function": TOOL}]
        p["tool_choice"] = {"type": "function", "function": {"name": TOOL["name"]}}
    else:
        p["messages"] = [{"role": "user", "content": prompt}]
        p["tools"] = [
            {
                "name": TOOL["name"],
                "description": TOOL["description"],
                "input_schema": TOOL["parameters"],
            }
        ]
        p["tool_choice"] = {"type": "tool", "name": TOOL["name"]}
    first = send(url, key, protocol, p, timeout)
    try:
        if protocol == "chat":
            message = first["choices"][0]["message"]
            calls = message["tool_calls"]
            call = calls[0]
            name, arguments = call["function"]["name"], json.loads(call["function"]["arguments"])
            p["messages"] += [message] + [
                {"role": "tool", "tool_call_id": c["id"], "content": "ITERACONNECT_OK"}
                for c in calls
            ]
        elif protocol == "responses":
            calls = [c for c in first["output"] if c["type"] == "function_call"]
            call = calls[0]
            name, arguments = call["name"], json.loads(call["arguments"])
            p["input"] = [
                {"role": "user", "content": prompt},
                *first["output"],
                *[
                    {
                        "type": "function_call_output",
                        "call_id": c["call_id"],
                        "output": "ITERACONNECT_OK",
                    }
                    for c in calls
                ],
            ]
        else:
            calls = [c for c in first["content"] if c["type"] == "tool_use"]
            call = calls[0]
            name, arguments = call["name"], call["input"]
            # Preserve thinking/signature blocks exactly as returned by the provider.
            p["messages"] += [
                {"role": "assistant", "content": first["content"]},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": c["id"],
                            "content": "ITERACONNECT_OK",
                        }
                        for c in calls
                    ],
                },
            ]
        if name != TOOL["name"] or arguments != {"code": "ITERACONNECT_OK"}:
            raise ConnectError("Tool call name or arguments did not match the probe")
    except (KeyError, IndexError, TypeError, ValueError):
        raise ConnectError("Provider did not return a valid tool call") from None
    p.pop("tool_choice", None)
    check_text(protocol, send(url, key, protocol, p, timeout))


def probe(config, pid, model=None, via="gateway", protocols=None, budget=256, tools=True):
    p = config["providers"][pid]
    selected = model or p["default_model"]
    if via == "magpie":
        selected = "iteraconnect-" + pid + "/" + selected
    protocols = protocols or [k for k in ("chat", "responses", "anthropic") if k in p["endpoints"]]
    results = []
    for protocol in protocols:
        for case in ["text", "stream", "tool-roundtrip"] if tools else ["text", "stream"]:
            start = time.monotonic()
            try:
                url, key = endpoint(config, pid, protocol, via)
                if case == "tool-roundtrip":
                    tool_roundtrip(
                        protocol, url, key, selected, budget, config["gateway"]["timeout"]
                    )
                else:
                    value = send(
                        url,
                        key,
                        protocol,
                        payload(protocol, selected, budget, case == "stream"),
                        config["gateway"]["timeout"],
                    )
                    if case == "text":
                        check_text(protocol, value)
                status, detail = "passed", "contract satisfied"
            except ConnectError as e:
                status, detail = "failed", str(e)
            results.append(
                {
                    "protocol": protocol,
                    "case": case,
                    "status": status,
                    "detail": detail,
                    "seconds": round(time.monotonic() - start, 3),
                }
            )
    return {
        "kind": "api-contract",
        "provider": pid,
        "model": selected,
        "via": via,
        "passed": bool(results) and all(x["status"] == "passed" for x in results),
        "results": results,
    }
