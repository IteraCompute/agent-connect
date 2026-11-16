# Advanced CLI, Magpie and CC Switch

The default client is `python3 start.py`. It owns an original local UI, private TOML settings,
native configuration editors and loopback relay. None of those require upstream software.

The advanced CLI keeps the composition interfaces for protocol conversion, subscription
providers, additional harnesses and upstream features. It uses a **separate configuration** from
the simple app: JSON provider profiles with environment key references. Switching an agent with
both managers simultaneously is unsupported. Stop one manager and restore its configuration first.

## Optional Magpie bridge

```bash
python -m pip install .
itera-connect init
itera-connect install-magpie
# Set ITERACOMPUTE_API_KEY securely in this terminal, then:
itera-connect up --web
```

This starts Magpie's own UI and the relay. It does not read `agent-connect.local.toml`.
Magpie is downloaded from its official release at a pinned version and verified by SHA-256.
Its independent process supplies cross-protocol conversion; its source is not copied into this package.

In another terminal:

```bash
itera-connect connect claude
itera-connect connect codex
itera-connect connect workbuddy
itera-connect connect openclaw
itera-connect connect hermes
itera-connect disconnect claude
itera-connect run codex --via magpie -- exec --skip-git-repo-check 'Reply only OK'
```

`connect`/`disconnect` in this advanced CLI intentionally use Magpie's native adapters. The simple
UI uses Agent Connect's independent editors. Magpie-backed WorkBuddy model IDs start with
`iteraconnect-iteracompute/`; simple-UI WorkBuddy model IDs start with `iteracompute/`.

Add another API with protocol-specific bases:

```bash
itera-connect provider add my-api --name 'My API' --key-env MY_API_KEY \
  --model my-model --chat https://example.com/v1
itera-connect provider use my-api
# Set MY_API_KEY, restart up, then connect the chosen client.
```

Only declare protocols the API supports. When it only serves Chat, Magpie can translate for
Codex or Claude Code. `run --via gateway` uses native protocols; `--via direct` accesses the
provider without the local relay. Vendor keys stay in process environments and are not put in argv.

All Magpie native options remain available through pass-through:

```bash
itera-connect magpie -- presets
itera-connect magpie -- ls
itera-connect magpie -- tui
```

Suppliers added inside Magpie follow its own credential/storage rules and access their APIs
directly. Subscription sign-ins, plugins, routing, fallback, MCP and skills are upstream features;
availability is not a claim that every combination has been acceptance tested here.

## Optional CC Switch import

Install CC Switch from its [official release](https://github.com/farion1231/cc-switch/releases).
Generate a native import link and open it in the installed application:

```bash
itera-connect cc-link claude
itera-connect cc-link codex --via magpie
itera-connect cc-link openclaw
itera-connect cc-link hermes
itera-connect cc-switch
```

Links contain a local gateway credential, not the vendor key. Imports are not switched on
automatically. Per-app protocol restrictions and the full capability matrix are documented in
[coverage.md](coverage.md). WorkBuddy provider deep links are not supported by this upstream
contract; use the independent simple-UI adapter or Magpie's adapter.

## Advanced acceptance commands

These commands use the advanced JSON/environment configuration and a running relay/bridge:

```bash
itera-connect doctor
itera-connect probe --via gateway --out reports/gateway.json
itera-connect probe --via magpie --protocol chat --protocol responses --protocol anthropic
itera-connect smoke claude codex openclaw --via magpie --out reports/clients.json
```

See [testing.md](testing.md) for exact test scope and [configuration.md](configuration.md) for paths.
