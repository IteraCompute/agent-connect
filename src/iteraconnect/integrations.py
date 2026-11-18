"""Composition adapters: keep Magpie's full CLI and CC Switch's native import contract."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

from .config import ConnectError, RuntimeConfig, gateway_key, gateway_url, private_write, state_dir
from .network import json_request

CC_FORMATS = {
    "claude": "anthropic",
    "codex": "openai_responses",
    "gemini": "gemini_native",
    "agy": "gemini_native",
    "grokbuild": "openai_responses",
    "opencode": "openai_chat",
    "openclaw": "openai_chat",
    "hermes": "openai_chat",
    "pi": "openai_chat",
}
FORMAT_PROTOCOL = {
    "anthropic": "anthropic",
    "openai_responses": "responses",
    "openai_chat": "chat",
    "gemini_native": "gemini",
}


def lock_data():
    return json.loads(Path(__file__).with_name("upstreams.lock.json").read_text())


def magpie_bin() -> str:
    if path := os.environ.get("ITERACONNECT_MAGPIE_BIN"):
        if not Path(path).is_file():
            raise ConnectError("ITERACONNECT_MAGPIE_BIN is not a file")
        return path
    local = state_dir() / "bin" / ("magpie.exe" if os.name == "nt" else "magpie")
    if local.is_file():
        return str(local)
    if path := shutil.which("magpie"):
        return path
    raise ConnectError("Magpie is not installed; run: itera-connect install-magpie")


def install_magpie() -> Path:
    system = {"Darwin": "darwin", "Linux": "linux", "Windows": "windows"}.get(platform.system())
    machine = {"x86_64": "amd64", "AMD64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(
        platform.machine()
    )
    name = f"magpie-cli-{system}-{machine}" + (".exe" if system == "windows" else "")
    info = lock_data()["magpie"]["assets"].get(name)
    if not info:
        raise ConnectError("No pinned Magpie binary for this platform; build the pinned source")
    dest = state_dir() / "bin" / ("magpie.exe" if system == "windows" else "magpie")
    if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == info["sha256"]:
        private_write(
            dest.parent / "THIRD_PARTY_NOTICES",
            Path(__file__).with_name("upstream-notices.txt").read_text(),
        )
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=dest.parent, prefix=".magpie-")
    try:
        digest, length = hashlib.sha256(), 0
        with os.fdopen(fd, "wb") as output:
            with urllib.request.urlopen(info["url"], timeout=30) as response:
                while block := response.read(1024 * 1024):
                    length += len(block)
                    if length > info["size"]:
                        raise ConnectError("Magpie download exceeds pinned size")
                    digest.update(block)
                    output.write(block)
        if length != info["size"] or digest.hexdigest() != info["sha256"]:
            raise ConnectError("Magpie checksum mismatch; download was not installed")
        os.chmod(temporary, 0o700)
        os.replace(temporary, dest)
        private_write(
            dest.parent / "THIRD_PARTY_NOTICES",
            Path(__file__).with_name("upstream-notices.txt").read_text(),
        )
    except (OSError, ValueError):
        raise ConnectError("Magpie download failed; retry install-magpie") from None
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return dest


def magpie(args: list[str], capture=False, timeout=90, vendor_env_names=()):
    env = {**os.environ, "DO_NOT_TRACK": "1", "MAGPIE_NO_STATS": "1"}
    for name in vendor_env_names:
        env.pop(name, None)
    try:
        result = subprocess.run(
            [magpie_bin(), *args], env=env, capture_output=capture, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        raise ConnectError("Magpie command timed out") from None
    if result.returncode and capture:
        # Magpie can include keys and upstream error bodies; do not copy these to logs.
        raise ConnectError("Magpie command failed; inspect Magpie locally for details")
    return result


def magpie_providers() -> dict:
    folder = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "magpie"
    path = folder / "providers.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return {p["id"]: p for p in data["providers"]}
    except (ValueError, KeyError, TypeError):
        raise ConnectError(
            "Cannot read Magpie providers.json; refusing to overwrite providers"
        ) from None


def sync_magpie(config: RuntimeConfig) -> list[str]:
    base = gateway_url(config)
    hello = json_request("GET", base + "/health", timeout=3)
    if hello.get("name") != "iteraconnect":
        raise ConnectError("The local port is not an Agent Connect gateway")
    existing = magpie_providers()
    synced = []
    vendor_env_names = [p["key_env"] for p in config["providers"].values()]
    for pid, source in config["providers"].items():
        mid = "iteraconnect-" + pid
        root = gateway_url(config, pid)
        if old := existing.get(mid):
            old_urls = [old.get(k, "") for k in ("chat", "responses", "anthropic", "gemini")]
            if not any(u.startswith(root + "/") or u == root for u in old_urls):
                raise ConnectError(f"Magpie id {mid} is already used by another provider")
        # The only key passed to Magpie is the local relay key. Vendor keys stay in the relay.
        pairs = ["name=" + source["name"] + " · Agent Connect", "key=" + gateway_key()]
        pairs += ["url=" + (root + "/v1" if "chat" in source["endpoints"] else "")]
        pairs += ["responses=" + (root + "/v1" if "responses" in source["endpoints"] else "")]
        pairs += ["anthropic=" + (root if "anthropic" in source["endpoints"] else "")]
        pairs += ["gemini=" + (root + "/v1beta" if "gemini" in source["endpoints"] else "")]
        # This is also an authenticated health check: a different local key must fail sync.
        rows = json_request("GET", root + "/v1/models", gateway_key(), timeout=25)["data"]
        ids = [r["id"] for r in rows]
        if not ids:
            raise ConnectError(f"No models discovered for {pid}")
        if any("," in model for model in ids):
            raise ConnectError("Magpie CLI cannot import a model id containing a comma")
        pairs += ["models=" + ",".join(ids), "list=off"]
        if old:
            magpie(
                ["provider", "set", mid, *pairs], capture=True, vendor_env_names=vendor_env_names
            )
        else:
            magpie(
                ["provider", "add", source["name"] + " Agent Connect", "id=" + mid, *pairs],
                capture=True,
                vendor_env_names=vendor_env_names,
            )
        synced.append(mid)
    return synced


def connect(config: RuntimeConfig, target: str, pid: str, model: str | None = None):
    vendor_env_names = [p["key_env"] for p in config["providers"].values()]
    # WorkBuddy selects a model per task; its adapter connects a provider/picker, not a default model.
    if target in ("workbuddy", "workbuddy-ai"):
        magpie([target, "provider", "magpie"], capture=True, vendor_env_names=vendor_env_names)
    else:
        selected = model or config["providers"][pid]["default_model"]
        magpie(
            [target, "iteraconnect-" + pid + "/" + selected],
            capture=True,
            vendor_env_names=vendor_env_names,
        )


def cc_link(
    config: RuntimeConfig, target: str, pid: str, model=None, api_format=None, via="gateway"
) -> str:
    if target not in CC_FORMATS:
        raise ConnectError("This client has no CC Switch provider import; use: connect <client>")
    fmt = api_format or CC_FORMATS[target]
    protocol = FORMAT_PROTOCOL.get(fmt)
    if not protocol:
        raise ConnectError("Unsupported CC Switch API format")
    if target in ("gemini", "agy") and protocol != "gemini":
        raise ConnectError("This CC Switch client only supports gemini_native imports")
    if target in ("codex", "grokbuild", "hermes") and protocol == "gemini":
        raise ConnectError("This CC Switch client does not support gemini_native imports")
    p = config["providers"][pid]
    if via == "magpie":
        # Magpie converts protocols here when a provider only serves Chat, Messages, etc.
        root = os.environ.get("ITERACONNECT_MAGPIE_URL", "http://127.0.0.1:3425").rstrip("/")
        key = "magpie-iteraconnect-" + target
        selected = "iteraconnect-" + pid + "/" + (model or p["default_model"])
    else:
        if protocol not in p["endpoints"]:
            raise ConnectError("Provider lacks this native protocol; use --via magpie")
        root, key, selected = gateway_url(config, pid), gateway_key(), model or p["default_model"]
    suffix = (
        "/v1"
        if protocol in ("chat", "responses") or (protocol == "anthropic" and target == "opencode")
        else ""
    )
    if protocol == "gemini" and target in ("opencode", "openclaw", "pi"):
        suffix = "/v1beta"
    return "ccswitch://v1/import?" + urlencode(
        {
            "resource": "provider",
            "app": target,
            "name": p["name"] + " · Agent Connect",
            "endpoint": root + suffix,
            "apiKey": key,
            "apiFormat": fmt,
            "model": selected,
            "homepage": "https://github.com/IteraCompute/agent-connect",
            "enabled": "false",
        }
    )


def export_fragment(config: RuntimeConfig, target: str, pid: str, model=None) -> str:
    """Standalone fragments for manual merging; never overwrite native config files."""
    root, key = gateway_url(config, pid), gateway_key()
    p = config["providers"][pid]
    selected = model or p["default_model"]
    if target == "codex":
        if "responses" not in p["endpoints"]:
            raise ConnectError("Codex needs Responses; connect through Magpie for translation")
        return (
            f'model = {json.dumps(selected)}\nmodel_provider = "iteraconnect"\n\n'
            '[model_providers.iteraconnect]\nname = "IteraCompute Agent Connect"\n'
            f'base_url = {json.dumps(root + "/v1")}\nenv_key = "ITERACONNECT_GATEWAY_KEY"\n'
            'wire_api = "responses"\nrequires_openai_auth = false\nsupports_websockets = false\n'
        )
    value: dict[str, object] | list[dict[str, object]]
    if target == "claude":
        if "anthropic" not in p["endpoints"]:
            raise ConnectError("Claude Code needs Messages; connect through Magpie for translation")
        value = {
            "env": {
                "ANTHROPIC_BASE_URL": root,
                "ANTHROPIC_AUTH_TOKEN": key,
                "ANTHROPIC_MODEL": selected,
            }
        }
    elif target in ("workbuddy", "workbuddy-ai"):
        if "chat" not in p["endpoints"]:
            raise ConnectError("WorkBuddy needs Chat; connect through Magpie for translation")
        value = [
            {
                "id": selected,
                "name": p["name"] + " / " + selected,
                "vendor": "iteraconnect",
                "apiKey": key,
                "url": root + "/v1/chat/completions",
                "supportsToolCall": True,
            }
        ]
    elif target == "openclaw":
        if "chat" not in p["endpoints"]:
            raise ConnectError("This fragment uses Chat; use Magpie for another protocol")
        value = {
            "models": {
                "mode": "merge",
                "providers": {
                    "iteraconnect": {
                        "baseUrl": root + "/v1",
                        "apiKey": "${ITERACONNECT_GATEWAY_KEY}",
                        "api": "openai-completions",
                        "models": [{"id": selected, "name": selected}],
                    }
                },
            },
            "agents": {"defaults": {"model": {"primary": "iteraconnect/" + selected}}},
        }
    elif target == "hermes":
        if "chat" not in p["endpoints"]:
            raise ConnectError("This fragment uses Chat; use Magpie for another protocol")
        # JSON is also valid YAML; Hermes can read this standalone config.yaml fragment.
        value = {
            "model": {"provider": "iteraconnect", "default": selected},
            "providers": {
                "iteraconnect": {
                    "base_url": root + "/v1",
                    "api_key": key,
                    "api_mode": "chat_completions",
                }
            },
        }
    else:
        raise ConnectError("Use Magpie's native adapter for this client")
    return json.dumps(value, indent=2) + "\n"


def write_export(config, target, pid, path, model=None):
    if Path(path).exists():
        raise ConnectError("Export output already exists; choose a new file")
    private_write(Path(path), export_fragment(config, target, pid, model))
