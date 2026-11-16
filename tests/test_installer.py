import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from iteraconnect.config import ConnectError
from iteraconnect.integrations import install_magpie


class InstallerTests(unittest.TestCase):
    def attempt(self, home, received, expected=b"verified fixture executable"):
        lock = {
            "magpie": {
                "assets": {
                    "magpie-cli-linux-amd64": {
                        "url": "https://example.test/fixture",
                        "size": len(expected),
                        "sha256": hashlib.sha256(expected).hexdigest(),
                    }
                }
            }
        }
        with (
            patch.dict(os.environ, {"ITERACONNECT_HOME": home}),
            patch("iteraconnect.integrations.platform.system", return_value="Linux"),
            patch("iteraconnect.integrations.platform.machine", return_value="x86_64"),
            patch("iteraconnect.integrations.lock_data", return_value=lock),
            patch(
                "iteraconnect.integrations.urllib.request.urlopen",
                return_value=io.BytesIO(received),
            ),
        ):
            return install_magpie()

    def test_verified_bytes_are_installed_with_notices(self):
        with tempfile.TemporaryDirectory() as home:
            expected = b"verified fixture executable"
            path = self.attempt(home, expected)
            self.assertEqual(path.read_bytes(), expected)
            self.assertIn("MIT License", (path.parent / "THIRD_PARTY_NOTICES").read_text())

    def test_checksum_or_size_mismatch_preserves_existing_binary(self):
        for received in (b"bad executable", b"x" * 100):
            with self.subTest(received=received), tempfile.TemporaryDirectory() as home:
                path = Path(home) / "bin/magpie"
                path.parent.mkdir()
                path.write_bytes(b"previous binary")
                with self.assertRaises(ConnectError):
                    self.attempt(home, received)
                self.assertEqual(path.read_bytes(), b"previous binary")
                self.assertEqual(list(path.parent.glob(".magpie-*")), [])
