# plone-codemod

Automated code migration tool for upgrading Plone add-ons and projects from Plone 5.2 to Plone 6.x.

Unlike simple `sed`/`find` scripts, plone-codemod uses [libcst](https://github.com/Instagram/LibCST) (a concrete syntax tree parser) to correctly handle multi-line imports, aliased imports, mixed imports, and scoped usage-site renaming.

## What it does

**Python files** (libcst-based, AST-aware):
- Rewrites 129+ import paths (`Products.CMFPlone.*` → `plone.base.*`, etc.)
- Renames functions at usage sites (`safe_unicode()` → `safe_text()`, `getNavigationRoot()` → `get_navigation_root()`, etc.)
- Splits mixed imports when names move to different modules
- Preserves aliases, comments, and formatting

**ZCML files** (string replacement):
- Updates dotted names in `class=`, `for=`, `provides=`, `interface=` and other attributes

**GenericSetup XML** (string replacement):
- Updates interface references in `registry.xml` and profile XML
- Replaces removed view names (`folder_summary_view` → `folder_listing`, etc.)

**Audit** (semgrep, optional):
- 18 rules to detect remaining deprecated imports, function calls, and string references
- Use in CI to prevent regressions

## Installation

```bash
pip install libcst pyyaml

# Optional: for audit phase
pip install semgrep
```

## Usage

```bash
cd plone-codemod

# Preview what would change (no files modified)
python runner.py /path/to/your/src/ --dry-run

# Apply all migrations
python runner.py /path/to/your/src/

# Run only specific phases
python runner.py /path/to/your/src/ --skip-python     # ZCML + XML only
python runner.py /path/to/your/src/ --skip-zcml        # Python + XML only
python runner.py /path/to/your/src/ --skip-xml          # Python + ZCML only
python runner.py /path/to/your/src/ --skip-audit        # Skip semgrep audit

# Use a custom config
python runner.py /path/to/your/src/ --config my_config.yaml
```

After running, review changes with `git diff` and commit.

## How it works

### Phase 1: Python imports (libcst)

The codemod reads `migration_config.yaml` and rewrites import statements using libcst's concrete syntax tree. This means it correctly handles cases that `sed` cannot:

```python
# Multi-line imports
from Products.CMFPlone.utils import (
    safe_unicode,      # → safe_text
    base_hasattr,      # stays, module path updated
)

# Aliased imports (alias preserved)
from Products.CMFPlone.utils import safe_unicode as su
# → from plone.base.utils import safe_text as su

# Mixed imports split when destinations differ
from Products.CMFPlone.utils import safe_unicode, directlyProvides
# → from plone.base.utils import safe_text
# → from zope.interface import directlyProvides

# Usage sites renamed only when imported from the old module
text = safe_unicode(value)  # → safe_text(value)
```

### Phase 2: ZCML migration

Simple string replacement of dotted names in `.zcml` files:

```xml
<!-- Before -->
<browser:page for="plone.app.layout.navigation.interfaces.INavigationRoot" />

<!-- After -->
<browser:page for="plone.base.interfaces.siteroot.INavigationRoot" />
```

### Phase 3: GenericSetup XML

Updates `registry.xml` and type profile XML files:

```xml
<!-- Before -->
<records interface="Products.CMFPlone.interfaces.controlpanel.IEditingSchema">
<property name="default_view">folder_summary_view</property>

<!-- After -->
<records interface="plone.base.interfaces.controlpanel.IEditingSchema">
<property name="default_view">folder_listing</property>
```

### Phase 4: Audit (optional)

Runs semgrep rules to find anything the automated migration missed:

```bash
# Standalone semgrep usage
semgrep --config semgrep_rules/ /path/to/your/src/
```

## Migration config

All mappings live in `migration_config.yaml`. To add a new migration rule, add an entry:

```yaml
imports:
  - old: old.module.path.OldName
    new: new.module.path.NewName
```

The tool splits on the last `.` to determine module vs name.

### Coverage

The config covers:

| Category | Count |
|----------|-------|
| `Products.CMFPlone.utils` → `plone.base.utils` | 18 functions |
| `Products.CMFPlone.interfaces` → `plone.base.interfaces` | 60+ interfaces |
| Control panel interfaces | 20+ |
| TinyMCE interfaces | 5 |
| Navigation root functions | 3 |
| Syndication interfaces | 4 |
| `plone.dexterity.utils` → `plone.dexterity.schema` | 4 |
| Message factory, batch, permissions, defaultpage, i18n | 10+ |
| Special case: `ILanguageSchema` → `plone.i18n` | 1 |

### What it does NOT cover (manual migration needed)

- **Archetypes removal** — AT content types must be migrated to Dexterity before upgrading
- **`getFolderContents()`** → `restrictedTraverse("@@contentlisting")()` (method call rewrite, flagged by semgrep)
- **`queryCatalog`** removal (flagged by semgrep)
- **`getViewTemplateId`** deprecation (flagged by semgrep)
- **Buildout → pip/mxdev** migration (different config format)
- **Python 2 cleanup** (`six`, `__future__`, `u""` strings) — use [pyupgrade](https://github.com/asottile/pyupgrade) for this
- **Resource registry / LESS** changes
- **Dynamic imports** (`importlib.import_module("Products.CMFPlone.utils")`)

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

## Architecture

```
plone-codemod/
  migration_config.yaml         # Declarative old→new mapping (YAML)
  codemods/
    import_migrator.py           # libcst codemod: Python imports + usage sites
  zcml/
    zcml_migrator.py             # ZCML + GenericSetup XML transformer
  semgrep_rules/
    plone6_deprecated.yaml       # CI audit rules
  runner.py                      # Orchestrator with --dry-run
  tests/
    test_import_migrator.py      # 32 tests for Python migration
    test_zcml_migrator.py        # 17 tests for ZCML/XML migration
```

## License

GPL-2.0 — same as Plone.
