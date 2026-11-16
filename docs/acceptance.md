# Initial acceptance record

Date: **2026-11-16 (Asia/Shanghai)**. Release candidate: **0.1.0**.

This record is for the initial implementation PR. A dedicated IteraCompute test key has not
yet been supplied for this acceptance run. No paid model inference was performed.

| Check | Result | Evidence / limits |
| --- | --- | --- |
| Full local suite | Passed, 34 tests | All optional Magpie and installed native CLI tests enabled; no skipped tests in this local run |
| Native relay protocols | Passed against fixture | Chat, Responses and Messages text, full SSE and tool-call/result round trips |
| Chat-only source via actual Magpie | Passed against fixture | All 9 text/stream/tool contract cases across Chat, Responses and Messages |
| Native config connection/restoration | Passed | Actual Magpie adapters for Claude Code, Codex, WorkBuddy, OpenClaw and Hermes; unrelated settings preserved |
| Claude Code 2.1.312 | Passed against fixture | Actual CLI, temporary HOME, final reply exactly `ITERACONNECT_OK` |
| Codex CLI 0.156.1 | Passed against fixture | Actual CLI, temporary HOME, completed turn with an actual assistant reply |
| OpenClaw 2026.10.2 | Passed against fixture | Actual CLI, temporary HOME, reply payload contains the expected reply; channel delivery disabled |
| CC Switch imports | Contract validated | Per-app URLs, protocol restrictions, opt-in switching, no vendor key in links; desktop click/import test pending |
| WorkBuddy app inference | Pending | Config adapter verified; app restart, task-picker selection and real tool loop still require application acceptance |
| Hermes app inference | Pending | Config adapter verified; Hermes executable is not installed in this test environment |
| Real IteraCompute inference | Pending dedicated test key | Text, streaming, tool round trips, permissions and each real client must be run with the supplied key |
| Python formatting/static checks | Passed | Ruff check and format |
| Python artifacts | Passed | sdist/wheel built; clean wheel installation, CLI and pinned resources verified |
| GitHub governance | Passed | Public repo, Issues/Discussions enabled; protected main requires administrator CODEOWNER review, CI and resolved conversations |

Pinned Magpie engine: **v0.1.4314**, Linux x64 SHA-256
`b1d88d7afd5e211d8992273e906455c11ea84cac31e764d47af20ac4d0a25339`.
Upstream source commits and platform binaries are recorded in the lock file.

Local command:

```bash
ITERACONNECT_TEST_MAGPIE_BIN=/absolute/path/to/verified/magpie \
ITERACONNECT_TEST_NATIVE=1 python -m unittest discover -v
```

Fixture validation established handling of Claude Code's native `beta=true` transport query,
Codex's pre-existing config-directory requirement, Gemini's `alt=sse` transport, stream
termination checks, vendor/local credential separation, and checksum failure preserving an
existing binary. Native smoke success requires an actual assistant reply, not a prompt echoed
in logs. API tool round trips do not stand in for each native client's real tool-execution loop.

GitHub CI additionally runs the fixture suite on Linux/macOS/Windows with Python 3.11 and 3.14,
builds the package, and downloads/verifies the pinned Magpie for the real-engine fixture tests.
Its current results are shown on the PR; local Linux evidence alone does not establish the other
operating systems' result. Follow [testing.md](testing.md) for the remaining test-key acceptance.
