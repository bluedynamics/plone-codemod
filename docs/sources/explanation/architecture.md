# Architecture

<!-- diataxis: explanation -->

plone-codemod is organized as a phase-based pipeline orchestrated by a single CLI entry point.

## Module structure

```
src/plone_codemod/
  cli.py                    # Orchestrator: argument parsing, phase sequencing
  import_migrator.py        # Phase 1: libcst Python import rewriter
  zcml_migrator.py          # Phases 2-3: ZCML + GenericSetup XML
  pt_migrator.py            # Phases 4-5: Page templates + Bootstrap
  namespace_migrator.py     # Phase 7: PEP 420 namespace packages
  packaging_migrator.py     # Phase 8: setup.py → pyproject.toml
  migration_config.yaml     # Declarative rule definitions
  semgrep_rules/
    plone6_deprecated.yaml  # Phase 6: audit rules
```

## Data flow

```{mermaid}
flowchart LR
    YAML[migration_config.yaml] --> P1[Phase 1: Python]
    YAML --> P2[Phase 2: ZCML]
    YAML --> P3[Phase 3: XML]
    YAML --> P4[Phase 4: PT]
    YAML --> P5[Phase 5: Bootstrap]
    SG[semgrep_rules/] --> P6[Phase 6: Audit]
    P1 --> Files[Modified files]
    P2 --> Files
    P3 --> Files
    P4 --> Files
    P5 --> Files
    P6 --> Report[Audit report]
    Files --> P7[Phase 7: Namespaces]
    Files --> P8[Phase 8: Packaging]
```

All phases read the same YAML config (except the audit phase, which reads semgrep YAML). Each phase is independent and can be skipped, but phases always run in the same fixed order.

## Why phases run in order

- **Phase 7 before Phase 8**: Namespace migration removes `namespace_packages` from `setup.py`, which must happen before the packaging migrator parses `setup.py` to generate `pyproject.toml`.
- **Phase 6 (audit) after modification phases**: The audit should detect issues in already-migrated code to catch anything the other phases missed.

## How the Python migrator works

The Python migrator (`import_migrator.py`) uses libcst's `VisitorBasedCodemodCommand` pattern:

1. **`visit_ImportFrom()`** -- Walks import statements and records which imported names need renaming at usage sites.
2. **`leave_SimpleStatementLine()`** -- Rewrites import statements. If names move to different modules, the import is split into multiple statements.
3. **`leave_Name()`** -- At each identifier reference, checks if it was imported from an old module and renames it.

The migrator runs in a subprocess to ensure clean module state for each file.

## String replacement strategy

ZCML, GenericSetup XML, page templates, and Bootstrap migrations use simple string replacement. Replacements are sorted longest-first to prevent partial matches (e.g., `Products.CMFPlone.interfaces.controlpanel.IEditingSchema` is replaced before `Products.CMFPlone.interfaces`).

## Packaging migrator internals

The packaging migrator (`packaging_migrator.py`) parses `setup.py` using Python's `ast` module -- it never executes `setup.py`. It statically evaluates common patterns like `read()` helpers, string concatenation, and `str.join()` to extract metadata. `setup.cfg` is parsed with `configparser`. The output is generated using `tomlkit` to preserve formatting when merging into an existing `pyproject.toml`.
