"""One local control panel plus the inference relay; no third-party UI/runtime."""

from __future__ import annotations

import copy
import hmac
import json
import os
import secrets
import shutil
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .config import ConnectError, gateway_key, gateway_url, state_dir
from .diagnostics import probe
from .gateway import Gateway, provider_models
from .native import client_path, connect_native, disconnect_native, render_native
from .settings import (
    CLIENTS,
    check_settings,
    public_settings,
    read_settings,
    runtime_config,
    write_settings,
)
from .smoke import smoke


class App(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, settings, port=18424, relay_port=18423):
        self.settings_path = Path(settings).absolute()
        self.data = read_settings(self.settings_path)
        self.settings_bytes = self.settings_path.read_bytes()
        self.config = runtime_config(self.data, relay_port or 18423)
        self.token = secrets.token_urlsafe(32)
        self.operation = threading.Lock()
        self.relay = Gateway(self.config, address=("127.0.0.1", relay_port))
        self.config["gateway"]["port"] = self.relay.server_port
        try:
            super().__init__(("127.0.0.1", port), Handler)
        except OSError:
            self.relay.server_close()
            raise
        self.origin = "http://127.0.0.1:" + str(self.server_port)

    def activate(self, data, persist=False):
        check_settings(data)
        if persist and self.settings_path.read_bytes() != self.settings_bytes:
            raise ConnectError(
                "本地配置文件已被修改，请先点击「重新读取配置」，避免覆盖刚填的 key。"
            )
        config = runtime_config(data, self.relay.server_port)
        if persist:
            write_settings(self.settings_path, data)
        self.settings_bytes = self.settings_path.read_bytes()
        self.data, self.config, self.relay.config = data, config, config

    def state(self):
        return {
            "settings": public_settings(self.data),
            "settings_path": str(self.settings_path),
            "relay_port": self.relay.server_port,
            "clients": [self.client_state(k) for k in CLIENTS],
        }

    @staticmethod
    def client_state(target):
        client = CLIENTS[target]
        path = None if client.guided else client_path(target)
        command = {"vscode": "code", "visual-studio": "devenv"}.get(target, target)
        return {
            "id": target,
            "name": client.name,
            "protocol": client.protocols[0],
            "protocols": client.protocols,
            "guided": client.guided,
            "manual_test": client.manual_test,
            "next_step": client.next_step,
            "installed": bool(shutil.which(command)),
            "config_detected": bool(path and path.parent.exists()),
            "config_path": str(path) if path else None,
            "connected": bool(
                path and (state_dir() / "native-backups" / (target + ".json")).exists()
            ),
        }

    def draft_models(self, body):
        """Discover models without saving a draft or changing live relay credentials."""
        pid = body.get("provider")
        if not isinstance(pid, str):
            raise ConnectError("请选择有效的 API。")
        old = self.data["providers"].get(pid, {})
        provider = {k: body.get(k, old.get(k)) for k in ("name", "base_url", "protocols")}
        provider["model"] = body.get("model") or old.get("model") or "Auto"
        provider["api_key"] = body.get("api_key") or old.get("api_key", "")
        if "endpoints" in body or "endpoints" in old:
            provider["endpoints"] = body.get("endpoints", old.get("endpoints"))
        # Each request owns a distinct temporary env reference; the active provider
        # can keep serving requests with its original key during discovery.
        temporary = "catalog-" + secrets.token_hex(16)
        data = {
            "selected_provider": temporary,
            "client": body.get("client", self.data["client"]),
            "providers": {temporary: provider},
        }
        check_settings(data)
        if not provider["api_key"]:
            raise ConnectError("请先填写此 API 的 key。")
        key_env = "ITERACONNECT_APP_KEY_" + temporary.upper().replace("-", "_")
        try:
            config = runtime_config(data, self.relay.server_port)
            return {"models": [m["id"] for m in provider_models(config["providers"][temporary])]}
        finally:
            os.environ.pop(key_env, None)

    def save_selection(self, body):
        data = copy.deepcopy(self.data)
        pid, target = body.get("provider"), body.get("client")
        if target not in CLIENTS or not isinstance(pid, str):
            raise ConnectError("请选择有效的 API 和客户端。")
        old = data["providers"].get(pid, {})
        p = {k: body.get(k, old.get(k)) for k in ("name", "base_url", "model", "protocols")}
        p["api_key"] = body.get("api_key") or old.get("api_key", "")
        if "endpoints" in body:
            p["endpoints"] = body["endpoints"]
        elif "endpoints" in old:
            p["endpoints"] = old["endpoints"]
        data["providers"][pid] = p
        data["selected_provider"], data["client"] = pid, target
        self.activate(data, persist=True)

    def action(self, route, body):
        if route == "/api/models" and body:
            return self.draft_models(body)
        if route == "/api/reload":
            self.activate(read_settings(self.settings_path))
            return self.state()
        if route == "/api/disconnect":
            target = body.get("client", self.data["client"])
            if target not in CLIENTS or CLIENTS[target].guided:
                raise ConnectError("此客户端请在应用的模型管理中移除端点。")
            return disconnect_native(target)
        if route == "/api/save":
            self.save_selection(body)
            return self.state()
        if body and route in ("/api/connect", "/api/export", "/api/probe", "/api/smoke"):
            self.save_selection(body)
            return {**self.run_selected(route), "state": self.state()}
        return self.run_selected(route)

    def run_selected(self, route):
        pid, target = self.data["selected_provider"], self.data["client"]
        p = self.data["providers"][pid]
        if route == "/api/export":
            fragment = render_native(target, "", self.config, pid, p["model"])
            # Export substitutes the local relay token, never a vendor key.
            return {"fragment": fragment, "message": "手动合并到客户端配置；仅含本地网关令牌。"}
        if not p["api_key"]:
            raise ConnectError("请先填写并保存 API key，或修改本地配置后点击「重新读取」。")
        if route == "/api/models":
            return {"models": [m["id"] for m in provider_models(self.config["providers"][pid])]}
        if route == "/api/connect":
            if CLIENTS[target].guided:
                if "chat" not in p["protocols"]:
                    raise ConnectError("Visual Studio 的此接入方式需要 Chat Completions。")
                return {
                    "setup": "guided",
                    "base_url": gateway_url(self.config, pid) + "/v1",
                    "model": p["model"],
                    "local_key": gateway_key(),
                }
            return connect_native(target, self.config, pid, p["model"])
        if route == "/api/probe":
            protocol = CLIENTS[target].select_protocol(p["protocols"])
            if protocol not in p["protocols"]:
                raise ConnectError(f"此客户端需要 {protocol} 协议，当前 API 未配置。")
            return probe(self.config, pid, protocols=[protocol], budget=256)
        if route == "/api/smoke":
            if CLIENTS[target].manual_test:
                return {
                    "status": "manual-required",
                    "message": CLIENTS[target].next_step.format(provider=pid, model=p["model"])
                    + " 在新会话发送：Reply with exactly ITERACONNECT_OK. 核对回复。",
                }
            return smoke(self.config, target, pid, timeout=90, native=True)
        raise ConnectError("未知操作。")


