# Add a ZCML / GenericSetup Replacement

<!-- diataxis: how-to -->

Dotted-name replacements in ZCML and GenericSetup XML files are derived automatically from the `imports` section of `migration_config.yaml`. If you have already added an import mapping (see {doc}`add-import-rule`), the ZCML and XML phases will pick it up automatically.

## View name replacements

To add a GenericSetup view name replacement (e.g., a removed default view), add an entry to the `genericsetup.view_replacements` section:

```yaml
genericsetup:
  view_replacements:
    # ...existing entries...
    old_view_name: new_view_name
```

## Test

```bash
uv run pytest tests/test_zcml_migrator.py -v
```

If your replacement needs a dedicated test, add a test case to `tests/test_zcml_migrator.py` following the existing pattern.
