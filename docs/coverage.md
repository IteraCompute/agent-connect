# Upstream and downstream coverage

## Independent simple client

`python3 start.py` uses original UI, settings, native adapters and the relay. It needs no upstream
binary. API switching, custom native endpoints, model discovery, connect/restore and API/client
tests are available in one local interface. Six client entries cover Claude Code, Codex,
WorkBuddy, WorkBuddy AI, OpenClaw and Hermes. Config adaptation is separate from actual app
inference verification; see acceptance.md. Protocol conversion, subscription login, upstream
plugins and additional clients remain in the optional advanced interfaces below.

## Optional upstream composition

Composition keeps upstream capabilities available through their own supported interfaces.
It does not claim every upstream feature has been retested against every IteraCompute model.
Source revisions and the Magpie release artifacts are pinned in
[`upstreams.lock.json`](../src/iteraconnect/upstreams.lock.json).

| Layer | Available interface | Scope |
| --- | --- | --- |
| IteraCompute and custom APIs | `provider`, `models`, `serve`, `probe` | Selectable Chat, Responses, Messages and Gemini native bases; environment-only vendor keys |
| Magpie upstreams | `itera-connect magpie -- presets`, Magpie web/TUI | All presets, custom endpoints, local models, remote Magpie, supported sign-ins, subscription providers and community plugins |
| Magpie routing | Magpie web/TUI or CLI pass-through | Groups, fallback, account selection, quota/usage, native plugins, MCP, skills and supported agent settings |
| Magpie downstreams | `connect <agent>` or full upstream CLI | Native adapters, including Claude Code, Codex, WorkBuddy/WorkBuddy AI, OpenClaw, Hermes, Gemini CLI, OpenCode, Pi, Goose, Copilot, Qwen, Kimi, dsh and the other registered agents |
| CC Switch upstreams | `cc-link`, CC Switch desktop | Import Agent Connect as a provider beside every upstream preset/custom provider and official account option |
| CC Switch downstreams | CC Switch desktop, native app settings | Claude Code/Desktop, Codex, Gemini, Grok Build, OpenCode, OpenClaw, Hermes, Pi, MiniMax Code, Kimi, dsh, Antigravity, Oh My Pi, Copilot, WorkBuddy |
| CC Switch extra features | CC Switch desktop | Its native MCP, prompt, skills, workspace, account and local routing features remain available |
| Additional API-compatible clients | local gateway URL/key or Magpie | Use a supported native protocol; no fixed list of clients in the relay |

`connect` accepts arbitrary Magpie agent IDs rather than imposing a smaller allowlist.
Most model-selecting adapters accept the standard model command. Provider-only or other
special adapters should use the full native CLI (`magpie -- <agent> <field> <value>`).
WorkBuddy and WorkBuddy AI are handled explicitly as provider/picker adapters.

CC Switch currently accepts provider deep links for `claude`, `codex`, `gemini`, `agy`,
`grokbuild`, `opencode`, `openclaw`, `hermes` and `pi`. Other desktop entries remain available
through the upstream UI; a missing deep-link adapter is reported explicitly. Unsupported
protocol/client combinations must be routed through Magpie or CC Switch's native routing.

The default IteraCompute profile advertises Chat, Responses and Messages. It does not assume
that IteraCompute serves the native Gemini API. Gemini CLI can use IteraCompute through
Magpie's protocol conversion. Provider-specific beta features, signatures, reasoning budgets,
context limits and tool support still depend on the selected model/API.

Verified source references:

- [Magpie reference](https://github.com/yetone/magpie/blob/187d067241d891b0603358537f7ef8909a7599a7/docs/reference.md)
- [Magpie agent registry](https://github.com/yetone/magpie/blob/187d067241d891b0603358537f7ef8909a7599a7/internal/agent/agents.go)
- [Magpie integration contract](https://usemagpie.ai/docs/integrate)
- [CC Switch app capabilities](https://github.com/farion1231/cc-switch/blob/09acca04941a359096bb16ea4fa4073c5e2c46e5/src/config/appSpecs.ts)
- [CC Switch deep-link contract](https://github.com/farion1231/cc-switch/blob/09acca04941a359096bb16ea4fa4073c5e2c46e5/docs/user-manual/en/5-faq/5.3-deeplink.md)
- [Codex provider configuration](https://developers.openai.com/codex/config-reference/)
- [OpenClaw custom providers](https://docs.openclaw.ai/gateway/config-tools/custom-providers)
- [Hermes custom providers](https://hermes-agent.nousresearch.com/docs/integrations/providers)
