# Agent Connect

**Choose an API. Choose a client. Connect.**

An original local control panel, native configuration manager and authenticated relay for
Claude Code, Codex, WorkBuddy, WorkBuddy AI, OpenClaw and Hermes. IteraCompute is the default;
other compatible APIs are selectable. No CC Switch or Magpie installation is needed for the
simple workflow. Their optional advanced integrations remain available without copying their
application source.

[中文](README.md) · [Configuration](docs/configuration.md) · [Acceptance](docs/acceptance.md)

![Agent Connect local client](docs/images/client.jpg)

## Start

Requires Python 3.11+ and the client you want to use. The implementation is under administrator
review, so use the feature branch until it is merged:

```bash
git clone --branch feat/agent-connect https://github.com/IteraCompute/agent-connect.git
cd agent-connect
python3 start.py
```

Windows: `py -3 start.py` or double-click `Start.bat`. macOS: `Start.command`.
The browser opens a local panel. No pip install, Node.js or third-party Python runtime is required.

1. Enter your API key. IteraCompute and the verified `openai/gpt-6-luna` model are selected by default.
2. Choose your client and click **连接 Claude Code** (Connect Claude Code), or the selected client’s name. Existing settings are backed up first.
3. Restart your client. WorkBuddy requires selecting `custom-local:iteracompute/model` in its task picker.

Keep the launcher running while using the client. Closing the browser does not stop the service;
press Ctrl+C in the terminal to stop it. The UI currently uses Chinese labels.

## Fill a file instead

The first launch creates `agent-connect.local.toml` beside `start.py`. Fill `api_key = ""`
under `[providers.iteracompute]`, save, then click **重新读取** (Reload configuration).
The complete blank template is [config.example.toml](config.example.toml).
This private file is ignored by Git and written with owner-only permissions on POSIX.
Never publish it after adding credentials. The app uses this file exclusively, not an unrelated
vendor key inherited from your shell. Empty key input in the UI preserves the stored key;
clear it in the file to remove it.

## Providers and protocols

Click **添加 API** (Add API), enter a unique lowercase ID, name, URL and key. Fetch models
before choosing a model, or enter its ID directly. Fetching the catalog does not save the draft
or replace the active relay credentials. New providers start with an empty key; Cancel returns
to the previous provider. Connections, exports and tests automatically save the form.

Choose only the API's supported native protocols in **地址与协议** (URL and protocols).
Claude Code needs Anthropic Messages; Codex needs Responses; WorkBuddy,
OpenClaw and Hermes use Chat Completions. The relay preserves the native protocol. APIs that
need protocol conversion can use the optional [Magpie bridge](docs/advanced.md).

The simple UI independently edits user settings, preserves unrelated fields and records an
exact original backup. Restore refuses to overwrite files changed by another tool afterward.
Standard JSON, Codex TOML and plain Hermes mapping YAML are supported. Complex YAML or JSON5
is rejected without changing the original; advanced upstream adapters cover more formats.
Client environment variables, project settings or organization policies can override user settings.

## Reading the interface

The save badge shows pending changes. Each client card shows installation detection and whether
an original-config backup exists; neither is an inference result. The connection preview shows
the selected API, model and required protocol. A protocol mismatch disables connection/testing
and links to the relevant setting. Checking a protocol does not add support to the API itself.
Client cards support Tab, arrow keys and Home/End. Narrow screens use a stacked layout.

Tests show separate text, streaming and tool-roundtrip cards. Details are collapsed by default;
changing the API, model or client clears stale results. Export includes a copy button for the
local relay configuration. Restore becomes available after a configuration backup exists.

## Verify

**测试 API** checks text, complete SSE and a tool-call/result round trip for the selected
client's protocol: up to four generation requests, each with a 256-token output budget.
**客户端实测** launches an installed Claude Code, Codex, OpenClaw or Hermes in a temporary home with
configuration produced by our native adapter, then verifies the actual assistant reply.
Hermes automation uses the 0.23.1 stream-json CLI. WorkBuddy application execution requires manual acceptance; config success is
not reported as inference success. Tests use the selected API key and may incur usage charges.

![API result cards](docs/images/test-passed.jpg)

The result-card screenshot uses a local simulated backend to demonstrate the UI. Actual
IteraCompute and installed-client evidence is recorded separately in [acceptance](docs/acceptance.md).

See [testing](docs/testing.md), [current results](docs/acceptance.md),
[full advanced coverage](docs/coverage.md) and [contributing](CONTRIBUTING.md).

## Security and development

UI: `127.0.0.1:18424`. Relay: `127.0.0.1:18423`. The UI requires a per-launch control token and
checks Host/Origin. Vendor keys stay in the private file and relay process; clients receive
only the local relay token. Protect that token too. Neither prompts nor raw client logs are recorded.
Use `python3 start.py --port 18434 --relay-port 18433` to change ports, then reconnect clients.

```bash
python -m pip install -e . -r requirements-dev.txt
python -m unittest discover -v
ruff check .
ruff format --check .
python -m build
```

MIT licensed. Issues, discussions and PRs are welcome. Protected `main` requires administrator
CODEOWNER approval and passing checks, including for administrators. Every merge must satisfy
those protections. Organization Actions and initial review ownership still need administrator setup;
see [governance](docs/governance.md). Optional upstream licenses/pins remain recorded.
