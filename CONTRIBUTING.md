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

- **CUPS Confidentiality:** Universal Supply Point Codes (CUPS) are legally protected residential identifiers under European GDPR (Regulation EU 2016/679) and Spanish Organic Law 3/2018 (LOPDGDD).
- **Prohibited Data:** Never commit, log, or push real residential CUPS, customer names, addresses, contract IDs, or real metering time-series.
- **Permitted Mock Data:** Use exclusively synthetic mock identifiers following the standard format: `ES00210000000000XXYY` (e.g., `ES0021000000000001AA`, `ES0021000000000002BB`, etc.).
- **Local Data Isolation:** Input raw data directories (`.input/`) and output reports (`.output/`) are excluded from Git via `.gitignore`. Do not bypass this exclusion.
- **Automated Verification Harness:** The repository enforces this invariant via pre-commit hooks, automated tests, and git history auditing. Run the verification at any time:
  ```bash
  # Check workspace files and entire git commit history
  python3 -m src.security

  # Check only staged changes before committing
  python3 -m src.security --staged
  ```
- **Clean Git History Guarantee:** Every commit in the repository history must be 100% free of real CUPS or private customer data. Any compromised commit must be amended before pushing to remote repositories.

## Versioning (CalVer)

This project strictly follows Calendar Versioning (`YYYY.MM.NNN`).
Before each commit, run:
```bash
python -m src.version bump
```
Or let the pre-commit hook automatically enforce and bump the version for you.
