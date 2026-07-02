"""Linear reference adapter (via Linear's public GraphQL API).

Auth: the `LINEAR_API_KEY` environment variable (never written to files or
logs — see docs/SECURITY.md). Stdlib-only: uses urllib. A `transport` callable
can be injected for testing so no network is needed.

Branch naming: issues drive `kelix/<issue-identifier>-<slug>` branches so
Linear's GitHub integration auto-links branches and PRs to issues.

Every method is non-fatal: on any error it logs and returns a benign value,
so a Linear outage never breaks the loop.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request

from .base import InboundIssue, sanitize_inbound

log = logging.getLogger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"

_ISSUES_QUERY = """
query KelixIssues($filter: IssueFilter) {
  issues(filter: $filter, first: 50) {
    nodes {
      id identifier title description priority
      state { name type }
      labels { nodes { name } }
    }
  }
}
"""

_COMMENT_MUTATION = """
mutation KelixComment($issueId: String!, $body: String!) {
  commentCreate(input: { issueId: $issueId, body: $body }) {
    success
  }
}
"""


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].strip("-") or "issue"


def branch_name(prefix: str, identifier: str, title: str) -> str:
    return f"{prefix}{identifier.lower()}-{slugify(title)}"


def _default_transport(payload: dict, api_key: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        LINEAR_API_URL,
        data=data,
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


class LinearAdapter:
    name = "linear"

    def __init__(self, team: str = "", transport=None, api_key: str | None = None):
        self.team = team
        self._transport = transport or _default_transport
        # Read once; do not store beyond the process, never log it.
        self._api_key = api_key if api_key is not None else os.environ.get("LINEAR_API_KEY", "")

    def _call(self, query: str, variables: dict) -> dict | None:
        if not self._api_key:
            log.warning("linear sync skipped: LINEAR_API_KEY not set")
            return None
        try:
            result = self._transport({"query": query, "variables": variables}, self._api_key)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            log.warning("linear API unreachable, skipping: %s", exc)
            return None
        except Exception as exc:  # never fatal
            log.warning("linear sync error, skipping: %s", exc)
            return None
        if result.get("errors"):
            log.warning("linear API errors, skipping: %s", result["errors"])
            return None
        return result.get("data")

    def fetch_issues(self) -> list[InboundIssue]:
        # Only pull actionable (unstarted/started) issues; done/canceled are
        # not backlog work. Team filter is applied when configured.
        filt: dict = {"state": {"type": {"in": ["backlog", "unstarted", "started"]}}}
        if self.team:
            filt["team"] = {"key": {"eq": self.team}}
        data = self._call(_ISSUES_QUERY, {"filter": filt})
        if not data:
            return []
        issues: list[InboundIssue] = []
        for node in data.get("issues", {}).get("nodes", []):
            # Linear priority: 1=urgent..4=low, 0=none. Map into owner band
            # (70-89) so tracker issues outrank kelix-proposed work but stay
            # legible in the rubric.
            lp = node.get("priority") or 0
            priority = {1: 89, 2: 85, 3: 80, 4: 75, 0: 78}.get(lp, 78)
            issues.append(
                InboundIssue(
                    external_id=node["id"],
                    identifier=node.get("identifier", node["id"]),
                    title=sanitize_inbound(node.get("title", ""), max_len=200),
                    body=sanitize_inbound(node.get("description", "")),
                    priority=priority,
                    labels=[
                        n["name"] for n in node.get("labels", {}).get("nodes", [])
                    ],
                )
            )
        return issues

    def _comment(self, issue_id: str, body: str) -> bool:
        from ..security import scrub

        data = self._call(_COMMENT_MUTATION, {"issueId": issue_id, "body": scrub(body)})
        return bool(data and data.get("commentCreate", {}).get("success"))

    def push_status(self, external_id: str, status: str, evidence: str) -> bool:
        body = f"**Kelix**: task status → `{status}`\n\n{evidence}".strip()
        return self._comment(external_id, body)

    def push_pr_link(self, external_id: str, url: str) -> bool:
        return self._comment(external_id, f"**Kelix** opened a PR: {url}")
