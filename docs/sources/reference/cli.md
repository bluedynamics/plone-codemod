# CLI Reference

<!-- diataxis: reference -->

## Synopsis

```
plone-codemod [OPTIONS] SOURCE_DIR
```

## Positional Arguments

`SOURCE_DIR`
: Root directory of the source code to migrate (typically `src/`).

## Options

`--config PATH`
: Path to `migration_config.yaml`. Defaults to the config bundled with the package.

`--dry-run`
: Preview what would change without writing any files.

`--bootstrap`
: Enable Bootstrap 3 to 5 migration (opt-in, not run by default).

`--skip-python`
: Skip Phase 1 (Python import migration).

`--skip-zcml`
: Skip Phase 2 (ZCML migration).

`--skip-xml`
: Skip Phase 3 (GenericSetup XML migration).

`--skip-pt`
: Skip Phase 4 (Page template migration).

`--skip-audit`
: Skip Phase 6 (semgrep audit).

`--project-dir PATH`
: Project root directory (where `setup.py` / `pyproject.toml` live). Auto-detected by default by walking up from `SOURCE_DIR`.

`--namespaces`
: Enable Phase 7: PEP 420 namespace package migration (opt-in).

`--packaging`
: Enable Phase 8: `setup.py` to `pyproject.toml` migration (opt-in).

## Examples

```bash
# Default: phases 1-6 (no Bootstrap, no packaging)
plone-codemod ./src/

# Preview changes without modifying files
plone-codemod ./src/ --dry-run

# Include Bootstrap 3 to 5 migration
plone-codemod ./src/ --bootstrap

# Full modernization (PEP 420 + pyproject.toml)
plone-codemod ./src/ --namespaces --packaging

# Custom config file
plone-codemod ./src/ --config my_config.yaml

# Skip specific phases
plone-codemod ./src/ --skip-python --skip-audit

# Explicit project root for packaging
plone-codemod ./src/ --packaging --project-dir /path/to/project
```

## Phase Execution Order

Phases run in this fixed order:

1. Python imports (`--skip-python` to disable)
2. ZCML (`--skip-zcml` to disable)
3. GenericSetup XML (`--skip-xml` to disable)
4. Page templates (`--skip-pt` to disable)
5. Bootstrap (`--bootstrap` to enable)
6. Audit (`--skip-audit` to disable)
7. Namespace packages (`--namespaces` to enable)
8. Packaging (`--packaging` to enable)

Phase 7 always runs before Phase 8 so that `namespace_packages` is cleaned from `setup.py` before `pyproject.toml` generation.
