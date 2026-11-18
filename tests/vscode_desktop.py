"""Opt-in VS Code desktop chat acceptance on Linux with Playwright and a virtual display."""

import argparse
import json
import os
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from iteraconnect.diagnostics import PROMPT
from iteraconnect.gateway import Gateway
from iteraconnect.native import connect_native, disconnect_native
from iteraconnect.settings import read_settings, runtime_config
from iteraconnect.smoke import sandbox_env

from .fixtures import TEXT, stack


@contextmanager
def backend(settings):
    if settings is None:
        with stack(chat_only=True) as (config, vendor, _):
            yield config, "iteracompute"
            assert any(r[0] == "POST" and r[1] == "/v1/chat/completions" for r in vendor.requests)
        return
    if not settings.is_file():
        raise ValueError("Supply an existing private test settings file")
    data = read_settings(settings)
    pid = data["selected_provider"]
    if not data["providers"][pid]["api_key"]:
        raise ValueError("A dedicated provider test key is required")
    config = runtime_config(data)
    with Gateway(config, address=("127.0.0.1", 0)) as server:
        config["gateway"]["port"] = server.server_port
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield config, pid
        finally:
            server.shutdown()
            worker.join()


def chat(pw, root, args, model):
    user_data = root / "Code"
    env = sandbox_env(root)
    env.update(DISPLAY=os.environ["DISPLAY"], XAUTHORITY=os.environ.get("XAUTHORITY", ""))
    work = root / "workspace"
    work.mkdir()
    cmd = [
        str(args.electron),
        "--user-data-dir",
        str(user_data),
        "--extensions-dir",
        str(root / "extensions"),
        "--extensionDevelopmentPath=" + str(args.copilot),
        "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=0",
        "--skip-welcome",
        "--skip-release-notes",
        "--disable-gpu",
        str(work),
    ]
    with subprocess.Popen(
        cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
    ) as proc:
        try:
            port_file = user_data / "DevToolsActivePort"
            deadline = time.monotonic() + 30
            while not port_file.is_file() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.15)
            port = int(port_file.read_text().splitlines()[0])
            browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            page = browser.contexts[0].pages[0]
            editor = page.locator(".interactive-input-part .monaco-editor").last
            page.get_by_text(model, exact=True).first.wait_for(state="attached", timeout=60000)
            editor.click(position={"x": 45, "y": 12})
            page.keyboard.type(PROMPT)
            page.keyboard.press("Enter")
            page.locator(".interactive-response").get_by_text(TEXT, exact=True).first.wait_for(
                timeout=90000
            )
            if args.screenshot:
                page.screenshot(path=args.screenshot)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def main():
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--electron", type=Path, default=Path("/usr/share/code/code"))
    parser.add_argument(
        "--copilot", type=Path, default=Path("/usr/share/code/resources/app/extensions/copilot")
    )
    parser.add_argument("--settings", type=Path, help="explicitly use the selected real provider")
    parser.add_argument("--screenshot", type=Path, help="capture a fixture result")
    args = parser.parse_args()
    if args.settings and args.screenshot:
        parser.error("the automated screenshot is for fixture runs")
    with (
        tempfile.TemporaryDirectory(prefix="iteraconnect-vscode-") as directory,
        sync_playwright() as pw,
    ):
        root = Path(directory)
        user = root / "Code/User"
        user.mkdir(parents=True)
        (user / "settings.json").write_text(
            json.dumps(
                {
                    "workbench.startupEditor": "none",
                    "telemetry.telemetryLevel": "off",
                    "update.mode": "none",
                    "security.workspace.trust.enabled": False,
                }
            )
        )
        with (
            patch.dict(
                os.environ,
                ITERACONNECT_VSCODE_USER_DIR=str(user),
                ITERACONNECT_HOME=str(root / "state"),
            ),
            backend(args.settings) as (config, pid),
        ):
            model = config["providers"][pid]["default_model"]
            connect_native("vscode", config, pid, model)
            chat(pw, root, args, model)
            disconnect_native("vscode")
            assert not (user / "chatLanguageModels.json").exists()
    print(
        "VS Code desktop chat and restore passed ·", "real provider" if args.settings else "fixture"
    )


if __name__ == "__main__":
    main()
