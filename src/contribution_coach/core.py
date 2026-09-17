from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable


Runner = Callable[[list[str]], str]


def run_command(arguments: list[str]) -> str:
    result = subprocess.run(arguments, check=True, capture_output=True, text=True)
    return result.stdout


def parse_json_output(output: str) -> Any:
    """Read JSON even when a command shim prints setup notices first."""
    decoder = json.JSONDecoder()
    for index, character in enumerate(output):
        if character not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(output[index:])
            return value
        except json.JSONDecodeError:
            continue
    raise ValueError("GitHub CLI returned no JSON payload")


@dataclass(frozen=True)
class ContributionMetrics:
    total: int
    commits: int
    issues: int
    pull_requests: int
    reviews: int
    restricted: int

    @property
    def known_total(self) -> int:
        return self.commits + self.issues + self.pull_requests + self.reviews

    def percentage(self, value: int) -> float:
        denominator = self.known_total + self.restricted
        return 0 if denominator == 0 else value * 100 / denominator


@dataclass(frozen=True)
class Opportunity:
    kind: str
    repository: str
    title: str
    url: str


@dataclass(frozen=True)
class LocalRepository:
    name: str
    location: Path
    remote: str
    branch: str
    changed_files: int
    ahead: int


class GitHubClient:
    def __init__(self, runner: Runner = run_command) -> None:
        self.runner = runner

    def login(self) -> str:
        output = self.runner(["gh", "api", "user"])
        return str(parse_json_output(output)["login"])

    def user_id(self, login: str) -> str:
        query = "query($login:String!){user(login:$login){id}}"
        output = self.runner(
            ["gh", "api", "graphql", "-f", f"query={query}", "-f", f"login={login}"]
        )
        return str(parse_json_output(output)["data"]["user"]["id"])

    def metrics(self, login: str, days: int) -> tuple[ContributionMetrics, datetime, datetime]:
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        query = """
query($login:String!,$from:DateTime!,$to:DateTime!){
  user(login:$login){
    contributionsCollection(from:$from,to:$to){
      contributionCalendar{totalContributions}
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
    }
  }
}
""".strip()
        payload = self.runner(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                f"query={query}",
                "-f",
                f"login={login}",
                "-f",
                f"from={start.isoformat().replace('+00:00', 'Z')}",
                "-f",
                f"to={end.isoformat().replace('+00:00', 'Z')}",
            ]
        )
        values = parse_json_output(payload)["data"]["user"]["contributionsCollection"]
        return (
            ContributionMetrics(
                total=values["contributionCalendar"]["totalContributions"],
                commits=values["totalCommitContributions"],
                issues=values["totalIssueContributions"],
                pull_requests=values["totalPullRequestContributions"],
                reviews=values["totalPullRequestReviewContributions"],
                restricted=values["restrictedContributionsCount"],
            ),
            start,
            end,
        )

    def repository_commits(
        self, repository: str, author_id: str, start: datetime, end: datetime
    ) -> int:
        owner, name = repository.split("/", 1)
        query = """
query($owner:String!,$name:String!,$since:GitTimestamp!,$until:GitTimestamp!,$author:ID!){
  repository(owner:$owner,name:$name){
    defaultBranchRef{target{... on Commit{
      history(since:$since,until:$until,author:{id:$author}){totalCount}
    }}}
  }
}
""".strip()
        output = self.runner(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                f"query={query}",
                "-f",
                f"owner={owner}",
                "-f",
                f"name={name}",
                "-f",
                f"since={start.isoformat().replace('+00:00', 'Z')}",
                "-f",
                f"until={end.isoformat().replace('+00:00', 'Z')}",
                "-f",
                f"author={author_id}",
            ]
        )
        values = parse_json_output(output)["data"]["repository"]
        return int(values["defaultBranchRef"]["target"]["history"]["totalCount"])

    def search(self, query: str, kind: str, limit: int = 10) -> list[Opportunity]:
        payload = self.runner(
            [
                "gh",
                "api",
                "--method",
                "GET",
                "search/issues",
                "-f",
                f"q={query}",
                "-f",
                f"per_page={limit}",
            ]
        )
        opportunities = []
        for item in parse_json_output(payload).get("items", []):
            repository_url = item.get("repository_url", "")
            repository = repository_url.removeprefix("https://api.github.com/repos/")
            opportunities.append(
                Opportunity(kind=kind, repository=repository, title=item["title"], url=item["html_url"])
            )
        return opportunities


def git_output(repo: Path, *arguments: str, runner: Runner = run_command) -> str:
    return runner(["git", "-C", str(repo), *arguments]).strip()


def scan_repositories(roots: list[Path], runner: Runner = run_command) -> list[LocalRepository]:
    found: dict[Path, LocalRepository] = {}
    for root in roots:
        expanded = root.expanduser()
        if not expanded.exists():
            continue
        candidates = [expanded] if (expanded / ".git").exists() else []
        candidates.extend(marker.parent for marker in expanded.rglob(".git") if marker.is_dir())
        for repo in candidates:
            resolved = repo.resolve()
            if resolved in found:
                continue
            try:
                status = git_output(resolved, "status", "--porcelain", runner=runner)
                branch = git_output(resolved, "branch", "--show-current", runner=runner) or "detached"
            except subprocess.CalledProcessError:
                continue
            try:
                remote = git_output(resolved, "remote", "get-url", "origin", runner=runner)
            except subprocess.CalledProcessError:
                remote = "no origin remote"
            try:
                ahead_text = git_output(
                    resolved,
                    "rev-list",
                    "--count",
                    "@{upstream}..HEAD",
                    runner=runner,
                )
            except subprocess.CalledProcessError:
                ahead_text = "0"
            found[resolved] = LocalRepository(
                name=resolved.name,
                location=resolved,
                remote=remote,
                branch=branch,
                changed_files=len(status.splitlines()) if status else 0,
                ahead=int(ahead_text or 0),
            )
    return sorted(found.values(), key=lambda repo: (-repo.ahead, -repo.changed_files, repo.name.lower()))


def coaching_priorities(metrics: ContributionMetrics, automated_commits: int = 0) -> list[str]:
    priorities = []
    if metrics.reviews == 0:
        priorities.append("Review one open pull request where you can test the change and leave specific feedback.")
    if metrics.issues == 0:
        priorities.append("Turn one reproduced bug into a focused issue with steps, evidence, and expected behavior.")
    if metrics.pull_requests < 12:
        priorities.append("Ship one small upstream fix from an existing local customization.")
    if automated_commits > 0:
        priorities.append("Retire automated activity; it is outweighing the visible work on your profile.")
    if not priorities:
        priorities.append("Keep the cadence: one useful review or upstream fix this week.")
    return priorities
