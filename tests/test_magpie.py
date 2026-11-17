"""Opt-in tests with the actual pinned Magpie executable, under an isolated HOME."""

import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from iteraconnect.diagnostics import probe
from iteraconnect.integrations import connect, magpie, magpie_providers, sync_magpie
from iteraconnect.network import json_request
from iteraconnect.smoke import sandbox_env, smoke

from .fixtures import LOCAL_KEY, MODEL, VENDOR_KEY, stack


@unittest.skipUnless(
    os.environ.get("ITERACONNECT_TEST_MAGPIE_BIN"),
    "set ITERACONNECT_TEST_MAGPIE_BIN for real Magpie tests",
)
class MagpieTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources = ExitStack()
        cls.addClassCleanup(cls.resources.close)
        binary = os.environ["ITERACONNECT_TEST_MAGPIE_BIN"]
        cls.home = Path(
            cls.resources.enter_context(
                tempfile.TemporaryDirectory(prefix="iteraconnect-magpie-test-")
            )
        )
        cls.config, cls.vendor, _ = cls.resources.enter_context(stack(chat_only=True))
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        env = {
            **sandbox_env(cls.home),
            "ITERACONNECT_HOME": str(cls.home / "connector"),
            "ITERACONNECT_GATEWAY_KEY": LOCAL_KEY,
            "ITERACONNECT_MAGPIE_BIN": binary,
            "FIXTURE_VENDOR_KEY": VENDOR_KEY,
            "MAGPIE_ADDR": f"127.0.0.1:{port}",
            "ITERACONNECT_MAGPIE_URL": f"http://127.0.0.1:{port}",
        }
        cls.resources.enter_context(patch.dict(os.environ, env, clear=True))
        # Seed native config files so detection and preservation are both exercised.
        seeds = {
            ".claude/settings.json": json.dumps(
                {"model": "own-claude", "env": {"KEEP_ME": "yes"}, "theme": "dark"}
            ),
            ".codex/config.toml": '# keep comment\nmodel = "own-codex"\n[history]\npersistence = "none"\n',
            ".workbuddy/models.json": json.dumps(
                [{"id": "own-model", "name": "Mine", "vendor": "mine"}]
            ),
            ".openclaw/openclaw.json": json.dumps(
                {
                    "agents": {"defaults": {"model": {"primary": "mine/old"}}},
                    "messages": {"responsePrefix": "keep"},
                }
            ),
            ".hermes/config.yaml": "model:\n  provider: openrouter\n  default: own-hermes\nui:\n  theme: dark\n",
        }
        for name, content in seeds.items():
            path = cls.home / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        sync_magpie(cls.config)
        cls.log = cls.resources.enter_context(open(cls.home / "magpie.log", "w+"))
        cls.process = subprocess.Popen([binary, "serve"], env=env, stdout=cls.log, stderr=cls.log)
        cls.resources.callback(cls.stop)
        for _ in range(80):
            try:
                json_request(
                    "GET", env["ITERACONNECT_MAGPIE_URL"] + "/v1/models", "magpie-test", timeout=1
                )
                break
            except Exception:
                if cls.process.poll() is not None:
                    raise AssertionError("Magpie failed to start in sandbox")
                time.sleep(0.1)
        else:
            raise AssertionError("Magpie did not become ready")

    @classmethod
    def stop(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait()

    def test_chat_only_source_translates_all_three_protocols(self):
        result = probe(
            self.config,
            "iteracompute",
            MODEL,
            via="magpie",
            protocols=["chat", "responses", "anthropic"],
        )
        self.assertTrue(result["passed"], result)
        self.assertTrue(
            all(
                path.endswith("/chat/completions")
                for method, path, _, _ in self.vendor.requests
                if method == "POST"
            )
        )

    def test_sync_is_idempotent_and_vendor_key_never_reaches_magpie(self):
        sync_magpie(self.config)
        providers = magpie_providers()
        self.assertEqual(list(providers), ["iteraconnect-iteracompute"])
        self.assertEqual(providers["iteraconnect-iteracompute"]["key"], LOCAL_KEY)
        self.assertNotIn(VENDOR_KEY, json.dumps(providers))

    def test_connect_disconnect_five_native_configs(self):
        for target, filename, original in (
            ("claude", ".claude/settings.json", "own-claude"),
            ("codex", ".codex/config.toml", "own-codex"),
            ("workbuddy", ".workbuddy/models.json", "own-model"),
            ("openclaw", ".openclaw/openclaw.json", "mine/old"),
            ("hermes", ".hermes/config.yaml", "own-hermes"),
        ):
            with self.subTest(target=target):
                connect(self.config, target, "iteracompute", MODEL)
                text = (self.home / filename).read_text()
                self.assertIn("magpie", text)
                self.assertNotIn(VENDOR_KEY, text)
                magpie([target, "default"], capture=True)
                text = (self.home / filename).read_text()
                self.assertIn(original, text)
                if target == "claude":
                    self.assertIn("KEEP_ME", text)
                if target == "codex":
                    self.assertIn("keep comment", text)
                if target == "hermes":
                    self.assertIn("theme: dark", text)


@unittest.skipUnless(
    os.environ.get("ITERACONNECT_TEST_NATIVE"), "opt-in actual installed native CLI tests"
)
class NativeClientTests(unittest.TestCase):
    def test_installed_clients_against_fixture(self):
        with stack() as (config, _, _):
            results = [
                smoke(config, target, "iteracompute", MODEL, timeout=45)
                for target in ("claude", "codex", "openclaw")
            ]
            self.assertTrue(
                all(r["status"] in ("passed", "not-installed") for r in results), results
            )
            print(json.dumps({"backend": "local-fixture", "native_clients": results}))
