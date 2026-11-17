"""Read-only audit of repository visibility and administrator review enforcement."""

import base64
import json
import subprocess


def api(path):
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def main():
    repo = "IteraCompute/agent-connect"
    metadata = api("repos/" + repo)
    protection = api("repos/" + repo + "/branches/main/protection")
    reviews = protection["required_pull_request_reviews"]
    owners = base64.b64decode(
        api("repos/" + repo + "/contents/.github/CODEOWNERS?ref=main")["content"]
    ).decode()
    checks = {
        "public": metadata["visibility"] == "public",
        "issues": metadata["has_issues"],
        "discussions": metadata["has_discussions"],
        "no_auto_merge": not metadata["allow_auto_merge"],
        "admins_enforced": protection["enforce_admins"]["enabled"],
        "code_owner_review": reviews["require_code_owner_reviews"],
        "approval_required": reviews["required_approving_review_count"] >= 1,
        "stale_reviews_dismissed": reviews["dismiss_stale_reviews"],
        "latest_push_approved": reviews["require_last_push_approval"],
        "ci_required": "checks" in protection["required_status_checks"]["contexts"],
        "conversations_resolved": protection["required_conversation_resolution"]["enabled"],
        "no_force_push": not protection["allow_force_pushes"]["enabled"],
        "no_main_deletion": not protection["allow_deletions"]["enabled"],
        "codeowner_is_admin": api("repos/" + repo + "/collaborators/K-3-LT/permission")[
            "permission"
        ]
        == "admin",
        "independent_admin_is_admin": api("repos/" + repo + "/collaborators/aikevan/permission")[
            "permission"
        ]
        == "admin",
        "base_codeowners_include_independent_admin": "@aikevan" in owners,
        "actions_enabled": api("repos/" + repo + "/actions/permissions")["enabled"],
    }
    print(json.dumps(checks, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
