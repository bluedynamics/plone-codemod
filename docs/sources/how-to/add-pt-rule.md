# Add a Page Template Replacement

<!-- diataxis: how-to -->

Page template replacements are simple string substitutions applied to `.pt` files.

## 1. Edit `migration_config.yaml`

Add an entry to the `pagetemplates` section:

```yaml
pagetemplates:
  # ...existing entries...

  - old: "old/pattern"
    new: "new/pattern"
```

Patterns are matched as literal strings, not regexes. Order does not matter; longer patterns are matched first.

## 2. Add a test

Add a test case to `tests/test_pt_migrator.py`:

```python
def test_my_pt_replacement(self):
    before = '<div tal:define="x old/pattern">'
    expected = '<div tal:define="x new/pattern">'
    result = migrate_pt_content(before, self.config)
    self.assertEqual(result, expected)
```

## 3. Run the tests

```bash
uv run pytest tests/test_pt_migrator.py -v
```
