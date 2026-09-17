from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from contribution_coach.core import ContributionMetrics, coaching_priorities, scan_repositories


class CoachingTests(TestCase):
    def test_prioritizes_real_missing_activity(self) -> None:
        metrics = ContributionMetrics(
            total=1722,
            commits=546,
            issues=0,
            pull_requests=13,
            reviews=0,
            restricted=1150,
        )

        priorities = coaching_priorities(metrics, automated_commits=719)

        self.assertIn("Review one open pull request", priorities[0])
        self.assertTrue(any("reproduced bug" in priority for priority in priorities))
        self.assertTrue(any("Retire automated activity" in priority for priority in priorities))

    def test_does_not_call_private_work_automated_without_evidence(self) -> None:
        metrics = ContributionMetrics(100, 10, 1, 1, 1, 87)

        priorities = coaching_priorities(metrics)

        self.assertFalse(any("automated" in priority for priority in priorities))

    def test_percentage_includes_restricted_activity(self) -> None:
        metrics = ContributionMetrics(100, 20, 5, 5, 0, 70)

        self.assertEqual(metrics.percentage(metrics.commits), 20)

    def test_scans_dirty_and_ahead_repositories(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "plugin"
            (repo / ".git").mkdir(parents=True)

            def runner(arguments: list[str]) -> str:
                command = tuple(arguments[3:])
                responses = {
                    ("status", "--porcelain"): " M Panel.qml\n?? test.qml\n",
                    ("branch", "--show-current"): "feature\n",
                    ("remote", "get-url", "origin"): "https://example.com/plugin.git\n",
                    ("rev-list", "--count", "@{upstream}..HEAD"): "1\n",
                }
                return responses[command]

            repositories = scan_repositories([root], runner=runner)

        self.assertEqual(len(repositories), 1)
        self.assertEqual(repositories[0].changed_files, 2)
        self.assertEqual(repositories[0].ahead, 1)
