# Contributing to Electricity Share Distributor (`esd`)

## 🛠️ Development Standards

- **Language & Typing:** Universal English codebase. Strict Python 3.11+ typing (`X | Y`, dataclasses) across all modules.
- **Code Quality:** Format and lint with [Ruff](https://astral.sh/ruff):
  ```bash
  ruff check --fix . && ruff format .
  ```
- **Testing:** Verify changes with `pytest -v`.
- **Conventional Commits:** Adhere to [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).
- **Calendar Versioning (CalVer):** Bump release version (`YYYY.MM.NNN`) on every commit:
  ```bash
  python -m src.version bump
  ```

## 🔒 Data Privacy & Security (GDPR / LOPDGDD)

- **Zero Real Data Policy:** Never commit or log real CUPS, contract IDs, customer names, addresses, or actual consumption curves.
- **Synthetic Identifiers Only:** Use authorized mock CUPS conforming to `ES00210000000000XXYY` (e.g. `ES0021000000000001AA`).
- **Privacy Harness:** Audit workspace and git history before pushing:
  ```bash
  python3 -m src.security          # Full scan (workspace & git history)
  python3 -m src.security --staged # Pre-commit staged changes scan
  ```
