# Governance setup and initial blockers

The repository is public, permits forks and community pull requests (`pull_request_creation_policy=all`),
and enables Issues, Discussions and private vulnerability reporting. No interaction restriction is
configured at repository level. Current repository administrators are `K-3-LT` and `aikevan`.

`main` currently enforces:

- At least one approving review and a CODEOWNER review.
- Dismissal of stale approvals and approval by someone other than the latest reviewable pusher.
- The `checks` CI status against the current base, and resolved review conversations.
- Enforcement for administrators, no force pushes, no branch deletion, no automatic merge.

## Organization Actions policy

Rechecked on 2026-11-17, `GET /repos/IteraCompute/agent-connect/actions/permissions` reported
`enabled=false`. Repository-level enablement returned **409: GitHub Actions is disabled on this
repository by the organization**. The local GitHub CLI has repository administration access but
not the organization-settings OAuth scope. The in-app browser reaches GitHub's sign-in page.

An organization owner must allow Actions for **this repository** at
[IteraCompute organization Actions settings](https://github.com/organizations/IteraCompute/settings/actions).
Do not enable unrelated repositories as a workaround. After this is allowed, enable this repo's
Actions, keep default workflow tokens read-only and disable workflow approval of PRs. Push a new
commit or reopen the PR to trigger the configured workflow. The current implementation has not
run in GitHub CI; the required CI check is retained rather than bypassed.

## First CODEOWNER review

The initial protected `main` bootstrap lists `K-3-LT` as the sole CODEOWNER. The implementation
PR is also authored by that account because the connected secondary GitHub account lacks
collaboration access. GitHub uses the **base branch's** CODEOWNERS and does not allow a PR author
to approve their own PR. Adding `aikevan` only in the PR does not change the base branch's rule.

The PR proposes both existing repository administrators as CODEOWNERS. An existing administrator
must review and authorize the first ownership setup; it cannot be silently applied by bypassing
the required review. Real-key acceptance has completed for the API and four installed CLIs (see [acceptance](acceptance.md)).
The implementation PR is ready for independent review; the first ownership setup and organization
Actions policy still block merge. No new administrator access has been granted.

After setup, run `python scripts/check_governance.py` under a repository administrator account.
The audit returns nonzero while Actions or base-branch ownership is still pending.

References:

- [GitHub code owners and base branches](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [GitHub required reviews and author self-approval](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/reviewing-proposed-changes-in-a-pull-request)
