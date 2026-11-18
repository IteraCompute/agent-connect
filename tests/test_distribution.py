"""Contracts for the installed Python distribution and its dependency-free runtime."""

import ast
import json
import sys
import unittest
from importlib.metadata import distribution
from pathlib import Path

import iteraconnect


class DistributionTests(unittest.TestCase):
    def test_metadata_and_upstream_resources(self):
        package = distribution("iteracompute-agent-connect")
        self.assertEqual(package.version, iteraconnect.__version__)
        self.assertFalse(package.requires)
        root = Path(iteraconnect.__file__).parent
        pins = json.loads((root / "upstreams.lock.json").read_bytes())
        self.assertTrue(pins["magpie"]["assets"])
        notices = (root / "upstream-notices.txt").read_text(encoding="utf-8")
        self.assertIn("MIT License", notices)
        self.assertTrue(package.read_text("licenses/LICENSE"))
        self.assertEqual(package.read_text("licenses/THIRD_PARTY_NOTICES"), notices)

    def test_runtime_imports_only_stdlib_and_its_own_package(self):
        root = Path(iteraconnect.__file__).parent
        allowed = sys.stdlib_module_names | {"iteraconnect"}
        for path in root.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_bytes())):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    with self.subTest(module=path.relative_to(root), line=node.lineno, name=name):
                        self.assertIn(name.partition(".")[0], allowed)
