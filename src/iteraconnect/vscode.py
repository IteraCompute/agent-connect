"""Insert a Custom Endpoint group into the VS Code user's model catalog."""

import json
import os
import re
import sys
from pathlib import Path

from .config import ConnectError


def models_path(home):
    if location := os.environ.get("ITERACONNECT_VSCODE_USER_DIR"):
        user = Path(location).expanduser()
    elif sys.platform == "darwin":
        user = home / "Library/Application Support/Code/User"
    elif os.name == "nt":
        user = Path(os.environ.get("APPDATA") or home / "AppData/Roaming") / "Code/User"
    else:
        user = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / "Code/User"
    return user / "chatLanguageModels.json"


# Mask comments without changing offsets or matching comment markers inside strings.
_STRING = r'"(?:[^"\\]|\\.)*"'
_TOKENS = re.compile(_STRING + r"|//[^\r\n]*|/\*[\s\S]*?\*/")
_TRAILING_COMMA = re.compile(_STRING + r"|,\s*(?=[]}])")


def insert_group(text, root, key, model):
    group = {
        "name": "Agent Connect",
        "vendor": "customendpoint",
        "apiType": "chat-completions",
        "models": [
            {
                "id": model,
                "name": model,
                "url": root + "/v1/chat/completions",
                # VS Code resolves the provider apiKey via its interactive secret store.
                # Custom Endpoint supports an explicit auth header for local gateways.
                "requestHeaders": {"Authorization": "Bearer " + key},
                "toolCalling": True,
                "vision": False,
                "maxInputTokens": 16384,
                "maxOutputTokens": 2048,
            }
        ],
    }
    if not text.strip():
        return json.dumps([group], ensure_ascii=False, indent=2) + "\n"
    sanitized = _TOKENS.sub(lambda m: " " * len(m[0]) if m[0].startswith("/") else m[0], text)

    def remove_trailing(m):
        if m[0].startswith(",") and sanitized[: m.start()].rstrip()[-1:] not in ("[", "{", ",", ""):
            return " " * len(m[0])
        return m[0]

    try:
        groups = json.loads(_TRAILING_COMMA.sub(remove_trailing, sanitized))
        if not isinstance(groups, list) or not all(isinstance(g, dict) for g in groups):
            raise ValueError
    except ValueError:
        raise ConnectError(
            "无法读取 VS Code 模型列表，请导出配置并在“管理语言模型”中添加。"
        ) from None
    if any(g.get("name") == group["name"] for g in groups):
        raise ConnectError("VS Code 已有 Agent Connect 分组。请先重命名该分组或使用手动导出。")
    # Insert at the opening bracket. Existing groups, comments and trailing commas stay verbatim.
    pos = sanitized.index("[") + 1
    inserted = "\n" + "\n".join(
        "  " + line for line in json.dumps(group, ensure_ascii=False, indent=2).splitlines()
    )
    return text[:pos] + inserted + ("," if groups else "") + "\n" + text[pos:]
