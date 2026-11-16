# Agent Connect development

This repository is independent of IteraCompute/LLMProxy. Do not change production gateway,
website or platform services as part of connector development.

- Python source is in `src/iteraconnect`; the runtime uses the standard library only.
- Use `python -m unittest discover -v`, Ruff check/format and `python -m build`.
- Optional real Magpie/native fixture tests are documented in `docs/testing.md`.
- The simple app stores keys only in ignored private local TOML; runtime provider profiles use environment references. Never print keys, request bodies or arbitrary client logs.
- Distinguish fixture tests, config adapter checks and actual provider/client acceptance.
- Preserve upstream MIT notices and pinned source/release provenance.
- Work on a feature branch and open a PR. Do not merge or bypass administrator review.
