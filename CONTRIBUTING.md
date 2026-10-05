# Contributing to Electricity Share Distributor (`esd`)

Thank you for your interest in contributing to `electricity-share-distributor`!

## Code of Conduct & Standards

- **Language:** All code, comments, docstrings, tests, and commit messages must be written in **English**.
- **Typing:** Use Python 3.11+ type hints (`typing`, `X | Y` union syntax) everywhere.
- **Formatting & Linting:** Code formatting and linting is enforced via [Ruff](https://astral.sh/ruff).
  ```bash
  ruff check --fix .
  ruff format .
  ```
- **Testing:** Ensure all tests pass with `pytest`:
  ```bash
  pytest -v
  ```
- **Conventional Commits:** Commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) format:
  - `feat: ...` for new features
  - `fix: ...` for bug fixes
  - `chore: ...` for maintenance, tooling, or version bumps
  - `docs: ...` for documentation
  - `test: ...` for tests

## Versioning (CalVer)

This project strictly follows Calendar Versioning (`YYYY.MM.NNN`).
Before each commit, run:
```bash
python -m src.version bump
```
Or let the pre-commit hook automatically enforce and bump the version for you.
