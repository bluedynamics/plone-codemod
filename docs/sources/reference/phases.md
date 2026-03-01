# Migration Phases

<!-- diataxis: reference -->

plone-codemod runs up to 8 sequential phases. Phases 1-4 and 6 are enabled by default; phases 5, 7, and 8 are opt-in.

## Phase 1: Python Import Migration

**Module:** `import_migrator.py` (libcst-based)
**Skip:** `--skip-python`

Rewrites Python import statements and renames usage sites using libcst's concrete syntax tree.

**Capabilities:**
- Rewrites 129+ import paths
- Renames functions at usage sites when the name changed
- Splits mixed imports when names move to different modules
- Preserves aliases, comments, and formatting
- Handles multi-line imports correctly

```python
# Before
from Products.CMFPlone.utils import safe_unicode, base_hasattr
from Products.CMFPlone.utils import directlyProvides

# After
from plone.base.utils import safe_text, base_hasattr
from zope.interface import directlyProvides
```

**Files affected:** `*.py`

## Phase 2: ZCML Migration

**Module:** `zcml_migrator.py`
**Skip:** `--skip-zcml`

String replacement of dotted names in ZCML attributes (`class=`, `for=`, `provides=`, `interface=`, `layer=`, `handler=`, etc.).

```xml
<!-- Before -->
<browser:page for="plone.app.layout.navigation.interfaces.INavigationRoot" />

<!-- After -->
<browser:page for="plone.base.interfaces.siteroot.INavigationRoot" />
```

Replacements are derived from the `imports` section of `migration_config.yaml`, sorted longest-first to avoid partial matches.

**Files affected:** `*.zcml`

## Phase 3: GenericSetup XML Migration

**Module:** `zcml_migrator.py`
**Skip:** `--skip-xml`

Updates interface references and view names in GenericSetup profile XML files.

```xml
<!-- Before -->
<records interface="Products.CMFPlone.interfaces.controlpanel.IEditingSchema">
<property name="default_view">folder_summary_view</property>

<!-- After -->
<records interface="plone.base.interfaces.controlpanel.IEditingSchema">
<property name="default_view">folder_listing</property>
```

**Files affected:** `*.xml` in `profiles/` directories

## Phase 4: Page Template Migration

**Module:** `pt_migrator.py`
**Skip:** `--skip-pt`

Safe string replacements in page templates:

- `context/main_template` to `context/@@main_template` (acquisition to browser view)
- `here/` to `context/` (deprecated alias)
- `prefs_main_template` to `@@prefs_main_template`

**Files affected:** `*.pt`

## Phase 5: Bootstrap 3 to 5 Migration

**Module:** `pt_migrator.py`
**Enable:** `--bootstrap`

Opt-in because some projects intentionally keep Bootstrap 3 for parts of their UI.

- 17 data attribute renames (`data-toggle=` to `data-bs-toggle=`, etc.)
- 30+ CSS class renames (`pull-right` to `float-end`, `panel` to `card`, etc.)
- Plone-specific overrides (`plone-btn` to `btn`, etc.)

```html
<!-- Before -->
<button data-toggle="modal" class="btn btn-default pull-right">

<!-- After -->
<button data-bs-toggle="modal" class="btn btn-secondary float-end">
```

**Files affected:** `*.pt`, `*.html`

## Phase 6: Audit

**Module:** `semgrep_rules/plone6_deprecated.yaml`
**Skip:** `--skip-audit`

Runs 35+ semgrep rules to detect issues that need manual attention. See {doc}`semgrep-rules` for the full list.

**Requires:** `pip install plone-codemod[audit]` (installs semgrep)

## Phase 7: Namespace Package Migration

**Module:** `namespace_migrator.py`
**Enable:** `--namespaces`

Converts old-style namespace packages (`pkg_resources` / `pkgutil`) to PEP 420 implicit namespace packages.

- Removes `__import__('pkg_resources').declare_namespace(__name__)` declarations
- Removes `try/except ImportError` wrappers around the above
- Removes `from pkgutil import extend_path` + `__path__ = extend_path(...)` patterns
- Deletes namespace-only `__init__.py` files (preserves mixed files)
- Cleans `namespace_packages` from `setup.py` and `setup.cfg`

**Files affected:** `__init__.py` files in namespace package directories, `setup.py`, `setup.cfg`

## Phase 8: Packaging Migration

**Module:** `packaging_migrator.py`
**Enable:** `--packaging`

Converts `setup.py` / `setup.cfg` to a PEP 621 compliant `pyproject.toml` with hatchling build backend.

- Parses `setup.py` using AST (does not execute it)
- Parses `setup.cfg` using configparser
- Generates `pyproject.toml` with `hatchling` and `hatch-vcs`
- Converts tool configs:
  - `[flake8]` / `[isort]` / `[pycodestyle]` to `[tool.ruff.*]`
  - `[tool:pytest]` to `[tool.pytest.ini_options]`
  - `[coverage:*]` to `[tool.coverage.*]`
- Strips `setuptools` from runtime dependencies
- Normalizes license strings to SPDX
- Merges into existing `pyproject.toml` if present
- Removes `check-manifest` from `.pre-commit-config.yaml`
- Deletes `setup.py`, `setup.cfg`, `MANIFEST.in` after migration

**Important:** Run Phase 7 before Phase 8 (`--namespaces --packaging`) so `namespace_packages` is cleaned before `pyproject.toml` generation.

**Files affected:** `setup.py`, `setup.cfg`, `MANIFEST.in` (deleted), `pyproject.toml` (created/updated), `.pre-commit-config.yaml`
