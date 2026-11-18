"""Private, user-facing settings; convert credentials to runtime references only."""

from __future__ import annotations

import copy
import json
import os
import re
import tomllib
from pathlib import Path
from typing import NamedTuple

from .config import DEFAULT, ConnectError, private_write, validate, validate_url


class Client(NamedTuple):
    name: str
    protocols: tuple[str, ...]
    next_step: str
    manual_test: bool = False
    guided: bool = False

    def select_protocol(self, available):
        return next((p for p in self.protocols if p in available), self.protocols[0])


CLIENTS = {
    "claude": Client("Claude Code", ("anthropic",), "在新终端启动 claude，开始新会话。"),
    "codex": Client("Codex CLI", ("responses",), "在新终端启动 codex，开始新会话。"),
    "workbuddy": Client(
        "WorkBuddy",
        ("chat",),
        "重启 WorkBuddy，新建任务，在模型菜单选择 custom-local:{provider}/{model}。",
        manual_test=True,
    ),
    "workbuddy-ai": Client(
        "WorkBuddy AI",
        ("chat",),
        "重启 WorkBuddy AI，新建任务，在模型菜单选择 custom-local:{provider}/{model}。",
        manual_test=True,
    ),
    "visual-studio": Client(
        "Visual Studio",
        ("chat",),
        "在 Windows 的 Visual Studio 2026 中打开 Copilot Chat → 管理模型，添加自定义端点。",
        manual_test=True,
        guided=True,
    ),
    "vscode": Client(
        "VS Code",
        ("responses", "chat"),
        "在 VS Code 中启用 Copilot Chat 并重新加载窗口，在本地聊天中选择 Agent Connect 下的 {model}。",
        manual_test=True,
    ),
    "openclaw": Client("OpenClaw", ("chat",), "重启 OpenClaw，在新会话中使用默认模型。"),
    "hermes": Client(
        "Hermes", ("chat",), "重启 Hermes，在新会话中使用 custom:iteraconnect 提供方。"
    ),
}
APP_DEFAULT = {
    "selected_provider": "iteracompute",
    "client": "claude",
    "providers": {
        "iteracompute": {
            "name": "IteraCompute",
            "api_key": "",
            "base_url": "https://api.iteracompute.com",
            "model": "openai/gpt-6-luna",
            "protocols": ["chat", "responses", "anthropic"],
        }
    },
}


def check_settings(data):
    try:
        if set(data) - {"selected_provider", "client", "providers"}:
            raise ValueError
        if data["client"] not in CLIENTS or data["selected_provider"] not in data["providers"]:
            raise ValueError
        for pid, p in data["providers"].items():
            if not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", pid):
                raise ValueError
            if set(p) - {"name", "api_key", "base_url", "model", "protocols", "endpoints"}:
                raise ValueError
            for field in ("name", "model", "base_url"):
                if not isinstance(p[field], str) or not p[field].strip():
                    raise ValueError
            if not isinstance(p["api_key"], str) or any(
                ord(c) < 33 or ord(c) > 126 for c in p["api_key"]
            ):
                raise ValueError
            validate_url(p["base_url"])
            if not isinstance(p["protocols"], list) or not p["protocols"]:
                raise ValueError
            if set(p["protocols"]) - {"chat", "responses", "anthropic", "gemini"}:
                raise ValueError
            for protocol, url in p.get("endpoints", {}).items():
                if protocol not in p["protocols"]:
                    raise ValueError
                validate_url(url)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ConnectError(
            "本地配置格式错误，请参照 config.example.toml；错误内容不会显示密钥。"
        ) from None
    return data


def write_settings(path: Path, data):
    check_settings(data)
    lines = [
        "# 本地私密配置，请勿分享或提交。只需填写 api_key，保存后在界面点「重新读取」。",
        "selected_provider = " + json.dumps(data["selected_provider"]),
        "client = " + json.dumps(data["client"]),
    ]
    for pid, p in data["providers"].items():
        lines += ["", f"[providers.{pid}]"]
        for k in ("name", "api_key", "base_url", "model", "protocols"):
            lines.append(k + " = " + json.dumps(p[k], ensure_ascii=False))
        if p.get("endpoints"):
            lines.append(f"[providers.{pid}.endpoints]")
            lines.extend(k + " = " + json.dumps(v) for k, v in p["endpoints"].items())
    private_write(path, "\n".join(lines) + "\n")


def read_settings(path: Path):
    if not path.exists():
        write_settings(path, copy.deepcopy(APP_DEFAULT))
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        if os.name != "nt":
            path.chmod(0o600)
        return check_settings(data)
    except (tomllib.TOMLDecodeError, UnicodeError):
        raise ConnectError("无法读取本地 TOML 配置，请检查引号；错误内容不会显示密钥。") from None


def runtime_config(data, port=18423):
    """The app exclusively uses this private file, never an unrelated inherited vendor key."""
    config = copy.deepcopy(DEFAULT)
    config["active_provider"] = data["selected_provider"]
    config["gateway"]["port"] = port
    config["providers"] = {}
    for pid, p in data["providers"].items():
        name = "ITERACONNECT_APP_KEY_" + pid.upper().replace("-", "_")
        os.environ[name] = p["api_key"]
        base = p["base_url"].rstrip("/")
        root = base[:-3] if base.endswith("/v1") else base
        endpoints = {}
        for protocol in p["protocols"]:
            endpoints[protocol] = p.get("endpoints", {}).get(protocol) or (
                base
                if protocol in ("chat", "responses") and base.endswith("/v1")
                else root + "/v1"
                if protocol in ("chat", "responses")
                else root + "/v1beta"
                if protocol == "gemini"
                else root
            )
        config["providers"][pid] = {
            "name": p["name"],
            "key_env": name,
            "default_model": p["model"],
            "endpoints": endpoints,
        }
    return validate(config)


def public_settings(data):
    visible = copy.deepcopy(data)
    for p in visible["providers"].values():
        p["has_key"] = bool(p.pop("api_key"))
    return visible
