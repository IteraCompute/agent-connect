"""Small, versioned configuration. Provider credentials are environment references."""

from __future__ import annotations

import copy
import ipaddress
import json
import os
import re
import secrets
import tempfile
from pathlib import Path
from typing import NotRequired, TypedDict
from urllib.parse import urlsplit

PROTOCOLS = ("chat", "responses", "anthropic", "gemini")


class ProviderConfig(TypedDict):
    name: str
    key_env: str
    default_model: str
    endpoints: dict[str, str]
    allow_http: NotRequired[bool]


class GatewayConfig(TypedDict):
    host: str
    port: int
    timeout: float


class RuntimeConfig(TypedDict):
    schema_version: int
    active_provider: str
    gateway: GatewayConfig
    providers: dict[str, ProviderConfig]


DEFAULT: RuntimeConfig = {
    "schema_version": 1,
    "active_provider": "iteracompute",
    "gateway": {"host": "127.0.0.1", "port": 18423, "timeout": 180},
    "providers": {
        "iteracompute": {
            "name": "IteraCompute",
            "key_env": "ITERACOMPUTE_API_KEY",
            "default_model": "Auto",
            "endpoints": {
                "chat": "https://api.iteracompute.com/v1",
                "responses": "https://api.iteracompute.com/v1",
                "anthropic": "https://api.iteracompute.com",
            },
        }
    },
}


class ConnectError(Exception):
    """An error safe to show to the user, without upstream data or credentials."""


def state_dir() -> Path:
    if p := os.environ.get("ITERACONNECT_HOME"):
        return Path(p).expanduser().absolute()
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "iteraconnect"


def private_write(path: Path, content: str | bytes) -> None:
    """Replace one file atomically; never create a world-readable intermediate file."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content.encode() if isinstance(content, str) else content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def validate_url(value: str, allow_http: bool = False) -> str:
    try:
        p = urlsplit(value)
        _ = p.port
        if p.scheme not in ("http", "https") or not p.hostname:
            raise ValueError
        if p.username or p.password or p.query or p.fragment:
            raise ValueError
        if any(c.isspace() or ord(c) < 32 for c in value):
            raise ValueError
        loopback = p.hostname == "localhost"
        try:
            loopback = loopback or ipaddress.ip_address(p.hostname).is_loopback
        except ValueError:
            pass
        if p.scheme == "http" and not (loopback or allow_http):
            raise ConnectError("HTTP requires --allow-http except on loopback addresses")
    except ValueError:
        raise ConnectError(
            "Invalid endpoint: use an HTTP(S) URL without credentials or query"
        ) from None
    return value.rstrip("/")


def validate(data: RuntimeConfig) -> RuntimeConfig:
    try:
        if data["schema_version"] != 1 or not data["providers"]:
            raise ValueError
        gateway = data["gateway"]
        # This gateway holds vendor credentials. Remote/LAN serving belongs to Magpie.
        if gateway["host"] not in ("127.0.0.1", "localhost"):
            raise ConnectError(
                "Agent Connect binds to loopback; use Magpie's sharing for remote access"
            )
        if type(gateway["port"]) is not int or not 1 <= gateway["port"] <= 65535:
            raise ValueError
        if not 1 <= gateway["timeout"] <= 600:
            raise ValueError
        if data["active_provider"] not in data["providers"]:
            raise ValueError
        for pid, p in data["providers"].items():
            if not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", pid):
                raise ValueError
            if not isinstance(p["name"], str) or not p["name"]:
                raise ValueError
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", p["key_env"]):
                raise ValueError
            if not isinstance(p["default_model"], str) or not p["default_model"].strip():
                raise ValueError
            if not p["endpoints"] or set(p["endpoints"]) - set(PROTOCOLS):
                raise ValueError
            if type(p.get("allow_http", False)) is not bool:
                raise ValueError
            for protocol, endpoint in p["endpoints"].items():
                p["endpoints"][protocol] = validate_url(endpoint, p.get("allow_http", False))
            # Never silently accept inline keys from hand-edited configs.
            if set(p) - {"name", "key_env", "default_model", "endpoints", "allow_http"}:
                raise ConnectError("Provider config accepts key_env, never inline credentials")
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ConnectError(
            "Invalid Agent Connect configuration; see docs/configuration.md"
        ) from None
    return data


def load(path: Path | None = None) -> RuntimeConfig:
    path = path or state_dir() / "config.json"
    if not path.exists():
        return copy.deepcopy(DEFAULT)
    try:
        return validate(json.loads(path.read_text()))
    except (json.JSONDecodeError, UnicodeError):
        raise ConnectError("Invalid configuration JSON") from None


def save(data: RuntimeConfig, path: Path | None = None) -> None:
    private_write(path or state_dir() / "config.json", json.dumps(validate(data), indent=2) + "\n")


def gateway_key() -> str:
    if value := os.environ.get("ITERACONNECT_GATEWAY_KEY"):
        if len(value) < 24 or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ConnectError(
                "ITERACONNECT_GATEWAY_KEY needs at least 24 printable ASCII characters"
            )
        return value
    path = state_dir() / "gateway.key"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        value = path.read_text().strip()
        if len(value) < 24:
            raise ConnectError(
                "Invalid gateway.key; restore it or remove it to create a new local key"
            ) from None
        return value
    value = "ic-" + secrets.token_urlsafe(32)
    with os.fdopen(fd, "w") as f:
        f.write(value)
    return value


def api_key(provider: ProviderConfig, required: bool = True) -> str:
    value = os.environ.get(provider["key_env"], "")
    if required and not value:
        raise ConnectError(f"Set {provider['key_env']} in the gateway process environment")
    if any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ConnectError(f"{provider['key_env']} must contain printable ASCII without whitespace")
    return value


def gateway_url(config: RuntimeConfig, pid: str | None = None) -> str:
    base = f"http://127.0.0.1:{config['gateway']['port']}"
    return base + (f"/p/{pid}" if pid else "")
