"""Run installed clients in a temporary HOME, with no access to saved user logins."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .config import gateway_key, gateway_url
from .diagnostics import PROMPT
from .launch import launch_args


def reply_received(target, stdout):
    if target == "claude":
        return stdout.strip() == "ITERACONNECT_OK"
    if target == "hermes":
        try:
            events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
            return any(
                isinstance(event, dict)
                and event.get("type") == "result"
                and event.get("exit_code") == 0
                and not event.get("error")
                and event.get("text", "").strip() == "ITERACONNECT_OK"
                for event in events
            )
        except (ValueError, TypeError, AttributeError):
            return False
    if target == "codex":
        events = []
        try:
            events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
        except ValueError:
            return False
        messages = [e.get("item", {}) for e in events if e.get("type") == "item.completed"]
        return any(e.get("type") == "turn.completed" for e in events) and any(
            m.get("type") == "agent_message" and m.get("text", "").strip() == "ITERACONNECT_OK"
            for m in messages
        )
    # OpenClaw may print startup notices before its JSON result. Inspect actual reply payloads.
    decoder = json.JSONDecoder()
    for index, char in enumerate(stdout):
        if char != "{":
            continue
        try:
            data, _ = decoder.raw_decode(stdout[index:])
            if not isinstance(data, dict):
                continue
            data = data.get("result", data)
            if isinstance(data, dict) and any(
                p.get("text", "").strip() == "ITERACONNECT_OK" for p in data.get("payloads", [])
            ):
                return True
        except (ValueError, TypeError, AttributeError):
            continue
    return False


def sandbox_env(home: Path) -> dict:
    env = {
        k: v
        for k, v in os.environ.items()
        if k in ("PATH", "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "LC_ALL", "TERM")
    }
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_DATA_HOME": str(home / ".local/share"),
            "XDG_STATE_HOME": str(home / ".local/state"),
            "APPDATA": str(home / "AppData/Roaming"),
            "LOCALAPPDATA": str(home / "AppData/Local"),
            "CODEX_HOME": str(home / ".codex"),
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
            "HERMES_HOME": str(home / ".hermes"),
            "OPENCLAW_STATE_DIR": str(home / ".openclaw"),
            "OPENCLAW_CONFIG_PATH": str(home / ".openclaw/openclaw.json"),
            "DO_NOT_TRACK": "1",
            "DISABLE_TELEMETRY": "1",
            "MAGPIE_NO_STATS": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "NO_PROXY": "127.0.0.1,localhost",
            "CLAUDE_CODE_SIMPLE": "1",
            "NO_COLOR": "1",
        }
    )
    return env


def smoke(config, target, pid, model=None, via="gateway", timeout=90, native=False):
    if target not in ("claude", "codex", "openclaw", "hermes") or (
        target == "hermes" and via != "gateway"
    ):
        return {
            "kind": "native-client",
            "target": target,
            "status": "manual-required",
            "detail": "Use connect and the documented UI/CLI acceptance steps",
        }
    if not shutil.which(target):
        return {"kind": "native-client", "target": target, "status": "not-installed"}
    selected = model or config["providers"][pid]["default_model"]
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="iteraconnect-smoke-") as directory:
        home = Path(directory)
        env = sandbox_env(home)
        for name in ("CODEX_HOME", "CLAUDE_CONFIG_DIR", "HERMES_HOME", "OPENCLAW_STATE_DIR"):
            Path(env[name]).mkdir(parents=True, exist_ok=True)
        if target in ("claude", "codex"):
            args = (
                [
                    "-p",
                    "--tools",
                    "",
                    "--strict-mcp-config",
                    "--mcp-config",
                    '{"mcpServers":{}}',
                    "--setting-sources",
                    "",
                    PROMPT,
                ]
                if target == "claude"
                else ["exec", "--skip-git-repo-check", "--sandbox", "read-only", "--json", PROMPT]
            )
            command, routed = launch_args(config, target, pid, model, via, args)
            names = (
                "ANTHROPIC_BASE_URL",
                "ANTHROPIC_AUTH_TOKEN",
                "ANTHROPIC_MODEL",
                "ITERACONNECT_SESSION_KEY",
            )
            env.update({k: routed[k] for k in names if k in routed})
            if native:
                from .native import render_native

                folder = Path(env["CLAUDE_CONFIG_DIR" if target == "claude" else "CODEX_HOME"])
                path = folder / ("settings.json" if target == "claude" else "config.toml")
                path.write_text(render_native(target, "", config, pid, selected))
                if target == "claude":
                    args[args.index("--setting-sources") + 1] = "user"
                command = [target, *args]
                for name in names:
                    env.pop(name, None)
        elif target == "hermes":
            from .native import render_native

            seed = {
                "platform_toolsets": {"cli": []},
                "agent": {"max_turns": 1},
                "memory": {"memory_enabled": False, "user_profile_enabled": False},
            }
            path = Path(env["HERMES_HOME"]) / "config.yaml"
            path.write_text(render_native(target, json.dumps(seed), config, pid, selected))
            command = [
                target,
                "--ignore-rules",
                "chat",
                "--quiet",
                "--format",
                "stream-json",
                "--max-turns",
                "1",
                "-q",
                PROMPT,
            ]
        else:
            root, key = gateway_url(config, pid), gateway_key()
            api_base = root + "/v1"
            if via == "magpie":
                root = os.environ.get("ITERACONNECT_MAGPIE_URL", "http://127.0.0.1:3425")
                key, selected = "magpie-openclaw", "iteraconnect-" + pid + "/" + selected
                api_base = root.rstrip("/") + "/v1"
            elif via == "direct":
                from .config import api_key

                api_base = config["providers"][pid]["endpoints"]["chat"]
                key = api_key(config["providers"][pid])
            data = {
                "models": {
                    "mode": "merge",
                    "providers": {
                        "iteraconnect": {
                            "baseUrl": api_base,
                            "apiKey": key,
                            "api": "openai-completions",
                            "models": [
                                {
                                    "id": selected,
                                    "name": selected,
                                    "contextWindow": 32768,
                                    "maxTokens": 256,
                                }
                            ],
                        }
                    },
                },
                "agents": {
                    "defaults": {
                        "workspace": str(home / "workspace"),
                        "model": {"primary": "iteraconnect/" + selected},
                    }
                },
                "tools": {"deny": ["*"]},
            }
            path = Path(env["OPENCLAW_CONFIG_PATH"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
            if native:
                from .native import render_native

                path.write_text(render_native(target, path.read_text(), config, pid, selected))
            command = [
                target,
                "agent",
                "--local",
                "--agent",
                "main",
                "--session-id",
                "iteraconnect-smoke",
                "--message",
                PROMPT,
                "--thinking",
                "off",
                "--timeout",
                str(timeout),
                "--json",
            ]
        try:
            result = subprocess.run(
                command, env=env, cwd=home, capture_output=True, text=True, timeout=timeout
            )
            # Never publish arbitrary CLI output: it may contain URLs, credentials or private context.
            valid = result.returncode == 0 and reply_received(target, result.stdout)
            detail = (
                "expected reply received"
                if valid
                else f"client exited {result.returncode} or reply missing"
            )
            return {
                "kind": "native-client",
                "target": target,
                "via": via,
                "status": "passed" if valid else "failed",
                "detail": detail,
                "seconds": round(time.monotonic() - start, 3),
            }
        except subprocess.TimeoutExpired:
            return {
                "kind": "native-client",
                "target": target,
                "via": via,
                "status": "failed",
                "detail": "client timed out",
                "seconds": round(time.monotonic() - start, 3),
            }
        finally:
            if target == "hermes":
                # Hermes one-shot starts a profile gateway. Stop only this temporary profile's gateway.
                try:
                    subprocess.run(
                        [target, "gateway", "stop"],
                        env=env,
                        cwd=home,
                        capture_output=True,
                        timeout=15,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    pass
