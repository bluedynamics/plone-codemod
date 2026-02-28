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

**Page templates** (string replacement):
- `context/main_template` → `context/@@main_template` (acquisition → browser view)
- `here/` → `context/` (deprecated alias)
- `prefs_main_template` → `@@prefs_main_template`

**Bootstrap 3 → 5** (opt-in via `--bootstrap`):
- `data-toggle` → `data-bs-toggle` (and 17 other data attributes)
- CSS class renames: `pull-right` → `float-end`, `panel` → `card`, `btn-default` → `btn-secondary`, etc.
- Plone-specific overrides: `plone-btn` → `btn`, etc.

**Audit** (semgrep, optional):
- 35+ rules to detect deprecated imports, removed skin scripts, portal_properties usage, Bootstrap 3 patterns, and more
- Use in CI to prevent regressions

**Namespace packages → PEP 420** (opt-in via `--namespaces`):
- Removes `__import__('pkg_resources').declare_namespace(__name__)` declarations
- Removes `pkgutil.extend_path` declarations
- Deletes namespace-only `__init__.py` files (or edits them if they contain other code)
- Cleans `namespace_packages` from `setup.py` and `setup.cfg`

**setup.py → pyproject.toml** (opt-in via `--packaging`):
- Parses `setup.py` (AST-based) and `setup.cfg` (configparser-based)
- Generates PEP 621 compliant `pyproject.toml` with hatchling build backend
- Converts tool configs: `[flake8]`/`[isort]`/`[pycodestyle]` → `[tool.ruff.*]`, `[tool:pytest]` → `[tool.pytest.ini_options]`, coverage sections, etc.
- Strips `setuptools` from runtime dependencies, normalizes license strings to SPDX
- Merges into existing `pyproject.toml` if present (preserves `[tool.ruff]` etc.)
- Deletes `setup.py`, `setup.cfg`, `MANIFEST.in` after migration

## Installation

```bash
pip install plone-codemod

# Or with uv
uv pip install plone-codemod

# Optional: for audit phase
pip install plone-codemod[audit]
```

## Usage

```bash
# Preview what would change (no files modified)
plone-codemod /path/to/your/src/ --dry-run

# Apply all migrations (without Bootstrap)
plone-codemod /path/to/your/src/

# Include Bootstrap 3→5 migration
plone-codemod /path/to/your/src/ --bootstrap

# Preview Bootstrap changes
plone-codemod /path/to/your/src/ --bootstrap --dry-run

# Run only specific phases
plone-codemod /path/to/your/src/ --skip-python     # ZCML + XML + PT only
plone-codemod /path/to/your/src/ --skip-zcml        # Python + XML + PT only
plone-codemod /path/to/your/src/ --skip-pt          # Skip page templates
plone-codemod /path/to/your/src/ --skip-audit       # Skip semgrep audit

# Use a custom config
plone-codemod /path/to/your/src/ --config my_config.yaml

# Packaging modernization (opt-in)
plone-codemod /path/to/your/src/ --namespaces                 # PEP 420 namespace migration
plone-codemod /path/to/your/src/ --packaging                  # setup.py → pyproject.toml
plone-codemod /path/to/your/src/ --namespaces --packaging     # Both (recommended)
plone-codemod /path/to/your/src/ --packaging --project-dir .  # Explicit project root
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

String replacement of dotted names in `.zcml` files:

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

### Phase 4: Page templates

Safe automated fixes for `.pt` files:

```xml
<!-- Before -->
<html metal:use-macro="context/main_template/macros/master">
<div tal:define="x here/title">

<!-- After -->
<html metal:use-macro="context/@@main_template/macros/master">
<div tal:define="x context/title">
```

### Phase 5: Bootstrap 3 → 5 (opt-in)

Only runs when `--bootstrap` is passed. Handles data attributes and CSS classes:

```html
<!-- Before -->
<button data-toggle="modal" data-target="#m" class="btn btn-default pull-right">
<div class="panel panel-default"><div class="panel-body">...</div></div>

<!-- After -->
<button data-bs-toggle="modal" data-bs-target="#m" class="btn btn-secondary float-end">
<div class="card"><div class="card-body">...</div></div>
```

Bootstrap migration is opt-in because some projects intentionally keep Bootstrap 3 for parts of their UI.

### Phase 7: Namespace packages → PEP 420 (opt-in)

Only runs when `--namespaces` is passed. Converts old-style namespace packages to PEP 420 implicit namespace packages:

```
# Before: src/plone/__init__.py
__import__('pkg_resources').declare_namespace(__name__)

