# IteraCompute Agent Connect

[中文](README.md)

A composable connector for CC Switch and Magpie, with IteraCompute selected by default.
It preserves both upstream applications and adds a provider registry, authenticated loopback
relay, CC Switch import links, Magpie synchronization, native-client launchers and contract tests.
It does not combine the two desktop applications into a new UI.

Requires Python 3.11+. No third-party Python runtime dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
itera-connect init
itera-connect install-magpie
read -rsp 'IteraCompute API key: ' ITERACOMPUTE_API_KEY
export ITERACOMPUTE_API_KEY
itera-connect up --web
```

In another terminal, run `itera-connect connect claude`, `connect codex`, `connect workbuddy`,
`connect openclaw` or `connect hermes`. These commands use Magpie's native config adapters.
`disconnect <agent>` restores the previous configuration. WorkBuddy requires a restart and a
model selection in its task picker. `run claude|codex --via magpie -- <arguments>` offers
process-local settings without editing native config.

The default bases are `https://api.iteracompute.com/v1` for OpenAI protocols and
`https://api.iteracompute.com` for Anthropic Messages. Add other providers with
`provider add <id> --key-env <ENV_NAME> --model <id> --chat <base-url>` and select them with
`provider use <id>`. Restart the relay after editing providers, then run `sync`.

Use `cc-link <agent>` for a CC Switch import. Links carry only a local relay credential.
Use `magpie -- <arguments>` and `cc-switch -- <arguments>` for the upstream applications'
full interfaces, including their additional providers, agents, routing, MCP and skills.
Upstream feature availability is not equivalent to an end-to-end verification of every feature.

Read [coverage](docs/coverage.md), [configuration](docs/configuration.md),
[testing](docs/testing.md) and the [acceptance report](docs/acceptance.md).

MIT licensed. Issues, discussions and pull requests are welcome. Merging to `main` requires
an administrator code-owner approval and passing checks, including for administrators.
