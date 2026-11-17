import copy
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from iteraconnect.cli import main
from iteraconnect.config import (
    DEFAULT,
    ConnectError,
    gateway_key,
    load,
    save,
    validate,
    validate_url,
)
from iteraconnect.integrations import cc_link, export_fragment, write_export
from iteraconnect.launch import launch_args

from .fixtures import LOCAL_KEY, MODEL, VENDOR_KEY


class ConfigTests(unittest.TestCase):
    def test_defaults_and_isolation(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "absent"
            a = load(path)
            a["providers"].clear()
            self.assertIn("iteracompute", load(path)["providers"])
            self.assertEqual(load(path)["active_provider"], "iteracompute")

    def test_save_is_private_and_never_contains_key(self):
        with (
            tempfile.TemporaryDirectory() as d,
            patch.dict(os.environ, {"ITERACOMPUTE_API_KEY": VENDOR_KEY}),
        ):
            path = Path(d) / "config.json"
            save(copy.deepcopy(DEFAULT), path)
            self.assertNotIn(VENDOR_KEY, path.read_text())
            self.assertEqual(load(path), DEFAULT)
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_keys_are_created_once(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {"ITERACONNECT_HOME": d}):
            with patch.dict(os.environ):
                os.environ.pop("ITERACONNECT_GATEWAY_KEY", None)
                self.assertEqual(gateway_key(), gateway_key())

    def test_bad_url_rejected(self):
        for url in (
            "ftp://host",
            "https://user:secret@host",
            "https://host?key=a",
            "https://host/#x",
            "https://a/\nb",
        ):
            with self.subTest(url=url), self.assertRaises(ConnectError):
                validate_url(url)

    def test_lan_plain_http_requires_opt_in(self):
        with self.assertRaises(ConnectError):
            validate_url("http://192.168.1.1/v1")
        self.assertEqual(validate_url("http://192.168.1.1/v1", True), "http://192.168.1.1/v1")
        validate_url("http://127.0.0.1:1234/v1")

    def test_inline_credential_and_public_bind_rejected(self):
        for mutate in (
            lambda d: d["providers"]["iteracompute"].update(api_key="bad"),
            lambda d: d["gateway"].update(host="0.0.0.0"),
        ):
            value = copy.deepcopy(DEFAULT)
            mutate(value)
            with self.assertRaises(ConnectError):
                validate(value)

    def test_malformed_config_error_is_safe(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "config.json"
            path.write_text('{"secret":"' + VENDOR_KEY)
            with self.assertRaises(ConnectError) as e:
                load(path)
            self.assertNotIn(VENDOR_KEY, str(e.exception))


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ, {"ITERACONNECT_GATEWAY_KEY": LOCAL_KEY, "ITERACOMPUTE_API_KEY": VENDOR_KEY}
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_cc_link_is_per_app_and_has_no_vendor_key(self):
        for target, fmt, suffix in (
            ("claude", "anthropic", ""),
            ("codex", "openai_responses", "/v1"),
            ("hermes", "openai_chat", "/v1"),
            ("openclaw", "openai_chat", "/v1"),
        ):
            link = cc_link(DEFAULT, target, "iteracompute", MODEL)
            q = parse_qs(urlsplit(link).query)
            self.assertEqual(q["apiFormat"], [fmt])
            self.assertTrue(q["endpoint"][0].endswith("/p/iteracompute" + suffix))
            self.assertEqual(q["enabled"], ["false"])
            self.assertNotIn(VENDOR_KEY, link)

    def test_unsupported_cc_app_fails(self):
        with self.assertRaises(ConnectError):
            cc_link(DEFAULT, "workbuddy", "iteracompute")

    def test_chat_only_requires_magpie_for_codex(self):
        config = copy.deepcopy(DEFAULT)
        config["providers"]["iteracompute"]["endpoints"] = {"chat": "https://example.test/v1"}
        with self.assertRaises(ConnectError):
            cc_link(config, "codex", "iteracompute")
        q = parse_qs(urlsplit(cc_link(config, "codex", "iteracompute", via="magpie")).query)
        self.assertEqual(q["model"], ["iteraconnect-iteracompute/Auto"])

    def test_native_exports_and_no_overwrite(self):
        for target in ("claude", "codex", "workbuddy", "workbuddy-ai", "openclaw", "hermes"):
            self.assertNotIn(VENDOR_KEY, export_fragment(DEFAULT, target, "iteracompute"))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "fragment.json"
            write_export(DEFAULT, "claude", "iteracompute", path)
            with self.assertRaises(ConnectError):
                write_export(DEFAULT, "claude", "iteracompute", path)

    def test_native_launch_keys_only_in_environment(self):
        for target in ("claude", "codex"):
            command, env = launch_args(DEFAULT, target, "iteracompute", via="direct")
            self.assertNotIn(VENDOR_KEY, json.dumps(command))
            self.assertIn(VENDOR_KEY, env.values())
            if target == "codex":
                self.assertIn('model_providers.iteraconnect.wire_api="responses"', command)

    def test_managed_harnesses_do_not_inherit_vendor_credentials(self):
        for target in ("claude", "codex"):
            _, env = launch_args(DEFAULT, target, "iteracompute", via="gateway")
            self.assertNotIn("ITERACOMPUTE_API_KEY", env)
            self.assertNotIn(VENDOR_KEY, env.values())

    def test_cc_import_formats_follow_native_client_contracts(self):
        for target, fmt in (
            ("gemini", "anthropic"),
            ("agy", "openai_chat"),
            ("hermes", "gemini_native"),
        ):
            with self.assertRaises(ConnectError):
                cc_link(DEFAULT, target, "iteracompute", api_format=fmt, via="magpie")
        link = cc_link(DEFAULT, "gemini", "iteracompute", via="magpie")
        self.assertEqual(parse_qs(urlsplit(link).query)["endpoint"], ["http://127.0.0.1:3425"])
        link = cc_link(DEFAULT, "opencode", "iteracompute", api_format="anthropic")
        self.assertTrue(parse_qs(urlsplit(link).query)["endpoint"][0].endswith("/v1"))

    def test_cli_custom_provider_preserves_default(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "config.json"
            self.assertEqual(
                main(
                    [
                        "--config",
                        str(path),
                        "provider",
                        "add",
                        "other",
                        "--key-env",
                        "OTHER_KEY",
                        "--model",
                        MODEL,
                        "--chat",
                        "https://example.test/v1",
                    ]
                ),
                0,
            )
            self.assertIn("iteracompute", load(path)["providers"])
            self.assertEqual(load(path)["providers"]["other"]["key_env"], "OTHER_KEY")
