# Run Selective Migration Phases

<!-- diataxis: how-to -->

plone-codemod runs 8 phases. By default, phases 1-4 and 6 are enabled. You can skip default phases or opt into additional ones.

## Skip phases

```bash
# Skip Python import migration (only ZCML + XML + PT + audit)
plone-codemod ./src/ --skip-python

# Skip the semgrep audit
plone-codemod ./src/ --skip-audit

# Only run Python imports
plone-codemod ./src/ --skip-zcml --skip-xml --skip-pt --skip-audit
```

## Enable opt-in phases

```bash
# Bootstrap 3 to 5 migration
plone-codemod ./src/ --bootstrap

# PEP 420 namespace packages
plone-codemod ./src/ --namespaces

# setup.py to pyproject.toml
plone-codemod ./src/ --packaging

# Full modernization (recommended order)
plone-codemod ./src/ --namespaces --packaging
```

## Preview before applying

Always preview first with `--dry-run`:

```bash
plone-codemod ./src/ --dry-run
plone-codemod ./src/ --bootstrap --dry-run
plone-codemod ./src/ --namespaces --packaging --dry-run
```

## Phase order

Phases always run in a fixed order regardless of flag position. Phase 7 (namespaces) always runs before Phase 8 (packaging) so that `namespace_packages` is cleaned from `setup.py` before `pyproject.toml` generation.

See {doc}`../reference/phases` for details on each phase.
