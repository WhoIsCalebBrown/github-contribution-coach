# GitHub Contribution Coach

GitHub Contribution Coach turns an imbalanced activity graph and unfinished
local work into a short list of genuine contribution opportunities.

It is deliberately read-only. It does not generate commits, file issues, submit
pull requests, or leave reviews for you. Those actions only count when they are
useful to another person, so the tool finds the work and leaves the judgment to
you.

## What it does

- reports commits, issues, pull requests, reviews, and private/restricted work
  over a configurable period;
- recommends the next category where real participation is missing;
- lists pull requests where your review is requested;
- finds `help wanted` and `good first issue` work in projects you choose;
- scans local Git repositories for uncommitted or unpushed work that could
  become an upstream contribution.

## Requirements

- Python 3.11+
- [GitHub CLI](https://cli.github.com/) authenticated with `gh auth login`

## Install for development

```bash
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/contribution-coach init
```

Or install the CLI directly with `pipx`:

```bash
pipx install git+https://github.com/WhoIsCalebBrown/github-contribution-coach.git
contribution-coach init
```

Edit `~/.config/contribution-coach/config.toml`:

```toml
[coach]
period_days = 365
repositories = ["omacom/omarchy", "owner/another-project"]
automated_repositories = ["owner/old-activity-bot"]
local_roots = ["~/Code", "~/.config/omarchy/plugins"]
```

Then run:

```bash
contribution-coach status
contribution-coach opportunities
contribution-coach scan
contribution-coach plan
```

## Philosophy

A green square is an exhaust trail, not the destination. Useful issues,
thoughtful reviews, maintained tools, and merged fixes create the reputation
that a synthetic activity graph cannot.