# After: src/plone/__init__.py is DELETED (PEP 420 — no __init__.py needed)
```

Handles:
- `__import__('pkg_resources').declare_namespace(__name__)` (pkg_resources style)
- `try/except ImportError` wrappers around the above
- `from pkgutil import extend_path` + `__path__ = extend_path(...)` (pkgutil style)
- Nested namespaces (e.g., both `plone/` and `plone/app/`)
- Mixed files (namespace declaration removed, other code preserved)
- Cleans `namespace_packages` from `setup.py` and `setup.cfg`

### Phase 8: setup.py → pyproject.toml (opt-in)

Only runs when `--packaging` is passed. Converts `setup.py`/`setup.cfg` to a PEP 621 compliant `pyproject.toml` with hatchling build backend:

```toml
# Generated pyproject.toml
[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"

[project]
name = "plone.app.something"
dynamic = ["version"]
description = "A Plone addon"
readme = "README.rst"
license = "GPL-2.0-only"
requires-python = ">=3.8"
dependencies = ["plone.api>=2.0", "zope.interface"]

[project.entry-points."z3c.autoinclude.plugin"]
target = "plone"

[tool.hatch.build.targets.wheel]
packages = ["src/plone"]

[tool.hatch.version]
source = "vcs"
```

Tool config conversion (from `setup.cfg`):
- `[flake8]` → `[tool.ruff.lint]`
- `[isort]` → `[tool.ruff.lint.isort]`
- `[pycodestyle]`/`[pep8]` → `[tool.ruff.lint]`
- `[tool:pytest]` → `[tool.pytest.ini_options]`
- `[coverage:run]`/`[coverage:report]` → `[tool.coverage.*]`
- `[bdist_wheel]` — dropped (PEP 517 handles this)

Use `--project-dir` to specify the project root if it's not the parent of `source_dir`.

### Phase 6: Audit (optional)

Runs semgrep rules to detect issues that need manual attention:

```bash
# Standalone semgrep usage
semgrep --config semgrep_rules/ /path/to/your/src/
```

Detects: deprecated imports, removed skin scripts (`queryCatalog`, `getFolderContents`, `pretty_title_or_id`), `portal_properties` usage, `checkPermission` builtin in templates, `getIcon`, `normalizeString`, glyphicons, Bootstrap 3 patterns, and more.

## Migration config

All mappings live in `migration_config.yaml`. To add a new migration rule, add an entry:

```yaml
imports:
  - old: old.module.path.OldName
    new: new.module.path.NewName
```

The tool splits on the last `.` to determine module vs name.

### Coverage

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
| Page template patterns | 5 |
| Bootstrap data attributes | 17 |
| Bootstrap CSS class renames | 30+ |

### What it does NOT cover (manual migration needed)

- **Archetypes removal** — AT content types must be migrated to Dexterity before upgrading
- **`getFolderContents()`** → `restrictedTraverse("@@contentlisting")()` (method call rewrite, flagged by semgrep)
- **`queryCatalog`** removal (flagged by semgrep)
- **`portal_properties`** removal (flagged by semgrep — needs registry migration)
- **Removed skin scripts** in TAL expressions (flagged by semgrep)
- **`getViewTemplateId`** deprecation (flagged by semgrep)
- **Buildout → pip/mxdev** migration (different config format, use [mxdev](https://github.com/mxstack/mxdev))
- **Python 2 cleanup** (`six`, `__future__`, `u""` strings) — use [pyupgrade](https://github.com/asottile/pyupgrade) for this
- **Resource registry / LESS** changes (complete rewrite needed)
- **Glyphicons** → Bootstrap Icons / SVG (flagged by semgrep)
- **Dynamic imports** (`importlib.import_module("Products.CMFPlone.utils")`)

## Development

```bash
# Clone and install in dev mode
git clone https://github.com/bluedynamics/plone-codemod.git
cd plone-codemod
uv venv && uv pip install -e ".[dev]"

# Run tests
uv run pytest tests/ -v

# Lint
uvx ruff check .
uvx ruff format --check .
```

## Architecture

```
plone-codemod/
  src/plone_codemod/
    cli.py                       # Orchestrator with all phases and CLI flags
    import_migrator.py           # libcst codemod: Python imports + usage sites
    zcml_migrator.py             # ZCML + GenericSetup XML transformer
    pt_migrator.py               # Page template + Bootstrap migrator
    namespace_migrator.py        # PEP 420 namespace package migration
    packaging_migrator.py        # setup.py → pyproject.toml migration
    migration_config.yaml        # Declarative old→new mapping (YAML)
    semgrep_rules/
      plone6_deprecated.yaml     # 35+ audit/detection rules
  tests/
    test_import_migrator.py      # 32 tests for Python migration
    test_zcml_migrator.py        # 17 tests for ZCML/XML migration
    test_pt_migrator.py          # 24 tests for PT + Bootstrap migration
    test_namespace_migrator.py   # 47 tests for namespace migration
    test_packaging_migrator.py   # 48 tests for packaging migration
```
## Source Code and Contributions

The source code is managed in a Git repository, with its main branches hosted on GitHub.
Issues can be reported there too.

We'd be happy to see many forks and pull requests to make this tool even better.
We welcome AI-assisted contributions, but expect every contributor to fully understand and be able to explain the code they submit.
Please don't send bulk auto-generated pull requests.

Maintainers are Jens Klein, Johannes Raggam and the BlueDynamics Alliance developer team.
We appreciate any contribution and if a release on PyPI is needed, please just contact one of us.
We also offer commercial support if any training, coaching, integration or adaptations are needed.

## License

GPL-2.0 — same as Plone.
