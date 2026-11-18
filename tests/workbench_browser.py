"""Run the packaged workbench in Chromium against a localhost fixture vendor."""

import argparse
import copy
import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from iteraconnect.app import App
from iteraconnect.native import client_path
from iteraconnect.settings import APP_DEFAULT, CLIENTS, write_settings
from iteraconnect.smoke import sandbox_env

from .fixtures import LOCAL_KEY, MODEL, VENDOR_KEY, stack


def exercise(page, app, screenshot):
    from playwright.sync_api import expect

    page.goto(app.origin + "/#" + app.token)
    expect(page.get_by_role("radio")).to_have_count(len(CLIENTS))
    for target, client in CLIENTS.items():
        page.get_by_role("radio", name=client.name, exact=True).click()
        page.locator("#connect").click()
        if client.guided:
            expect(page.locator("#setup-guide")).to_be_visible()
            expect(page.locator("#guide-model")).to_have_value(MODEL)
            assert page.locator("#guide-local_key").input_value() == LOCAL_KEY
            expect(page.locator("#guide-local_key")).to_have_attribute("type", "password")
            page.get_by_role("button", name="复制端点地址").click()
            expect(page.get_by_role("button", name="复制端点地址")).to_have_text("已复制")
            assert (
                page.evaluate("navigator.clipboard.readText()")
                == page.locator("#guide-base_url").input_value()
            )
            expect(page.locator("#native-actions")).to_be_hidden()
        else:
            expect(page.locator("#result-title")).to_have_text("客户端已配置")
            path = client_path(target)
            assert path.exists() and VENDOR_KEY not in path.read_text()
            page.locator("#disconnect").click()
            expect(page.locator("#result-title")).to_have_text("已恢复原配置")
            assert not path.exists()
        if client.manual_test:
            page.locator("#smoke").click()
            expect(page.locator("#result-title")).to_have_text("需要在客户端继续操作")
            expect(page.locator("#result-message")).to_contain_text("ITERACONNECT_OK")
        print(target, "workbench flow passed", flush=True)

    page.locator('[data-id="visual-studio"]').click()
    page.locator("#connect").click()
    expect(page.locator("#setup-guide")).to_be_visible()
    page.locator('[data-id="vscode"]').click()
    expect(page.locator("#guide-fields input")).to_have_count(0)
    expect(page.locator("#required-protocol")).to_have_text("Responses")
    page.locator("#advanced").evaluate("(item) => item.open = true")
    page.locator('[name="protocol"][value="responses"]').uncheck()
    expect(page.locator("#required-protocol")).to_have_text("Chat Completions")
    page.locator("#probe").click()
    expect(page.locator("#result-title")).to_have_text("API 测试通过")
    expect(page.locator(".result-card")).to_have_count(3)
    page.locator('[data-id="vscode"]').press("Home")
    expect(page.locator('[data-id="claude"]')).to_have_attribute("aria-checked", "true")
    page.locator("#advanced").evaluate("(item) => item.open = true")
    page.locator('[name="protocol"][value="anthropic"]').uncheck()
    expect(page.locator("#connect")).to_be_disabled()
    page.locator('[name="protocol"][value="anthropic"]').check()
    page.locator("#advanced").evaluate("(item) => item.open = false")
    page.reload()
    expect(page.locator("#clients button")).to_have_count(len(CLIENTS))
    page.locator('[data-id="workbuddy"]').click()
    if screenshot:
        page.mouse.move(0, 0)
        page.emulate_media(reduced_motion="reduce")
        page.screenshot(path=screenshot, full_page=True, animations="disabled")
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator('[data-id="visual-studio"]').click()
    page.locator("#connect").click()
    expect(page.locator("#setup-guide")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    print("protocol validation, fixture probe, keyboard selection and 390px guide passed")


def main():
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", type=Path, help="save the desktop fixture workbench")
    args = parser.parse_args()
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as directory:
        browser = pw.chromium.launch()
        home = Path(directory)
        env = sandbox_env(home)
        env.update(
            ITERACONNECT_HOME=str(home / "state"),
            ITERACONNECT_VSCODE_USER_DIR=str(home / "Code/User"),
            WORKBUDDY_CONFIG_DIR=str(home / ".workbuddy"),
            WORKBUDDY_AI_CONFIG_DIR=str(home / ".workbuddy-ai"),
        )
        with patch.dict(os.environ, env), stack() as (config, _, _relay):
            data = copy.deepcopy(APP_DEFAULT)
            data["providers"]["iteracompute"].update(
                api_key=VENDOR_KEY,
                model=MODEL,
                base_url=config["providers"]["iteracompute"]["endpoints"]["anthropic"],
            )
            settings = home / "agent-connect.local.toml"
            write_settings(settings, data)
            with App(settings, port=0, relay_port=0) as app, app.relay:
                for server in (app, app.relay):
                    threading.Thread(target=server.serve_forever, daemon=True).start()
                try:
                    context = browser.new_context(viewport={"width": 1360, "height": 960})
                    context.grant_permissions(
                        ["clipboard-read", "clipboard-write"], origin=app.origin
                    )
                    exercise(context.new_page(), app, args.screenshot)
                finally:
                    app.shutdown()
                    app.relay.shutdown()
                    browser.close()


if __name__ == "__main__":
    main()
