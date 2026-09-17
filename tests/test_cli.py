from contextlib import redirect_stdout
from io import StringIO
from unittest import TestCase

from contribution_coach.cli import opportunities_command


class FakeClient:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def login(self) -> str:
        return "caleb"

    def search(self, query: str, kind: str, limit: int):
        self.queries.append(query)
        return []


class OpportunityTests(TestCase):
    def test_batches_configured_repositories_into_four_searches(self) -> None:
        client = FakeClient()

        with redirect_stdout(StringIO()):
            opportunities_command(client, ["acme/one", "acme/two"], 5)

        self.assertEqual(len(client.queries), 4)
        self.assertIn("repo:acme/one repo:acme/two", client.queries[1])
        self.assertIn('label:"help wanted"', client.queries[2])
        self.assertIn('label:"good first issue"', client.queries[3])
