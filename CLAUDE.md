# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install for development
python -m pip install -e '.[develop,docs]'

# Run all tests (includes doctests in papis/ modules)
python -m pytest papis tests

# Run a single test file
python -m pytest tests/test_document.py

# Run a single test by name
python -m pytest tests/test_document.py::test_function_name

# Run only doctests in a module
python -m pytest --doctest-modules papis/document.py

# Lint (ruff + mypy)
make ci-lint
# or individually:
ruff check
python -m mypy

# Run tests exactly as CI does
make ci-test
make ci-lint

# Fix auto-fixable lint issues
ruff check --fix

# Build docs
make doc
```

## Architecture Overview

Papis is a CLI document and bibliography manager built on Click. The main entry point is `papis/commands/default.py`, which defines the top-level `papis` group using `CommandPluginLoaderGroup` — this dynamically loads all subcommands from the `papis.command` entry-point namespace defined in `pyproject.toml`.

### Core Data Model

- **`papis/document.py`**: The `Document` class (a dict subclass) is the central data type. Each document lives in its own folder with a `info.yaml` file storing metadata. `KeyConversionPair` / `keyconversion_to_data` are used throughout importers and downloaders to normalize external metadata to papis key names.
- **`papis/library.py`**: A `Library` is a named collection of folder paths containing documents.
- **`papis/config.py`**: INI-style configuration via `configparser`. Settings are registered via `register_default_settings` and accessed with `papis.config.get("key")`. Default values live in `papis/defaults.py`.
- **`papis/database/`**: Two backends — `cache` (pickle-based, default) and `whoosh` (full-text search). `papis.database.get_database()` returns the active backend.

### Plugin System

All major extension points use Python entry points (`importlib.metadata`), loaded via `papis/plugin.py`:

| Namespace | Base class | Location |
|-----------|-----------|----------|
| `papis.command` | Click group/command | `papis/commands/` |
| `papis.importer` | `papis.importer.Importer` | `papis/importer/` |
| `papis.downloader` | `papis.downloaders.Downloader` | `papis/downloaders/` |
| `papis.explorer` | Click command | `papis/explorers/` |
| `papis.exporter` | callable | `papis/exporters/` |
| `papis.picker` | — | `papis/pick/` |
| `papis.format` | — | `papis/format/` |

**Importers** (`papis/importer/`): Fetch metadata/files from a URI (API, file, identifier). Implement `match(uri)` (class method returning self or None) and `fetch()` (populates `self.ctx` with data/files). Used by `papis add`.

**Downloaders** (`papis/downloaders/`): Subclass of `Importer` focused on web scraping. Implement `match()`, optionally `get_data()`, `get_bibtex_url()`, `get_document_url()`.

### Adding a New Configuration Option

1. Add default in `papis/defaults.py` under the `settings` dict.
2. Document in `doc/source/default_settings.rst`.
3. Access via `papis.config.get("myoption")`.

For section-scoped options, call `papis.config.register_default_settings({"section": {"option": value}})` and access with `papis.config.get("option", section="section")`.

### Testing

Tests use pytest with custom fixtures from `papis/testing.py` (registered as a pytest plugin via the `papis.testing` extra). Key fixtures:

- `tmp_config`: provides an isolated papis configuration
- `tmp_library`: provides a library populated with test documents
- `resource_cache`: caches remote resources for downloader tests

Set `PAPIS_UPDATE_RESOURCES=remote` (or `local`/`both`) to refresh cached test resources.

Doctests in `papis/*.py` modules are run automatically as part of the test suite (`--doctest-modules` in `pyproject.toml`).

### Code Style

- Python 3.10+ syntax; strict mypy; ruff linting.
- All files must have `from __future__ import annotations` as the first import (enforced by ruff isort).
- Double quotes for strings/docstrings.
- Sphinx-style docstrings.
