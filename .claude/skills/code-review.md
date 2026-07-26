---
name: code-review
description: Review changes to cli/ against this project's functional-style, no-dynamic-magic code standards before committing. Run before every commit that touches cli/, not just periodically.
---

# code-review

`ruff`, `ty`, `pytest --cov-fail-under=100`, and `scripts/check_no_magic.py` catch the
mechanical violations of `PROJECT_PLAN.md` §10.1. This skill covers what they *can't* check —
the shape and architecture calls from §10.2. Run it before committing any change that touches
`cli/`, not just periodically; it's cheap and the whole point of the standard is that it holds
up all season without a human reviewing every diff.

## Checklist

Walk the diff (not just the final file) against each item. Flag anything that fails, propose a
fix, and only move on once it's addressed or explicitly accepted as an exception with a
one-line rationale in the commit message.

1. **Functions and dataclasses, not classes.** Any new class that isn't `@dataclass` or `Enum`
   needs a specific justification (e.g. it's a required adapter to a stdlib API that only
   accepts a class, like `http.server`'s request handler — see `tests/support/mock_http.py` for
   the canonical example). A "service"/"client"/"manager" class with methods and instance state
   is always wrong here — it should be a module of functions taking explicit parameters.
2. **No new decorators beyond `@dataclass` and `@contextmanager`.** In particular: no
   `@pytest.fixture`, no `@pytest.mark.parametrize`, no framework-registration decorators
   (`@app.command()`-style). If a test needs shared setup, is it a plain function called
   explicitly at the top of each test, not a fixture pytest injects by argument-name matching?
3. **Composition over inheritance.** No base classes, no mixins, no ABCs. Shared behavior
   between two things is a function both call, never a shared superclass.
4. **Tagged unions + `match`, not optional-field bags.** Does new state modeling make invalid
   combinations unrepresentable (a `Union` of distinct `@dataclass` cases) rather than one type
   with several `| None` fields and a runtime invariant nothing enforces? Is `match`/`case` used
   on those unions instead of `if`/`elif` chains on a `.kind` string?
5. **No dynamic magic beyond the mechanical grep check.** Anything that reaches into another
   module's internals, relies on name-matching/introspection to wire behavior together, or uses
   metaprogramming cleverness `check_no_magic.py`'s literal string search wouldn't catch (e.g. a
   hand-rolled registry keyed by function `__name__`, dynamic class creation, `__getattr__`
   overrides) should be flagged even though the CI grep won't catch it.
6. **Explicit parameter threading over implicit/global state.** Especially for HTTP: does test
   coverage for new Sleeper-API-calling code use `tests/support/mock_http.py` (real local
   server, `base_url` parameter as the test seam) rather than any form of faked-out transport?
   Is every new external dependency (HTTP calls, the system clock, `time.sleep`, random values)
   an explicit parameter with a real default, not reached for globally?
7. **Full typing, no suppressions.** Is everything fully typed with no `# type: ignore`? If `ty`
   can't be satisfied cleanly, that's a signal the types need to model the domain better (see
   item 4), not a reason to suppress the checker.
8. **`# pragma: no cover` used narrowly and honestly.** Every occurrence should sit on the exact
   uncoverable line (not file/module scope) and have a comment explaining *why* it can't or
   shouldn't be covered by the automated suite (e.g. the one `nfl_data_py` call site per
   `PROJECT_PLAN.md` §10.4's closing note, or a CLI entrypoint's `if __name__ == "__main__":`
   guard). A pragma covering logic that could reasonably be tested is a finding, not a pass.
9. **Tests are plain `test_*` functions with plain helper functions for shared construction**
   (e.g. `make_league(**overrides) -> League`), looping over cases inside one test body or using
   multiple explicitly-named test functions for repeated scenarios — never a `parametrize`
   decorator generating cases.

## Notes

- This skill is a review pass over a diff, not a rewrite-everything pass — the goal is catching
  drift from the standard as it's introduced, not relitigating already-reviewed code.
- If a genuine exception is warranted (the mock-http-server pattern in item 1 is the reference
  case for "stdlib class used as a library, not a violation"), document it inline in the code
  next to the exception, not just in this checklist.
