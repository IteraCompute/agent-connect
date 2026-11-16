# Configuration

`itera-connect init` creates `$ITERACONNECT_HOME/config.json`, or
`${XDG_CONFIG_HOME:-~/.config}/iteraconnect/config.json` by default. Files are replaced
atomically with owner-only permissions on POSIX. Windows users should restrict the containing
folder's ACL to their account. Native app backups remain managed by Magpie/CC Switch.

```json
{
  "schema_version": 1,
  "active_provider": "iteracompute",
  "gateway": {"host": "127.0.0.1", "port": 18423, "timeout": 180},
  "providers": {
    "iteracompute": {
      "name": "IteraCompute",
      "key_env": "ITERACOMPUTE_API_KEY",
      "default_model": "Auto",
      "endpoints": {
        "chat": "https://api.iteracompute.com/v1",
        "responses": "https://api.iteracompute.com/v1",
        "anthropic": "https://api.iteracompute.com"
      }
    }
  }
}
```

An absent file uses these defaults in memory. An invalid existing file fails closed.
Inline provider secrets are rejected. `--config /path/config.json` selects a different file;
`ITERACONNECT_HOME` still selects its local key and installed binary directory.
The gateway reads config and environment at startup: restart it after changes.

| Endpoint key | Base convention | Native inference route |
| --- | --- | --- |
| `chat` | e.g. `https://relay.example/v1` | `/chat/completions` |
| `responses` | e.g. `https://relay.example/v1` | `/responses` |
| `anthropic` | e.g. `https://relay.example` | `/v1/messages`, `/v1/messages/count_tokens` |
| `gemini` | e.g. `https://relay.example/v1beta` | `/models/{model}:generateContent`, `:streamGenerateContent` |

Keep custom path prefixes in the base. Credentials, query strings and fragments are refused
in configured base URLs. HTTPS is required except on loopback; `provider add --allow-http`
explicitly allows a trusted LAN server. Declare only protocols the provider serves natively.
Magpie performs translation when the native client speaks a different protocol.

Provider IDs use lower-case letters, digits and hyphens. Model IDs can contain `/` and are
preserved. Root gateway requests may select `provider-id/model-id`. Explicit
`/p/provider-id/v1/...` routes accept the provider's exact model ID, avoiding namespace ambiguity.
`GET /v1/models` returns provider-prefixed IDs; per-provider catalogs preserve the original IDs.
Catalog failures are reported explicitly, without inventing a replacement catalog.

All inference and catalog routes require the local `gateway.key`, or an explicit
`ITERACONNECT_GATEWAY_KEY` (24+ printable characters). `/health` returns only name/version.
Never share the local key or generated CC Switch links. The relay replaces client credentials
with the selected provider's environment key and does not forward cookies or arbitrary headers.
It never retries a POST, follows an upstream redirect, or writes request/response content to logs.
HTTP upstream error bodies are replaced by generic status messages. Successful SSE content is
relayed as received, including in-stream provider error events; probe reports do not record it.

Requests are limited to 16 MiB JSON and 64 concurrent inference calls. The relay supports the
three agent protocols, Gemini content endpoints, Chat-style embeddings/rerank/image generation.
It does not implement arbitrary vendor administration APIs, WebSocket Responses, multipart
uploads or persisted Response retrieval. Magpie's own native-provider/plugin interfaces remain
available for APIs outside this relay's scope. HTTP proxy environment variables are not used
by the relay transport; configure a reachable provider endpoint or use Magpie's native proxy settings.

## Magpie and CC Switch

`sync` creates `iteraconnect-<provider-id>` entries in Magpie. These entries point to per-provider
relay URLs and hold only its local key. They expose exactly the provider's advertised native
protocols, letting Magpie translate correctly. Models are discovered on sync; run sync again
when the provider catalog changes. Existing unrelated Magpie providers are preserved. Changing
the relay port requires removing the old Agent Connect provider from Magpie before syncing,
so the collision guard cannot silently take over an existing endpoint.

`ITERACONNECT_MAGPIE_BIN` selects an existing binary, otherwise the checksum-verified local
installation is preferred, followed by `PATH`. `ITERACONNECT_MAGPIE_URL` overrides the default
client gateway `http://127.0.0.1:3425`; when changing Magpie's port, use the corresponding
`MAGPIE_ADDR` too. Agent Connect's generated Magpie client keys assume a loopback gateway;
remote Magpie deployments need their native gateway-key configuration instead.

The pinned installer writes only to the Agent Connect bin folder. It does not install a service
or replace a system Magpie. Pass-through commands disable Magpie usage telemetry with its
documented opt-out environment variables. Other upstream network behavior follows Magpie's settings.

`export <client> --out <new-file>` writes a private standalone fragment for manual merging.
It refuses to overwrite files. Claude and WorkBuddy fragments hold only the local relay key.
Codex/OpenClaw fragments reference `ITERACONNECT_GATEWAY_KEY`: export the contents of the local
`gateway.key` in the client process first, or use `run`/`connect` to supply it automatically.
Exports are optional; the preferred path is Magpie's native adapter, which preserves comments,
unrelated settings, profile behavior, model metadata and restoration state.
