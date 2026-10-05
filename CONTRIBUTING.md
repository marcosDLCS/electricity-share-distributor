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

## 🔒 Privacy, Anonymization & Security Standards

- **CUPS Confidentiality:** Universal Supply Point Codes (CUPS) are legally protected identifiers under European GDPR and Spanish Organic Law 3/2018 (LOPDGDD).
- **Prohibited Data:** Never commit, log, or push real residential CUPS, customer names, contract IDs, or real metering data.
- **Permitted Mock Data:** Use exclusively synthetic mock identifiers following the standard prefix format: `ES0021000000000001AA`, `ES0021000000000002BB`, etc.
- **Automated Verification:** The repository enforces this invariant via a pre-commit hook and automated test suite. You can manually run the privacy verification harness at any time:
  ```bash
  python3 -m src.security
  ```

## Versioning (CalVer)

This project strictly follows Calendar Versioning (`YYYY.MM.NNN`).
Before each commit, run:
```bash
python -m src.version bump
```
Or let the pre-commit hook automatically enforce and bump the version for you.
