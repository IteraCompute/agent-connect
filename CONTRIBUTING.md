# Contributing

Issues, Discussions and pull requests are welcome. Include a minimal reproduction, versions,
protocol and model ID. Redact keys, prompts and private paths before sharing logs.

Develop in a branch and run the checks in [testing.md](docs/testing.md). New behavior should
include an appropriate contract test; fixture evidence and real service evidence must remain
separate. Change upstream pins deliberately, retain licenses and verify release digests.

`main` is protected. Merging requires a repository administrator named in `.github/CODEOWNERS`,
at least one approval, approval of the latest reviewable push, resolution of review conversations
and the `checks` CI status. Stale reviews are dismissed. Administrators are subject to these rules.
Force pushes and deletion of `main` are disabled. CI runs untrusted contributions with read-only
repository access and no provider secrets. Automated merge is disabled.

The repository administrators are `@K-3-LT` and `@aikevan`; both are proposed as CODEOWNERS in
the initial implementation PR. Additional administrators can be added to CODEOWNERS
through the same reviewed workflow; reviewers must have write access for GitHub to recognize
their code-owner approval. Authors cannot approve their own pull requests. Normal contributions need a separate
administrator/reviewer account; administrator identity does not count as independent self-review.

Organization Actions is enabled for this repository, with read-only default workflow tokens and
no workflow review approval. See [governance setup](docs/governance.md) for the initial base-branch
ownership dependency and the current first-merge status. Initial setup exceptions require explicit
Owner approval, preserve required CI and must not become a permanent community-review bypass.
