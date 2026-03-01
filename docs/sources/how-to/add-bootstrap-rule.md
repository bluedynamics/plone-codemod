# Add a Bootstrap Migration Rule

<!-- diataxis: how-to -->

Bootstrap rules are applied only when `--bootstrap` is passed. There are two categories: data attribute renames and CSS class renames.

## Data attribute

Add to the `bootstrap.data_attributes` section of `migration_config.yaml`:

```yaml
bootstrap:
  data_attributes:
    # ...existing entries...
    - old: "data-example="
      new: "data-bs-example="
```

## CSS class

Add to the `bootstrap.css_classes` section:

```yaml
bootstrap:
  css_classes:
    # ...existing entries...
    - old: "old-class-name"
      new: "new-class-name"
```

CSS class replacements are matched as substrings within `class="..."` attribute values.

## Test

Add a test case to `tests/test_pt_migrator.py` and run:

```bash
uv run pytest tests/test_pt_migrator.py -v
```
