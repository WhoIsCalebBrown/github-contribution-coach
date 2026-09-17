import json
from unittest import TestCase

from contribution_coach.core import GitHubClient, parse_json_output


class GitHubClientTests(TestCase):
    def test_reads_json_after_command_shim_notices(self) -> None:
        output = 'mise installed a tool\n{"login":"caleb"}\n'

        self.assertEqual(parse_json_output(output)["login"], "caleb")

    def test_reads_contribution_metrics(self) -> None:
        payload = {
            "data": {
                "user": {
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 120},
                        "totalCommitContributions": 80,
                        "totalIssueContributions": 5,
                        "totalPullRequestContributions": 20,
                        "totalPullRequestReviewContributions": 10,
                        "restrictedContributionsCount": 5,
                    }
                }
            }
        }
        client = GitHubClient(lambda _: json.dumps(payload))

        metrics, _, _ = client.metrics("caleb", 30)

        self.assertEqual(metrics.total, 120)
        self.assertEqual(metrics.pull_requests, 20)
        self.assertEqual(metrics.reviews, 10)

    def test_reads_search_results(self) -> None:
        payload = {
            "items": [
                {
                    "title": "Fix the useful thing",
                    "html_url": "https://github.com/acme/project/issues/1",
                    "repository_url": "https://api.github.com/repos/acme/project",
                }
            ]
        }
        client = GitHubClient(lambda _: json.dumps(payload))

        opportunities = client.search("repo:acme/project is:issue", "issue")

        self.assertEqual(opportunities[0].repository, "acme/project")
        self.assertEqual(opportunities[0].kind, "issue")

    def test_reads_repository_commit_count(self) -> None:
        payload = {
            "data": {
                "repository": {
                    "defaultBranchRef": {"target": {"history": {"totalCount": 719}}}
                }
            }
        }
        client = GitHubClient(lambda _: json.dumps(payload))
        _, start, end = GitHubClient(
            lambda _: json.dumps(
                {
                    "data": {
                        "user": {
                            "contributionsCollection": {
                                "contributionCalendar": {"totalContributions": 1},
                                "totalCommitContributions": 1,
                                "totalIssueContributions": 0,
                                "totalPullRequestContributions": 0,
                                "totalPullRequestReviewContributions": 0,
                                "restrictedContributionsCount": 0,
                            }
                        }
                    }
                }
            )
        ).metrics("caleb", 30)

        count = client.repository_commits("caleb/noise", "U_1", start, end)

        self.assertEqual(count, 719)
