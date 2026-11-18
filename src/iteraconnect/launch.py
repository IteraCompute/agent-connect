"""Launch native harnesses with process-local settings, without editing user config."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from .config import ConnectError, RuntimeConfig, api_key, gateway_key, gateway_url


def launch_args(config: RuntimeConfig, target: str, pid: str, model=None, via="gateway", args=()):
    p = config["providers"][pid]
    selected = model or p["default_model"]
    protocol = {"claude": "anthropic", "codex": "responses"}.get(target)
    if not protocol:
        raise ConnectError("run supports claude and codex; use connect for other agents")
    env = os.environ.copy()
    for provider in config["providers"].values():
        env.pop(provider["key_env"], None)
    if via == "magpie":
        root = env.get("ITERACONNECT_MAGPIE_URL", "http://127.0.0.1:3425").rstrip("/")
        base = root + ("/v1" if protocol == "responses" else "")
        key, selected = "magpie-" + target, "iteraconnect-" + pid + "/" + selected
    else:
        if protocol not in p["endpoints"]:
            raise ConnectError("Provider lacks this protocol; use --via magpie")
        if via == "direct":
            base, key = p["endpoints"][protocol], api_key(p)
        else:
            base = gateway_url(config, pid) + ("/v1" if protocol == "responses" else "")
            key = gateway_key()
    if target == "claude":
        for name in (
            "ANTHROPIC_API_KEY",
            "CLAUDE_CODE_OAUTH_TOKEN",
            "CLAUDE_CODE_USE_BEDROCK",
            "CLAUDE_CODE_USE_VERTEX",
            "CLAUDE_CODE_USE_FOUNDRY",
        ):
            env.pop(name, None)
        env.update(ANTHROPIC_BASE_URL=base, ANTHROPIC_AUTH_TOKEN=key, ANTHROPIC_MODEL=selected)
        command = [target, "--model", selected, *args]
    else:
        env["ITERACONNECT_SESSION_KEY"] = key
        overrides = {
            "model": selected,
            "model_provider": "iteraconnect",
            "model_providers.iteraconnect.name": "IteraCompute Agent Connect",
            "model_providers.iteraconnect.base_url": base,
            "model_providers.iteraconnect.env_key": "ITERACONNECT_SESSION_KEY",
            "model_providers.iteraconnect.wire_api": "responses",
            "model_providers.iteraconnect.requires_openai_auth": False,
            "model_providers.iteraconnect.supports_websockets": False,
        }
        command = [target]
        for name, value in overrides.items():
            command += ["-c", name + "=" + json.dumps(value)]
        command += list(args)
    # Vendor credentials never appear in argv or generated native config files.
    return command, env


def launch(config, target, pid, model=None, via="gateway", args=()):
    if not shutil.which(target):
        raise ConnectError(f"{target} is not installed")
    command, env = launch_args(config, target, pid, model, via, args)
    return subprocess.run(command, env=env).returncode
