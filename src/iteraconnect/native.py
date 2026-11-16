"""Original, conservative native configuration editors with conflict-aware rollback."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tomllib
from pathlib import Path

from .config import ConnectError, gateway_key, gateway_url, private_write, state_dir
from .settings import CLIENTS


def client_path(target, home=None):
    home = home or Path.home()
    folders = {
        "claude": ("CLAUDE_CONFIG_DIR", ".claude", "settings.json"),
        "codex": ("CODEX_HOME", ".codex", "config.toml"),
        "workbuddy": ("WORKBUDDY_CONFIG_DIR", ".workbuddy", "models.json"),
        "workbuddy-ai": ("WORKBUDDY_AI_CONFIG_DIR", ".workbuddy-ai", "models.json"),
        "openclaw": ("OPENCLAW_STATE_DIR", ".openclaw", "openclaw.json"),
        "hermes": ("HERMES_HOME", ".hermes", "config.yaml"),
    }
    if target not in folders:
        raise ConnectError("未知客户端")
    env, folder, filename = folders[target]
    if target == "openclaw" and os.environ.get("OPENCLAW_CONFIG_PATH"):
        return Path(os.environ["OPENCLAW_CONFIG_PATH"]).expanduser().absolute()
    return (Path(os.environ[env]).expanduser() if env in os.environ else home / folder) / filename


def merge_dict(original, update):
    for k, v in update.items():
        if isinstance(v, dict):
            if k not in original:
                original[k] = {}
            if not isinstance(original[k], dict):
                raise ConnectError("客户端配置结构不兼容；原文件未修改，请使用手动导出。")
            merge_dict(original[k], v)
        else:
            original[k] = v
    return original


def unique_object(pairs):
    value = {}
    for name, item in pairs:
        if name in value:
            raise ValueError("duplicate JSON field")
        value[name] = item
    return value


def edit_codex(text, root, key, model):
    try:
        before = tomllib.loads(text)
        marker, end = "# BEGIN AGENT CONNECT\n", "# END AGENT CONNECT\n"
        if marker in text:
            start = text.index(marker)
            stop = text.index(end, start) + len(end)
            text = text[:start] + text[stop:]
        elif "iteraconnect" in before.get("model_providers", {}):
            raise ConnectError("Codex 已有同名 iteraconnect 配置，请先重命名或手动处理。")
        # Edit only simple root assignments. Parsing and equality checks below guard complex TOML.
        for name, value in (("model", model), ("model_provider", "iteraconnect")):
            pattern = rf"(?m)^{name}\s*=.*$"
            matches = list(re.finditer(pattern, text))
            if name in before:
                if not matches or ("[" in text[: matches[0].start()]):
                    raise ConnectError("Codex 根配置使用复杂 TOML，请使用手动导出。")
                text = (
                    text[: matches[0].start()]
                    + name
                    + " = "
                    + json.dumps(value)
                    + text[matches[0].end() :]
                )
            else:
                text = name + " = " + json.dumps(value) + "\n" + text
        text = text.rstrip() + "\n\n" + marker + "[model_providers.iteraconnect]\n"
        values = {
            "name": "Agent Connect",
            "base_url": root + "/v1",
            "experimental_bearer_token": key,
            "wire_api": "responses",
            "requires_openai_auth": False,
            "supports_websockets": False,
        }
        text += "".join(k + " = " + json.dumps(v) + "\n" for k, v in values.items()) + end
        after = tomllib.loads(text)
        expected = copy.deepcopy(before)
        expected["model"], expected["model_provider"] = model, "iteraconnect"
        expected.setdefault("model_providers", {})["iteraconnect"] = values
        if after != expected:
            raise ValueError
        return text
    except (ValueError, KeyError, TypeError):
        raise ConnectError("无法安全修改此 Codex TOML；原文件未修改，请使用手动导出。") from None


def yaml_put(text, path, value, remove=False):
    """Edit a plain mapping path, preserving all other YAML verbatim; refuse ambiguous syntax."""
    if text and not text.endswith("\n"):
        text += "\n"
    lines = text.splitlines(keepends=True)
    start, stop, indent = 0, len(lines), 0
    for pos, name in enumerate(path):
        found = []
        for i in range(start, stop):
            line = lines[i]
            if "\t" in line[: len(line) - len(line.lstrip())]:
                raise ConnectError("Hermes YAML 使用制表符，请使用手动导出。")
            if re.match(rf"^ {{{indent}}}{re.escape(name)}\s*:", line):
                found.append(i)
            # Quoted keys, flow mappings and aliases at the edited level require a full YAML editor.
            stripped = line.strip()
            if (
                len(line) - len(line.lstrip()) == indent
                and stripped
                and not stripped.startswith("#")
            ):
                if stripped.startswith(("{", "[", "&", "*", "<<:", "'" + name, '"' + name)):
                    raise ConnectError("Hermes YAML 包含复杂映射，请使用手动导出。")
        if len(found) > 1:
            raise ConnectError("Hermes YAML 含重复配置项；原文件未修改。")
        if not found:
            if remove:
                return text
            i = stop
            lines[i:i] = [" " * indent + name + ":\n"]
            stop += 1
        else:
            i = found[0]
        finish = i + 1
        while finish < stop:
            line = lines[finish]
            if (
                line.strip()
                and not line.lstrip().startswith("#")
                and len(line) - len(line.lstrip()) <= indent
            ):
                break
            finish += 1
        if pos == len(path) - 1:
            # Replace a single known field; nested values are deliberately rejected.
            if any(
                line.strip() and not line.lstrip().startswith("#") for line in lines[i + 1 : finish]
            ):
                raise ConnectError("Hermes 目标字段不是标量，请使用手动导出。")
            if remove:
                del lines[i]
            else:
                lines[i] = " " * indent + name + ": " + json.dumps(value, ensure_ascii=False) + "\n"
        else:
            rhs = lines[i].split(":", 1)[1].strip()
            if rhs and not rhs.startswith("#"):
                raise ConnectError("Hermes YAML 目标段使用行内映射，请使用手动导出。")
            start, stop, indent = i + 1, finish, indent + 2
    return "".join(lines)


def render_native(target, text, config, pid, model):
    protocol = CLIENTS[target][1]
    if protocol not in config["providers"][pid]["endpoints"]:
        raise ConnectError(
            f"当前 API 缺少 {protocol} 协议。请选择支持它的 API，或使用高级协议适配。"
        )
    root, key = gateway_url(config, pid), gateway_key()
    if target == "codex":
        return edit_codex(text, root, key, model)
    if target == "hermes":
        # Stale explicit model routes and key commands can override a newly selected named provider.
        removals = [
            ("model", key)
            for key in ("base_url", "api", "api_key", "api_mode", "key_env", "api_key_env")
        ]
        removals += [
            ("providers", "iteraconnect", key)
            for key in ("api", "url", "key_env", "key_cmd", "api_mode")
        ]
        if text.lstrip().startswith("{"):
            try:
                value = json.loads(text, object_pairs_hook=unique_object)
                for path in removals:
                    parent = value
                    for part in path[:-1]:
                        parent = parent.get(part, {})
                    parent.pop(path[-1], None)
                merge_dict(
                    value,
                    {
                        "model": {"provider": "custom:iteraconnect", "default": model},
                        "providers": {
                            "iteraconnect": {
                                "base_url": root + "/v1",
                                "api_key": key,
                                "transport": "chat_completions",
                            }
                        },
                    },
                )
                return json.dumps(value, indent=2) + "\n"
            except (ValueError, TypeError, AttributeError):
                raise ConnectError("无法解析 Hermes JSON 配置；原文件未修改。") from None
        if re.search(r"(?m)^(?:---|\.\.\.|%)", text):
            raise ConnectError("Hermes YAML 包含文档指令，请使用手动导出。")
        for path in removals:
            text = yaml_put(text, path, None, remove=True)
        for path, value in (
            (["model", "provider"], "custom:iteraconnect"),
            (["model", "default"], model),
            (["providers", "iteraconnect", "base_url"], root + "/v1"),
            (["providers", "iteraconnect", "api_key"], key),
            (["providers", "iteraconnect", "transport"], "chat_completions"),
        ):
            text = yaml_put(text, path, value)
        return text
    try:
        value = (
            json.loads(text, object_pairs_hook=unique_object)
            if text.strip()
            else ([] if target.startswith("workbuddy") else {})
        )
        if target.startswith("workbuddy"):
            models = value.get("models") if isinstance(value, dict) else value
            if not isinstance(models, list) or any(not isinstance(x, dict) for x in models):
                raise ValueError
            models = [x for x in models if x.get("vendor") != "iteraconnect"]
            models.append(
                {
                    "id": pid + "/" + model,
                    "name": "Agent Connect · " + model,
                    "vendor": "iteraconnect",
                    "apiKey": key,
                    "url": gateway_url(config) + "/v1/chat/completions",
                    "supportsToolCall": True,
                }
            )
            if isinstance(value, dict):
                value["models"] = models
            else:
                value = models
        elif target == "claude":
            # Explicitly neutralize competing API-key and cloud-provider settings at this scope.
            merge_dict(
                value,
                {
                    "model": model,
                    "env": {
                        "ANTHROPIC_BASE_URL": root,
                        "ANTHROPIC_AUTH_TOKEN": key,
                        "ANTHROPIC_API_KEY": "",
                        "ANTHROPIC_MODEL": model,
                        "CLAUDE_CODE_USE_BEDROCK": "0",
                        "CLAUDE_CODE_USE_VERTEX": "0",
                        "CLAUDE_CODE_USE_FOUNDRY": "0",
                    },
                },
            )
        else:
            merge_dict(
                value,
                {
                    "models": {
                        "mode": "merge",
                        "providers": {
                            "iteraconnect": {
                                "baseUrl": root + "/v1",
                                "apiKey": key,
                                "api": "openai-completions",
                                "models": [{"id": model, "name": model}],
                            }
                        },
                    },
                    "agents": {"defaults": {"model": {"primary": "iteraconnect/" + model}}},
                },
            )
            # An existing model allowlist also needs the newly selected model.
            defaults = value["agents"]["defaults"]
            if "models" in defaults:
                if not isinstance(defaults["models"], dict):
                    raise ValueError
                defaults["models"].setdefault("iteraconnect/" + model, {})
        return json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    except (ValueError, TypeError, AttributeError):
        raise ConnectError("客户端配置不是兼容的 JSON；原文件未修改，请使用手动导出。") from None


def digest(content):
    return hashlib.sha256(content).hexdigest()


def connect_native(target, config, pid, model, home=None, backups=None):
    path = client_path(target, home).resolve()
    backups = backups or state_dir() / "native-backups"
    record = backups / (target + ".json")
    old = path.read_bytes() if path.exists() else None
    try:
        text = (old or b"").decode("utf-8")
    except UnicodeError:
        raise ConnectError("客户端配置不是 UTF-8；原文件未修改。") from None
    new = render_native(target, text, config, pid, model).encode()
    if record.exists():
        saved = json.loads(record.read_text())
        if saved["path"] != str(path) or saved["applied_sha256"] != digest(old or b""):
            raise ConnectError("客户端配置在连接后发生变化。请先手动核对备份，避免覆盖你的修改。")
    else:
        saved = {"path": str(path), "original": text if old is not None else None}
    # Journal before mutation. If interrupted, rollback accepts the known before/after digest.
    saved["previous_sha256"] = digest(old or b"")
    saved["applied_sha256"] = digest(new)
    private_write(record, json.dumps(saved))
    private_write(path, new)
    return {
        "path": str(path),
        "message": "配置已连接。重启客户端后生效；使用期间保持 Agent Connect 运行。"
        + (
            " 在 WorkBuddy 的模型选择器中选择 custom-local:" + pid + "/" + model + "。"
            if target.startswith("workbuddy")
            else ""
        ),
    }


def disconnect_native(target, home=None, backups=None):
    path = client_path(target, home).resolve()
    record = (backups or state_dir() / "native-backups") / (target + ".json")
    if not record.exists():
        raise ConnectError("此客户端没有 Agent Connect 备份。")
    saved = json.loads(record.read_text())
    current = path.read_bytes() if path.exists() else b""
    if saved["path"] != str(path) or digest(current) not in (
        saved["applied_sha256"],
        saved["previous_sha256"],
    ):
        raise ConnectError(
            "客户端配置已有后续修改；为保护你的设置，停止自动恢复。备份位于 native-backups。"
        )
    if saved["original"] is None:
        path.unlink(missing_ok=True)
    else:
        private_write(path, saved["original"])
    record.unlink()
    return {"message": "已恢复连接前的配置，请重启客户端。"}
