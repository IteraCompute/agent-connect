# Agent Connect development

Scope is this connector repository. Production gateway, website and platform services
belong in their own repositories. Use a feature branch and submit a PR for independent
administrator review.

Run `python scripts/verify.py` before review. [Testing and release](docs/testing.md)
covers setup, the installed-wheel checks, the recovery model and release artifacts.

- Keep credentials in ignored private local TOML or runtime environment references.
  Never print keys, request bodies or arbitrary client logs.
- Preserve upstream MIT notices and pinned source and release provenance.
- Report fixture, configuration adapter and actual provider/client evidence separately.
