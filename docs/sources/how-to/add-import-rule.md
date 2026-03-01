# Add a Python Import Migration Rule

<!-- diataxis: how-to -->

This guide shows how to contribute a new import mapping to plone-codemod.

## 1. Edit `migration_config.yaml`

Open `src/plone_codemod/migration_config.yaml` and add an entry to the `imports` section.

Each entry needs a fully-qualified `old` name and a fully-qualified `new` name:

```yaml
imports:
  # ...existing entries...

  - old: some.old.module.SomeClass
    new: some.new.module.SomeClass
```

The tool splits on the last `.` to determine the module path and the imported name.

**Same name, different module** -- only the import path changes:

```yaml
- old: Products.CMFPlone.utils.base_hasattr
  new: plone.base.utils.base_hasattr
```

**Different name** -- usage sites are also renamed throughout the file:

```yaml
- old: Products.CMFPlone.utils.safe_unicode
  new: plone.base.utils.safe_text
```

## 2. Add a test

Open `tests/test_import_migrator.py` and add a test case. Follow the existing pattern:

```python
def test_my_new_migration(self):
    before = textwrap.dedent("""\
        from some.old.module import SomeClass

        obj = SomeClass()
    """)
    expected = textwrap.dedent("""\
        from some.new.module import SomeClass

        obj = SomeClass()
    """)
    result = transform_code(before, self.config_path)
    self.assertEqual(result, expected)
```

## 3. Run the tests

```bash
uv run pytest tests/test_import_migrator.py -v
```

## 4. Submit a pull request

Fork the repository, commit your changes, and open a pull request. Include the Plone version where the import moved and a link to the relevant Plone changelog or pull request if available.
