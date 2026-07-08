# Contributing to Feeds Manager

Thanks for considering a contribution. This project is small and intentionally
low-ceremony — these guidelines are just enough to keep changes consistent.

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Requires Python 3.9+. See the [README](README.md) for how to run the app and
a tour of the project layout.

## Running tests

```bash
pytest
pytest --cov=feedsmanager --cov-report=term-missing
```

Please add or update tests for any change to `feedsmanager/*.py` (the non-UI
logic — models, config, storage, feed_parser, users, audit, background,
export_import). Tests live in `tests/`, one file per module, and use the
`isolated_paths` fixture (`tests/conftest.py`) so nothing touches your real
`~/.../feedsmanager` data. `feedsmanager/screens/*` (the Textual UI) isn't covered
by automated tests yet — verify UI changes by hand (Textual's `run_test`/
pilot is a good way to script that) and describe how you tested them in your
PR.

All tests must pass before a PR is merged. If you touch behavior that's hard
to unit test (e.g. `runner.py`'s subprocess loop), say so in the PR and
explain how you verified it manually.

## Code style

- Match the style of the surrounding code rather than introducing a new
  pattern — this repo favors small, focused functions/classes and reuses
  existing conventions (e.g. atomic `tmp` + `os.replace` writes for JSON
  files, `to_dict`/`from_dict` on dataclasses, Textual screens following the
  existing modal/full-screen patterns in `feedsmanager/screens/`).
- No comments unless they explain a non-obvious *why* (a constraint, a
  workaround, an invariant) — well-named code should speak for itself.
- Don't add abstractions, config flags, or error handling for cases that
  can't happen. Keep changes scoped to what they're solving.
- Run `python3 -c "import ast; ast.parse(open('path/to/file.py').read())"`
  or just import the module to catch syntax errors before opening a PR.

## Submitting changes

1. Open an issue first for anything nontrivial (new features, behavior
   changes) so the approach can be discussed before you invest time.
2. Keep PRs focused — one logical change per PR, with a description of
   *why*, not just *what*.
3. Update the [README](README.md) if you change user-facing behavior
   (keybindings, CLI commands, file formats/locations).
4. Make sure `pytest` passes and new code has test coverage where it's
   feasible (see above).

## Reporting bugs

Open an issue with: what you did, what you expected, what happened instead,
your OS, and the relevant snippet of `runner.log` / `audit.log` if the bug
involves the background runner or admin actions.
