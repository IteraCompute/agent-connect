# Security policy

Report vulnerabilities privately using GitHub's **Report a vulnerability** feature on this
repository's Security page. Do not publish API keys or exploit details in public issues.

Agent Connect is an authenticated, loopback-only desktop relay. Provider keys are environment
references and never placed in generated agent configs, Magpie entries or command-line arguments.
Generated import links and native fragments may contain a local relay key: protect them as credentials.
The local key can make requests with the providers available to the relay; rotate it and resync
Magpie/reimport client configs if it is disclosed. Magpie's loopback gateway uses its own documented
local trust model, which should be considered on shared multi-user machines.

Use Magpie's native authenticated/TLS sharing feature for remote clients. Do not expose the relay
port using a public bind or tunnel. A successful protocol conversion does not imply identical
behavior for provider beta features, cache semantics, reasoning or signatures.

The pinned installer verifies published asset sizes and SHA-256 digests before executing anything.
It does not execute remote installer scripts. Keep upstream notices when redistributing binaries.
Supported release line: `0.1.x`.
