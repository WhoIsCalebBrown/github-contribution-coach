from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .config import default_path, initialize, load
from .core import GitHubClient, coaching_priorities, scan_repositories


def status_command(client: GitHubClient, days: int, automated_repositories: list[str]) -> int:
    login = client.login()
    metrics, start, end = client.metrics(login, days)
    print(f"GitHub contribution health for {login}")
    print(f"{start.date()} through {end.date()} ({days} days)\n")
    print(f"  Total contributions       {metrics.total:>6}")
    print(f"  Public commits           {metrics.commits:>6}  {metrics.percentage(metrics.commits):5.1f}%")
    print(f"  Pull requests            {metrics.pull_requests:>6}  {metrics.percentage(metrics.pull_requests):5.1f}%")
    print(f"  Pull request reviews     {metrics.reviews:>6}  {metrics.percentage(metrics.reviews):5.1f}%")
    print(f"  Issues                   {metrics.issues:>6}  {metrics.percentage(metrics.issues):5.1f}%")
    print(f"  Private/restricted       {metrics.restricted:>6}  {metrics.percentage(metrics.restricted):5.1f}%")
    automated_commits = 0
    if automated_repositories:
        author_id = client.user_id(login)
        print("\nConfigured automated activity:")
        for repository in automated_repositories:
            count = client.repository_commits(repository, author_id, start, end)
            automated_commits += count
            print(f"  {repository:<36} {count:>6} commits")
        print(f"  Estimated non-automated total       {max(0, metrics.total - automated_commits):>6}")
    print("\nRecommended next actions:")
    for index, priority in enumerate(coaching_priorities(metrics, automated_commits), start=1):
        print(f"  {index}. {priority}")
    return 0


def opportunities_command(client: GitHubClient, repositories: list[str], limit: int) -> int:
    login = client.login()
    opportunities = client.search(
        f"is:pr is:open review-requested:{login}", "review", limit
    )
    if repositories:
        repository_scope = " ".join(f"repo:{repository}" for repository in repositories)
        opportunities.extend(
            client.search(
                f"{repository_scope} is:pr is:open -author:{login} sort:updated-desc",
                "review candidate",
                limit,
            )
        )
        for label in ("help wanted", "good first issue"):
            opportunities.extend(
                client.search(
                    f'{repository_scope} is:issue is:open label:"{label}"',
                    "issue",
                    limit,
                )
            )
    unique = {opportunity.url: opportunity for opportunity in opportunities}
    if not unique:
        print("No current review requests or labeled opportunities were found.")
        return 0
    for opportunity in unique.values():
        print(f"[{opportunity.kind}] {opportunity.repository}: {opportunity.title}\n  {opportunity.url}")
    return 0


def scan_command(roots: list[Path]) -> int:
    if not roots:
        print("No local roots configured. Run `contribution-coach init` and edit the config.")
        return 0
    for repo in scan_repositories(roots):
        state = []
        if repo.ahead:
            state.append(f"{repo.ahead} unpushed commit(s)")
        if repo.changed_files:
            state.append(f"{repo.changed_files} changed file(s)")
        if not state:
            continue
        print(f"{repo.name} [{repo.branch}] — {', '.join(state)}")
        print(f"  {repo.location}")
        print(f"  {repo.remote}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contribution-coach",
        description="Find genuine GitHub contribution opportunities without manufacturing activity.",
    )
    parser.add_argument("--config", type=Path, default=default_path())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="write a starter configuration")
    subparsers.add_parser("status", help="show contribution balance and priorities")
    opportunities = subparsers.add_parser("opportunities", help="show review requests and useful issues")
    opportunities.add_argument("--limit", type=int, default=10)
    subparsers.add_parser("scan", help="find local work that may be ready to contribute")
    subparsers.add_parser("plan", help="run status, opportunities, and local scan")
    return parser


def main(arguments: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(arguments)
    try:
        if args.command == "init":
            print(f"Created {initialize(args.config)}")
            return 0
        config = load(args.config)
        client = GitHubClient()
        if args.command == "status":
            return status_command(client, config.period_days, config.automated_repositories)
        if args.command == "opportunities":
            return opportunities_command(client, config.repositories, args.limit)
        if args.command == "scan":
            return scan_command(config.local_roots)
        if args.command == "plan":
            status_command(client, config.period_days, config.automated_repositories)
            print("\nOpportunities:\n")
            opportunities_command(client, config.repositories, 5)
            print("\nLocal contribution candidates:\n")
            return scan_command(config.local_roots)
    except (FileExistsError, KeyError, OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"contribution-coach: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
