# Migrate Your First Add-on

<!-- diataxis: tutorial -->

In this tutorial we walk through migrating a Plone 5.2 add-on to Plone 6.x using plone-codemod. By the end you will have a working migration workflow you can apply to any package.

## Prerequisites

- A Plone add-on with its source in a git repository
- Python 3.12+
- The add-on should already be committed so you can review changes with `git diff`

## 1. Install plone-codemod

```bash
pip install plone-codemod

# Or with uv
uv pip install plone-codemod
```

If you want the audit phase (semgrep rules), install with the extra:

```bash
pip install plone-codemod[audit]
```

## 2. Preview the migration

Always start with `--dry-run` to see what would change without modifying any files:

```bash
plone-codemod /path/to/your/src/ --dry-run
```

You will see output like:

```
Plone 5.2 → 6.x Migration Tool
Source: /path/to/your/src
Config: .../migration_config.yaml
Mode: DRY RUN (no files will be modified)

=== Phase 1: Python import migration (libcst) ===
  [DRY RUN] Would modify: src/my/addon/browser/views.py
  [DRY RUN] Would modify: src/my/addon/setuphandlers.py

=== Phase 2: ZCML migration ===
  [DRY RUN] Would modify: src/my/addon/browser/configure.zcml

...
```

Review the list of files that would be modified.

## 3. Run the migration

When you are ready, run without `--dry-run`:

```bash
plone-codemod /path/to/your/src/
```

## 4. Review the changes

Use `git diff` to inspect every change:

```bash
git diff
```

Look for:
- Import paths updated correctly
- Usage sites renamed (e.g., `safe_unicode()` to `safe_text()`)
- ZCML dotted names updated
- Page template `here/` replaced with `context/`

## 5. Run Bootstrap migration (if needed)

If your add-on uses Bootstrap 3 templates, run with the `--bootstrap` flag:

```bash
plone-codemod /path/to/your/src/ --bootstrap
```

Review the changes again with `git diff`.

## 6. Modernize packaging (optional)

To convert namespace packages and `setup.py` to modern standards:

```bash
plone-codemod /path/to/your/src/ --namespaces --packaging
```

This removes old-style namespace declarations and generates a PEP 621 `pyproject.toml`.

## 7. Review audit findings

If you installed with `[audit]`, the semgrep phase will have printed warnings about issues that need manual attention. These are things the tool cannot auto-fix:

- `getFolderContents()` calls (removed in Plone 6)
- `queryCatalog` usage (removed)
- `portal_properties` references (needs registry migration)
- Glyphicon usage (needs Bootstrap Icons)

Address these manually based on the messages.

## 8. Commit

Once you are satisfied with the changes:

```bash
git add -A
git commit -m "Migrate to Plone 6.x using plone-codemod"
```

## What's next

- See {doc}`../reference/phases` for details on each migration phase
- See {doc}`../how-to/run-selective-phases` to run only specific phases
- See {doc}`../explanation/architecture` for how the tool works internally
