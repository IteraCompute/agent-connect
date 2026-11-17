# Repository governance and first-merge record

[中文说明](#中文说明) · [English](#english)

## 中文说明

### 已确认的权限与 Actions 修复

2026-11-17 核查：`K-3-LT` 既是 `agent-connect` 的仓库管理员，也是 IteraCompute 的组织 Owner。
组织角色与工具令牌的权限范围是两回事：当前 GitHub CLI 的令牌包含 `repo`、`workflow` 和 `read:org`，但没有组织 Actions 管理 API 所需的 `admin:org`。
此前组织 API 返回 403，仓库启用 API 返回“组织禁用”的 409；这些结果不表示账号不是管理员。

组织 Owner 登录 GitHub 网页后，已完成以下修复：

- 组织 Actions 从 Disabled 改为 **Selected repositories**，仅选择 `agent-connect`。
- 仓库 API 已确认 `enabled=true`，其余仓库没有因此获得 Actions 执行权限。
- 工作流默认权限仍为 **read**，不允许 Actions 创建或批准 PR；现有 CI 不使用供应商密钥。
- 未扩大本机 CLI 令牌的组织权限范围。更改由已登录 Owner 的网页会话完成。

页面：[组织 Actions 设置](https://github.com/organizations/IteraCompute/settings/actions)。
权限范围说明见 [GitHub Actions permissions API](https://docs.github.com/en/rest/actions/permissions#get-github-actions-permissions-for-an-organization)。

### 首次合并与当前审核规则

`main` 的保护规则明确包含 `enforce_admins=true`，所以管理员也要满足：

1. 至少一名审核者批准、CODEOWNER 批准。
2. 新推送使旧批准失效；最近一次可审核推送需要其他人批准。
3. 当前基线上的必需 `checks` 状态成功，所有审核讨论解决。
4. 禁止 force push、删除主分支，自动合并关闭。

首次初始化的 `main` 仅将 `K-3-LT` 列为 CODEOWNER，而 PR #1 的作者和推送者也是该账号。
GitHub 按 **base 分支**识别 CODEOWNERS，并禁止作者自审；PR 中增加 `aikevan` 在合并前无法解除这个初始依赖。
Owner 对 PR #1 的指定提交批准了一次性审核例外；必需 CI 仍通过，合并后立即移除例外并恢复原保护设置。
`main` 现已将两名既有管理员 `K-3-LT`、`aikevan` 列入 CODEOWNERS，后续 PR 继续要求独立管理员审核。
这次例外没有变成社区贡献可绕过审核的长期规则，也没有授予其他人管理员权限。

### 审核与审计

仓库公开，允许 fork 和社区 PR，Issues、Discussions 与私密漏洞报告已启用。
社区可以提出建议和代码；合并仍由管理员审核。CLI 的管理员身份不会被当作另一位审核者，也不会伪造 CI 或自审批准。

```bash
python scripts/check_governance.py
```

审计检查仓库公开性、管理员角色、主分支保护、base CODEOWNERS 与 Actions 状态。
PR #1 合并前，base CODEOWNERS 项会报告未完成；合并后的治理检查已通过。
当前状态以 [PR #1](https://github.com/IteraCompute/agent-connect/pull/1)、`main` 及 GitHub 设置为准。

## English

### Administrator identity and Actions repair

On 2026-11-17, the authenticated `K-3-LT` account was confirmed to be both repository administrator
and IteraCompute organization Owner. The CLI token's authorization is separate from that role:
it has `repo`, `workflow` and `read:org`, but lacks the `admin:org` scope required by the organization
Actions policy API. The earlier organization 403 and repository 409 did not mean the account lacked
an administrator role.

After the Owner signed into GitHub in the browser, organization Actions was changed from Disabled
to **Selected repositories**, with **agent-connect only** selected. The repository API confirms
`enabled=true`. Default workflow permissions remain **read**, and workflow PR approval remains
disabled. Other repositories were not enabled. No broader CLI token scope was granted.

### First CODEOWNER bootstrap

Protected `main` enforces rules for administrators too: one approving review, CODEOWNER approval,
stale-review dismissal, approval of the latest reviewable push by someone else, a passing `checks`
status against the current base, and resolved conversations. Force pushes and main deletion are
disabled, and automatic merge is off.

Initial base `main` named only `K-3-LT` as CODEOWNER; that account also authored and pushed PR #1.
GitHub uses the base branch's CODEOWNERS and does not permit author self-approval. Adding `aikevan`
inside the PR alone could not resolve that bootstrap dependency. The Owner approved a one-time
review exception for the specified PR #1 head. Required CI passed; the exception was removed and
the original protection settings restored immediately after the merge.
Current `main` lists both existing administrators in CODEOWNERS, so future PRs still require
independent administrator review. No new administrator was granted access, and the first-merge
exception is not a permanent bypass for community contributions.

Run `python scripts/check_governance.py` to check the current repository settings. Before PR #1
merged, its base-ownership audit was pending even after Actions was repaired; the post-merge
governance audit passed. The merged [PR #1](https://github.com/IteraCompute/agent-connect/pull/1),
current `main` and repository settings are the authoritative live state.

References:

- [Actions policy API and token scopes](https://docs.github.com/en/rest/actions/permissions#get-github-actions-permissions-for-an-organization)
- [Code owners and base branches](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [Protected branches and administrator enforcement](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
