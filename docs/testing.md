# Testing and acceptance

Tests deliberately distinguish three kinds of evidence:

1. **Contract tests with a simulated vendor**: requests, auth substitution, provider selection,
   text, SSE completion, tool results, failures, truncation, private exports and configuration preservation.
2. **Actual installed programs with a simulated vendor**: pinned Magpie translation and native
   adapter restoration, plus Claude Code, Codex and OpenClaw single-turn runs in temporary homes.
3. **Actual provider/model/client tests**: require an explicitly supplied test key. Fixture success
   is not evidence that the remote API, model permissions, budget, tool semantics or every client works.

## Repeatable local and CI tests

```bash
python -m pip install -e . -r requirements-dev.txt
python -m unittest discover -v
ruff check .
ruff format --check .
python -m build
```

For the actual Magpie engine, install the pinned binary, then set
`ITERACONNECT_TEST_MAGPIE_BIN` to its absolute path:

```bash
itera-connect install-magpie
ITERACONNECT_TEST_MAGPIE_BIN=/absolute/path/to/magpie python -m unittest tests.test_magpie.MagpieTests -v
ITERACONNECT_TEST_NATIVE=1 python -m unittest tests.test_magpie.NativeClientTests -v
```

No model key is needed for these tests. The opt-in native suite uses existing executables,
temporary HOME/XDG/config directories, a synthetic key and a local fixture vendor. No existing
user credentials or installed skills are copied. OpenClaw channel delivery is never enabled.
Only clients actually installed are executed. An unavailable program is reported as unavailable.
Magpie tests verify connection and restoration of Claude Code, Codex, WorkBuddy, OpenClaw and Hermes
configs; WorkBuddy/Hermes application execution is separate evidence.

## Test-key acceptance

Use a dedicated developer key. Supply it to the gateway process environment using the private
input in the README. No keys belong in issues, PRs, screenshots or committed files. Runtime
reports under `reports/` and `.env` files are ignored. The relay's process must receive the key;
setting it only in a second terminal cannot update a running relay's environment.

Start `itera-connect up --web`, then use the exact authorized model ID from `models`:

```bash
itera-connect models
itera-connect probe --model Auto --via gateway --out reports/gateway.json
itera-connect probe --model Auto --via magpie --protocol chat --protocol responses --protocol anthropic --out reports/magpie.json
itera-connect smoke claude codex openclaw --model Auto --via magpie --out reports/clients.json
```

Each full probe makes four requests per protocol: one text response, one SSE response, and two
requests for a tool call/result round trip. The default output budget is 256 tokens per request;
`--budget` adjusts it (32–8192). Reasoning models may need more. Default protocol selection tests
the three conversational protocols advertised by the provider. Pass all three `--protocol`
arguments explicitly to test conversion from a Chat-only source through Magpie.

The probe never executes arbitrary model tools; its sole tool returns a fixed code. It checks
the tool name/arguments and preserves full assistant output, including Messages thinking and
signature blocks, in the follow-up request. SSE tests require output and a protocol terminal
event and reject errors, incomplete responses and truncated streams.

`smoke` tests an installed client's actual process, using a temporary config/home and safe
single-turn prompt. It reports `passed`, `failed`, `not-installed` or `manual-required`.
Skipped/manual clients do not make the aggregate CLI command successful. It suppresses arbitrary
client output in saved reports, which can otherwise contain private context or credentials.

## WorkBuddy, Hermes and CC Switch UI acceptance

For WorkBuddy, run `connect workbuddy`, restart the app, start a new task, select the model under
`iteraconnect-iteracompute`, and ask for the fixed reply. Then use a disposable workspace and ask
it to create/read a small text file to exercise its real tool loop. Record app version, model,
result and a redacted screenshot. Repeat with WorkBuddy AI if supporting the international build.

For Hermes, install its CLI, run `connect hermes`, start a fresh session, select the connected
provider and ask for the reply and a disposable-file tool round trip. Disconnect and confirm its
previous provider returns. The initial release does not automate Hermes invocation because CLI
and profile behavior varies by installed version; it verifies the pinned Magpie config adapter.

For CC Switch, open each generated import link in the desktop app, confirm the endpoint and
protocol, import, switch to the provider, then execute the relevant native client. WorkBuddy
provider links are unsupported upstream and must use Magpie's adapter or the native CC Switch UI.
Do not report a generated link alone as a completed desktop integration test.

For each real client, also verify a tool call/result loop, streaming, a permission or bad-key
failure, and disconnect/restore behavior. The automated single-turn native smoke is only the
first part of acceptance; the API tool round-trip is not a substitute for each client's tool loop.