class Handler(BaseHTTPRequestHandler):
    server: App
    server_version = "AgentConnect"
    sys_version = ""

    def log_message(self, *_):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def reply(self, status, raw, mime="application/json; charset=utf-8"):
        if not isinstance(raw, bytes):
            raw = json.dumps(raw, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )
        self.end_headers()
        try:
            self.wfile.write(raw)
        except OSError:
            pass

    def authorized(self, api=True):
        if self.headers.get("Host") != urlsplit(self.server.origin).netloc:
            self.reply(403, {"error": "只允许本机访问。"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin != self.server.origin:
            self.reply(403, {"error": "不允许跨站请求。"})
            return False
        if api and not hmac.compare_digest(
            self.headers.get("X-Agent-Connect", "").encode(), self.server.token.encode()
        ):
            self.reply(401, {"error": "请使用启动器打开的完整地址。"})
            return False
        return True

    def do_GET(self):
        if not self.authorized(api=self.path.startswith("/api/")):
            return
        if self.path == "/api/state":
            self.reply(200, self.server.state())
            return
        files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/app.css": ("app.css", "text/css; charset=utf-8"),
        }
        if self.path in files:
            name, mime = files[self.path]
            self.reply(200, Path(__file__).with_name("web").joinpath(name).read_bytes(), mime)
        else:
            self.reply(404, {"error": "页面不存在。"})

    def do_POST(self):
        if not self.authorized():
            return
        if not self.server.operation.acquire(blocking=False):
            self.reply(409, {"error": "上一个操作仍在进行，请稍后重试。"})
            return
        previous_data = self.server.data
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 32768 or self.headers.get("Content-Type") != "application/json":
                raise ConnectError("请求必须是小于 32 KiB 的 JSON。")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError
            self.reply(200, self.server.action(self.path, body))
        except ConnectError as e:
            self.action_error(str(e), previous_data)
        except (ValueError, TypeError, KeyError, AttributeError, OSError):
            self.action_error("操作未完成，请检查配置、文件权限及网络。", previous_data)
        finally:
            self.server.operation.release()

    def action_error(self, message, previous_data):
        error = {"error": message}
        if self.server.data is not previous_data:
            # The submitted API was saved before the client operation failed.
            error.update(error="API 设置已保存。" + message, state=self.server.state())
        self.reply(400, error)


def serve_app(settings, port=18424, relay_port=18423, open_browser=True):
    with App(settings, port, relay_port) as app, app.relay:
        worker = threading.Thread(target=app.relay.serve_forever, daemon=True)
        worker.start()
        url = app.origin + "/#" + app.token
        print("Agent Connect 已启动：" + url, flush=True)
        print("配置文件：" + str(app.settings_path), flush=True)
        print("使用客户端期间请保持此窗口运行；Ctrl+C 退出。", flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            app.serve_forever()
        finally:
            app.relay.shutdown()
            worker.join(timeout=3)
