"""Exercise the simple entry point with fixture credentials and a local vendor only."""

import copy
import http.client
import json
import os
import stat
import tempfile
import threading
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from iteraconnect.app import App
from iteraconnect.config import DEFAULT, ConnectError
from iteraconnect.native import client_path, connect_native, disconnect_native, render_native
from iteraconnect.settings import (
    APP_DEFAULT,
    public_settings,
    read_settings,
    runtime_config,
    write_settings,
)
from iteraconnect.smoke import smoke

from .fixtures import LOCAL_KEY, MODEL, VENDOR_KEY, stack


class PrivateSettingsTests(unittest.TestCase):
    def test_editable_toml_roundtrip_private_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.toml"
            data = read_settings(path)
            data["providers"]["iteracompute"]["api_key"] = VENDOR_KEY
            write_settings(path, data)
            self.assertEqual(read_settings(path), data)
            self.assertNotIn(VENDOR_KEY, json.dumps(public_settings(data)))
            self.assertTrue(public_settings(data)["providers"]["iteracompute"]["has_key"])
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_explicit_file_key_does_not_fall_back_to_inherited_key(self):
        with patch.dict(os.environ, {"ITERACOMPUTE_API_KEY": "unrelated-existing-key"}):
            data = copy.deepcopy(APP_DEFAULT)
            runtime = runtime_config(data)
            self.assertEqual(os.environ[runtime["providers"]["iteracompute"]["key_env"]], "")
            data["providers"]["iteracompute"]["api_key"] = VENDOR_KEY
            runtime = runtime_config(data)
            self.assertEqual(
                os.environ[runtime["providers"]["iteracompute"]["key_env"]], VENDOR_KEY
            )
            self.assertNotIn(VENDOR_KEY, json.dumps(runtime))

    def test_nonstandard_protocol_paths_survive_roundtrip(self):
        data = copy.deepcopy(APP_DEFAULT)
        p = data["providers"]["iteracompute"]
        p["base_url"] = "https://example.test/openai/v1"
        p["endpoints"] = {"anthropic": "https://example.test/anthropic"}
        with patch.dict(os.environ):
            runtime = runtime_config(data)
        self.assertEqual(runtime["providers"]["iteracompute"]["endpoints"]["chat"], p["base_url"])
        self.assertEqual(
            runtime["providers"]["iteracompute"]["endpoints"]["anthropic"],
            p["endpoints"]["anthropic"],
        )

    def test_malformed_file_never_discloses_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.toml"
            path.write_text('api_key = "' + VENDOR_KEY)
            with self.assertRaises(ConnectError) as error:
                read_settings(path)
            self.assertNotIn(VENDOR_KEY, str(error.exception))


class NativeEditorTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"ITERACONNECT_GATEWAY_KEY": LOCAL_KEY}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_all_adapters_preserve_settings_reconnect_and_restore_exactly(self):
        seeds = {
            "claude": '{"theme":"dark","env":{"KEEP":"yes"}}\n',
            "codex": '# a comment\nmodel = "old"\n[history]\npersistence = "none"\n',
            "workbuddy": '[{"id":"mine","vendor":"mine","enabled":false}]\n',
            "workbuddy-ai": '[{"id":"mine","vendor":"mine","enabled":false}]\n',
            "vscode": '[{"vendor":"mine","models":[{"id":"keep"}]}]\n',
            "openclaw": '{"messages":{"responsePrefix":"keep"},"agents":{"defaults":{"models":{"mine/old":{}}}}}\n',
            "hermes": "# my config\nmodel:\n  provider: openrouter\n  default: old\nui:\n  theme: dark",
        }
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            for target, original in seeds.items():
                with self.subTest(target=target):
                    path = client_path(target, home)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(original)
                    connect_native(target, DEFAULT, "iteracompute", MODEL, home, home / "backups")
                    first = path.read_text()
                    self.assertNotIn(VENDOR_KEY, first)
                    self.assertIn(LOCAL_KEY, first)
                    connect_native(
                        target, DEFAULT, "iteracompute", MODEL + "-new", home, home / "backups"
                    )
                    self.assertIn(MODEL + "-new", path.read_text())
                    if target == "codex":
                        self.assertEqual(tomllib.loads(first)["history"]["persistence"], "none")
                        self.assertIn("# a comment", first)
                    if target == "hermes":
                        self.assertIn("ui:\n  theme: dark", first)
                        self.assertIn("# my config", first)
                    if target.startswith("workbuddy"):
                        rows = json.loads(first)
                        self.assertFalse(rows[0]["enabled"])
                        self.assertEqual(rows[1]["id"], "iteracompute/" + MODEL)
                    if target == "openclaw":
                        self.assertIn(
                            "iteraconnect/" + MODEL,
                            json.loads(first)["agents"]["defaults"]["models"],
                        )
                    disconnect_native(target, home, home / "backups")
                    self.assertEqual(path.read_text(), original)

    def test_restoring_a_new_file_removes_it_and_later_edits_are_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            backups = home / "backups"
            path = client_path("claude", home)
            connect_native("claude", DEFAULT, "iteracompute", MODEL, home, backups)
            disconnect_native("claude", home, backups)
            self.assertFalse(path.exists())
            connect_native("claude", DEFAULT, "iteracompute", MODEL, home, backups)
            path.write_text(path.read_text() + "\n")
            with self.assertRaises(ConnectError):
                disconnect_native("claude", home, backups)
            with self.assertRaises(ConnectError):
                connect_native("claude", DEFAULT, "iteracompute", MODEL, home, backups)

    def test_ambiguous_client_config_is_never_overwritten(self):
        for target, text in (
            ("hermes", "model: {provider: old}\n"),
            ("hermes", '"model":\n  provider: old\n'),
            ("openclaw", '{ // JSON5\n "key":true\n}'),
            ("codex", '[model_providers.iteraconnect]\nname="another app"\n'),
        ):
            with self.subTest(target=target), self.assertRaises(ConnectError):
                render_native(target, text, DEFAULT, "iteracompute", MODEL)

    def test_workbuddy_object_and_duplicate_json_fields(self):
        text = (
            '{"models":[{"id":"mine","vendor":"mine"}],"availableModels":["mine"],"theme":"dark"}'
        )
        data = json.loads(render_native("workbuddy", text, DEFAULT, "iteracompute", MODEL))
        self.assertEqual(data["availableModels"], ["mine", "iteracompute/" + MODEL])
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(len(data["models"]), 2)
        with self.assertRaises(ConnectError):
            render_native(
                "claude", '{"env":{},"env":{"KEEP":"yes"}}', DEFAULT, "iteracompute", MODEL
            )

    def test_workbuddy_picker_survives_switches_and_respects_unrestricted_lists(self):
        for target in ("workbuddy", "workbuddy-ai"):
            for allowed in ([], ["mine"], None):
                with self.subTest(target=target, allowed=allowed):
                    seed = {"models": [{"id": "mine"}]}
                    if allowed is not None:
                        seed["availableModels"] = allowed
                    first = render_native(target, json.dumps(seed), DEFAULT, "iteracompute", MODEL)
                    updated = json.loads(
                        render_native(target, first, DEFAULT, "iteracompute", "new/model")
                    )
                    expected = ["mine", "iteracompute/new/model"] if allowed else allowed
                    self.assertEqual(updated.get("availableModels"), expected)
                    self.assertEqual(
                        [r["id"] for r in updated["models"]], ["mine", "iteracompute/new/model"]
                    )
            with self.assertRaises(ConnectError):
                render_native(target, '[{"id":"iteracompute/dup"}]', DEFAULT, "iteracompute", "dup")

    def test_codex_root_after_array_and_comment_preserves_nested_settings(self):
        original = '# models [example]\nfeatures_list = ["keep"]\nmodel = "old"\n[profiles.test]\nmodel="keep"\n'
        edited = tomllib.loads(render_native("codex", original, DEFAULT, "iteracompute", MODEL))
        self.assertEqual(edited["model"], MODEL)
        self.assertEqual(edited["profiles"]["test"]["model"], "keep")

    def test_vscode_jsonc_preservation_switch_conflicts_and_exact_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            backups = home / "backups"
            path = client_path("vscode", home)
            path.parent.mkdir(parents=True)
            original = (
                b'// [ providers ]\r\n[ /* keep */ {"url":"https://mine/a,]", "models":[],}, ]\r\n'
            )
            path.write_bytes(original)
            for model in ("first", "next/model"):
                connect_native("vscode", DEFAULT, "iteracompute", model, home, backups)
                raw = path.read_bytes()
                self.assertIn(b'/* keep */ {"url":"https://mine/a,]", "models":[],},', raw)
                self.assertEqual(raw.count(b'"vendor": "customendpoint"'), 1)
                self.assertIn(model.encode(), raw)
            path.write_bytes(raw + b"// new edit")
            with self.assertRaises(ConnectError):
                disconnect_native("vscode", home, backups)
            path.write_bytes(raw)
            disconnect_native("vscode", home, backups)
            self.assertEqual(path.read_bytes(), original)
            for seed in ('[{"name":"Agent Connect"}]', "[,]", "{}", "[/* broken]"):
                path.write_text(seed)
                with self.assertRaises(ConnectError):
                    connect_native("vscode", DEFAULT, "iteracompute", MODEL, home, backups)
                self.assertEqual(path.read_text(), seed)
                self.assertFalse((backups / "vscode.json").exists())

    def test_hermes_stale_endpoint_and_key_command_cannot_override_selection(self):
        values = (
            'model:\n  provider: custom\n  base_url: "https://oldvendor.example/v1"\n  api_key: old-key\n  key_env: OLD_KEY\nproviders:\n  iteraconnect:\n    key_cmd: old-helper\n    api: "https://oldvendor.example/v1"\nui:\n  theme: dark\n',
            json.dumps(
                {
                    "model": {
                        "provider": "custom",
                        "base_url": "https://oldvendor.example/v1",
                        "api_key": "old-key",
                        "key_env": "OLD_KEY",
                    },
                    "providers": {
                        "iteraconnect": {
                            "key_cmd": "old-helper",
                            "api": "https://oldvendor.example/v1",
                        }
                    },
                    "ui": {"theme": "dark"},
                }
            ),
        )
        for value in values:
            result = render_native("hermes", value, DEFAULT, "iteracompute", MODEL)
            self.assertNotIn("oldvendor.example", result)
            self.assertNotIn("old-key", result)
            self.assertNotIn("old-helper", result)
            self.assertIn("dark", result)
            self.assertIn(LOCAL_KEY, result)

    @unittest.skipIf(os.name == "nt", "Windows symlink privilege varies")
    def test_symlinked_client_config_is_kept_as_a_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            original = '{"theme":"dark"}\n'
            real = home / "dotfiles" / "claude.json"
            real.parent.mkdir()
            real.write_text(original)
            path = client_path("claude", home)
            path.parent.mkdir()
            path.symlink_to(real)
            connect_native("claude", DEFAULT, "iteracompute", MODEL, home, home / "backups")
            self.assertTrue(path.is_symlink())
            self.assertIn(LOCAL_KEY, real.read_text())
            disconnect_native("claude", home, home / "backups")
            self.assertEqual(real.read_text(), original)


class ControlPanelTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = patch.dict(
            os.environ,
            {"ITERACONNECT_HOME": self.folder.name, "ITERACONNECT_GATEWAY_KEY": LOCAL_KEY},
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.app = App(Path(self.folder.name) / "settings.toml", port=0, relay_port=0)
        self.addCleanup(self.app.server_close)
        self.addCleanup(self.app.relay.server_close)
        self.worker = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.app.shutdown)

    def call(self, path, body=None, headers=None, auth=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.app.server_port, timeout=10)
        request_headers = {"Content-Type": "application/json"}
        if auth:
            request_headers["X-Agent-Connect"] = self.app.token
        request_headers.update(headers or {})
        conn.request(
            "POST" if body is not None else "GET",
            path,
            json.dumps(body) if body is not None else None,
            request_headers,
        )
        response = conn.getresponse()
        raw = response.read()
        status = response.status
        conn.close()
        return status, raw

    def test_api_auth_origin_host_and_static_assets(self):
        self.assertEqual(self.call("/api/state", auth=False)[0], 401)
        self.assertEqual(
            self.call("/api/state", headers={"Origin": "https://evil.example"})[0], 403
        )
        self.assertEqual(self.call("/api/state", headers={"Host": "evil.example"})[0], 403)
        for path in ("/", "/app.css", "/app.js"):
            self.assertEqual(self.call(path, auth=False)[0], 200)
        self.assertEqual(self.call("/../../settings.toml")[0], 404)

    def test_save_redacts_key_reload_and_empty_key_blocks_inference(self):
        self.assertEqual(self.call("/api/probe", {})[0], 400)
        body = {"provider": "iteracompute", "client": "codex", "api_key": VENDOR_KEY}
        status, raw = self.call("/api/save", body)
        self.assertEqual(status, 200)
        self.assertNotIn(VENDOR_KEY.encode(), raw)
        self.assertTrue(json.loads(raw)["settings"]["providers"]["iteracompute"]["has_key"])
        self.assertEqual(self.call("/api/save", {**body, "api_key": ""})[0], 200)
        self.assertEqual(
            read_settings(self.app.settings_path)["providers"]["iteracompute"]["api_key"],
            VENDOR_KEY,
        )
        self.assertNotIn(VENDOR_KEY.encode(), self.call("/api/reload", {})[1])

    def test_simple_ui_protocol_probe_against_fixture_vendor(self):
        # stack() supplies only a localhost vendor; no real API service is reachable in this test.
        with stack() as (fixture_config, vendor, gateway):
            provider = copy.deepcopy(APP_DEFAULT["providers"]["iteracompute"])
            provider.update(
                api_key=VENDOR_KEY,
                model=MODEL,
                base_url=fixture_config["providers"]["iteracompute"]["endpoints"]["anthropic"],
            )
            data = copy.deepcopy(APP_DEFAULT)
            data["providers"]["iteracompute"] = provider
            self.app.activate(data)
            worker = threading.Thread(target=self.app.relay.serve_forever, daemon=True)
            worker.start()
            try:
                status, raw = self.call("/api/probe", {})
                self.assertEqual(status, 200, raw)
                self.assertTrue(json.loads(raw)["passed"], raw)
                self.assertNotIn(VENDOR_KEY.encode(), raw)
            finally:
                self.app.relay.shutdown()
                worker.join(timeout=3)

    def test_model_discovery_works_before_saving_a_custom_provider_or_model(self):
        original = self.app.settings_path.read_bytes()
        active = copy.deepcopy(self.app.config)
        active_key_env = active["providers"]["iteracompute"]["key_env"]
        original_key = os.environ[active_key_env]
        before_env = dict(os.environ)
        with stack() as (config, vendor, gateway):
            status, raw = self.call(
                "/api/models",
                {
                    "provider": "my-api",
                    "name": "My API",
                    "client": "codex",
                    "base_url": config["providers"]["iteracompute"]["endpoints"]["chat"],
                    "protocols": ["chat", "responses"],
                    "api_key": VENDOR_KEY,
                    "model": "",
                },
            )
        self.assertEqual(status, 200, raw)
        self.assertIn(MODEL, json.loads(raw)["models"])
        self.assertNotIn(VENDOR_KEY.encode(), raw)
        self.assertEqual(self.app.settings_path.read_bytes(), original)
        self.assertEqual(self.app.config, active)
        self.assertEqual(os.environ[active_key_env], original_key)
        self.assertFalse(set(os.environ) - set(before_env))
        self.assertNotIn("my-api", self.app.data["providers"])

    def test_failed_draft_discovery_cleans_up_and_preserves_the_saved_key(self):
        self.app.data["providers"]["iteracompute"]["api_key"] = VENDOR_KEY
        original = self.app.settings_path.read_bytes()
        before_env = dict(os.environ)
        with patch("iteraconnect.app.provider_models", side_effect=ConnectError("目录暂不可用")):
            status, raw = self.call(
                "/api/models", {"provider": "iteracompute", "api_key": "draft-only-key"}
            )
        self.assertEqual(status, 400)
        self.assertNotIn(b"draft-only-key", raw)
        self.assertEqual(self.app.settings_path.read_bytes(), original)
        self.assertEqual(self.app.data["providers"]["iteracompute"]["api_key"], VENDOR_KEY)
        self.assertEqual(dict(os.environ), before_env)

    def test_visual_studio_guided_setup_is_scoped_and_never_records_a_connection(self):
        selected = {"provider": "iteracompute", "client": "visual-studio", "api_key": VENDOR_KEY}
        self.assertEqual(self.call("/api/connect", selected, auth=False)[0], 401)
        status, raw = self.call("/api/connect", selected)
        self.assertEqual(status, 200)
        self.assertNotIn(VENDOR_KEY.encode(), raw)
        guide = json.loads(raw)
        self.assertEqual(guide["local_key"], LOCAL_KEY)
        self.assertEqual(
            guide["base_url"], f"http://127.0.0.1:{self.app.relay.server_port}/p/iteracompute/v1"
        )
        self.assertEqual(guide["setup"], "guided")
        self.assertNotIn(LOCAL_KEY.encode(), self.call("/api/state")[1])
        client = next(c for c in guide["state"]["clients"] if c["id"] == "visual-studio")
        self.assertIsNone(client["config_path"])
        self.assertFalse(client["connected"])
        self.assertTrue(client["manual_test"])
        self.assertEqual(json.loads(self.call("/api/smoke", {})[1])["status"], "manual-required")
        for route in ("disconnect", "export"):
            self.assertEqual(self.call("/api/" + route, {})[0], 400)
        status, failed = self.call("/api/connect", {**selected, "protocols": ["responses"]})
        self.assertEqual(status, 400)
        self.assertNotIn(VENDOR_KEY.encode(), failed)
        self.assertEqual(json.loads(failed)["state"]["settings"]["client"], "visual-studio")

    def test_desktop_connection_values_route_model_catalog_and_chat_to_fixture(self):
        from iteraconnect.diagnostics import payload, send

        worker = threading.Thread(target=self.app.relay.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(self.app.relay.shutdown)
        base = Path(self.folder.name)
        dirs = {
            "WORKBUDDY_CONFIG_DIR": str(base / "wb"),
            "WORKBUDDY_AI_CONFIG_DIR": str(base / "wbai"),
            "ITERACONNECT_VSCODE_USER_DIR": str(base / "vs-code"),
        }
        with stack() as (config, vendor, _gateway), patch.dict(os.environ, dirs):
            for target in ("visual-studio", "vscode", "workbuddy", "workbuddy-ai"):
                with self.subTest(target=target):
                    status, raw = self.call(
                        "/api/connect",
                        {
                            "provider": "custom",
                            "client": target,
                            "name": "Fixture",
                            "model": MODEL,
                            "protocols": ["chat"],
                            "base_url": config["providers"]["iteracompute"]["endpoints"]["chat"],
                            "api_key": VENDOR_KEY,
                        },
                    )
                    self.assertEqual(status, 200)
                    if target == "visual-studio":
                        guide = json.loads(raw)
                        key, model = guide["local_key"], guide["model"]
                        url = guide["base_url"] + "/chat/completions"
                        request = Request(
                            guide["base_url"] + "/models",
                            headers={"Authorization": "Bearer " + key},
                        )
                        with urlopen(request, timeout=5) as response:
                            self.assertIn(MODEL, [row["id"] for row in json.load(response)["data"]])
                    else:
                        row = json.loads(client_path(target).read_text())[0]
                        if target == "vscode":
                            route = row["models"][0]
                            key = route["requestHeaders"]["Authorization"].removeprefix("Bearer ")
                        else:
                            route, key = row, row["apiKey"]
                        model, url = route["id"], route["url"]
                    result = send(url, key, "chat", payload("chat", model, 256, False), 5)
                    self.assertEqual(result["choices"][0]["message"]["content"], "ITERACONNECT_OK")
                    self.assertTrue(
                        vendor.requests[-1][2]["Authorization"] == "Bearer " + VENDOR_KEY
                    )
                    self.assertEqual(vendor.requests[-1][3]["model"], MODEL)

    def test_one_click_actions_target_the_submitting_tab_and_restore_without_saving_drafts(self):
        folder = Path(self.folder.name)
        with patch.dict(
            os.environ,
            {
                "ITERACONNECT_VSCODE_USER_DIR": str(folder / "Code/User"),
                "CODEX_HOME": str(folder / "Codex"),
            },
        ):
            for client in ("codex", "vscode"):
                status, raw = self.call(
                    "/api/connect",
                    {
                        "provider": "iteracompute",
                        "client": client,
                        "model": "owner/model",
                        "api_key": VENDOR_KEY,
                    },
                )
                self.assertEqual(status, 200)
                self.assertNotIn(VENDOR_KEY.encode(), raw)
                self.assertTrue(client_path(client).exists())
            group = json.loads(client_path("vscode").read_text())[0]
            entry = group["models"][0]
            self.assertEqual(entry["id"], "owner/model")
            self.assertTrue(entry["toolCalling"])
            self.assertFalse(entry["vision"])
            self.assertGreater(entry["maxInputTokens"], entry["maxOutputTokens"])
            self.assertEqual(
                group["models"][0]["url"],
                f"http://127.0.0.1:{self.app.relay.server_port}/p/iteracompute/v1/chat/completions",
            )
            settings = self.app.settings_path.read_bytes()
            self.assertEqual(self.call("/api/disconnect", {"client": "codex"})[0], 200)
            self.assertFalse(client_path("codex").exists())
            self.assertTrue(client_path("vscode").exists())
            self.assertEqual(self.app.settings_path.read_bytes(), settings)

    def test_external_key_file_edits_are_not_overwritten_by_stale_ui(self):
        data = read_settings(self.app.settings_path)
        data["providers"]["iteracompute"]["api_key"] = VENDOR_KEY
        write_settings(self.app.settings_path, data)
        status, raw = self.call("/api/save", {"provider": "iteracompute", "client": "claude"})
        self.assertEqual(status, 400)
        self.assertNotIn(VENDOR_KEY.encode(), raw)
        self.assertEqual(read_settings(self.app.settings_path), data)
        self.assertEqual(self.call("/api/reload", {})[0], 200)
        self.assertEqual(
            self.call("/api/save", {"provider": "iteracompute", "client": "codex"})[0], 200
        )

    def test_connect_and_restore_via_ui_api_without_touching_user_config(self):
        path = Path(self.folder.name) / "client" / "settings.json"
        path.parent.mkdir()
        original = '{"theme":"dark"}\n'
        path.write_text(original)
        self.assertEqual(
            self.call(
                "/api/save", {"provider": "iteracompute", "client": "claude", "api_key": VENDOR_KEY}
            )[0],
            200,
        )
        with patch("iteraconnect.native.client_path", return_value=path):
            status, raw = self.call("/api/connect", {})
            self.assertEqual(status, 200, raw)
            self.assertIn(LOCAL_KEY, path.read_text())
            self.assertNotIn(VENDOR_KEY, path.read_text())
            self.assertEqual(self.call("/api/disconnect", {})[0], 200)
            self.assertEqual(path.read_text(), original)


@unittest.skipUnless(
    os.environ.get("ITERACONNECT_TEST_NATIVE") == "1", "opt-in installed CLI tests"
)
class NativeSettingsClientTests(unittest.TestCase):
    def test_installed_clients_read_the_new_native_configuration(self):
        import shutil

        with stack() as (config, vendor, gateway):
            for target in ("claude", "codex", "openclaw", "hermes"):
                if not shutil.which(target):
                    continue
                with self.subTest(target=target):
                    result = smoke(config, target, "iteracompute", native=True)
                    self.assertEqual(result["status"], "passed", result)
