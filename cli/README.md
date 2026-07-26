# sleeper-agent CLI

Python CLI for the `sleeper-agent` project — see `../PROJECT_PLAN.md` and
`../IMPLEMENTATION_PLAN.md` for the full spec. All external I/O (Sleeper API, nflverse) and
numeric analysis (VORP, trade value, keeper cost) lives here; news research and judgment calls
live in Claude Code skills (`../.claude/skills/`) that call this CLI as their hands.

## Development

```sh
uv sync --locked
uv run sleeper-agent --help
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python scripts/check_no_magic.py
uv run pytest --cov=sleeper_agent --cov-report=term-missing --cov-fail-under=100
```

All of the above are hard gates in CI (`.github/workflows/ci.yml`).

## Code standards

See `PROJECT_PLAN.md` §10 for the full rationale. In short: `uv` + `ty` + `ruff` (default
rules), 100% line+branch test coverage, functional style (plain functions + `@dataclass`/`Enum`
only — no other classes, no inheritance), tagged unions matched with `match`/`case`, and no
dynamic magic (no mocking libraries, no monkeypatching, no `setattr`/`getattr` dispatch) — HTTP
tests run against a real local server (`tests/support/mock_http.py`) instead of a faked
transport. `.claude/skills/code-review.md` is the checklist for the parts of this a linter can't
enforce; run it before committing any change here.
