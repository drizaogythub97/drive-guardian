# Drive Guardian

> 🇧🇷 [Versão em português](README.pt-BR.md)

Continuous local backup of Google Drive folders to a physical disk on Windows.
A tray app with a configuration UI (PySide6) over a headless core (CLI), change
detection via Drive API polling, full-size downloads, and phone alerts via ntfy.

**Design principles:** never delete or destructively overwrite local files
(cumulative policy), always atomic downloads (md5-verified), zero paid
dependencies, and no secrets in the repo. See [`CLAUDE.md`](CLAUDE.md) and
[`SPEC.md`](SPEC.md).

## Status

Under active development, phased delivery:

- **Phase 0 — Foundation ✅** — skeleton, config, SQLite state, logging, service
  account auth, `python cli.py list` prints the Drive folder tree.
- **Phase 1 — Headless MVP ✅** — full reconciliation, download queue, atomic
  download (`.part` → md5 → rename) with Range resume, `_versões/` for modified
  files, incremental `changes.list` polling, and `sync` / `watch` / `--dry-run` CLI.
- **Phase 2 — Alerts** — error levels, ntfy, healthchecks.io heartbeat, weekly summary.
- **Phase 3 — UI** — tray, config window, logs, "Check now", Windows startup.
- **Phase 4 — GitHub polish** — user OAuth, native Docs export, READMEs, PyInstaller, tests.

## Quick start (developers)

Requires Python 3.12+.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -e ".[dev]"

cp config.example.yaml config.yaml   # then edit
python cli.py list                    # prints the monitored Drive folder tree
```

### Configuration

Copy `config.example.yaml` to `config.yaml` (git-ignored) and set your Drive
folder ID, service-account key path, and notification settings. Full reference:
[`SPEC.md` §1](SPEC.md).

**Service account setup:** create a service account in Google Cloud Console,
download its JSON key to `secrets/sa-key.json`, and share the target Drive folder
with the service account's e-mail (Reader role).

## Development

```bash
ruff check . && mypy core/ && pytest   # gate before every commit
```

## License

[MIT](LICENSE)
