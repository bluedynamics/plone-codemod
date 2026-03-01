# Add a Semgrep Audit Rule

<!-- diataxis: how-to -->

Semgrep rules detect issues that cannot be auto-fixed and need manual attention. They run in Phase 6 (Audit).

## 1. Edit the rules file

Open `src/plone_codemod/semgrep_rules/plone6_deprecated.yaml` and add a new rule.

### Python pattern

```yaml
rules:
  # ...existing rules...

  - id: plone6-my-new-rule
    languages: [python]
    pattern: deprecated_function($...ARGS)
    message: >
      deprecated_function() was removed in Plone 6.
      Use new_function() instead.
    severity: ERROR
```

### Template / generic pattern

For `.pt`, `.html`, `.zcml`, or `.xml` files, use `languages: [generic]` with a `paths` filter:

```yaml
  - id: plone6-pt-my-pattern
    languages: [generic]
    pattern: some_deprecated_pattern
    paths:
      include:
        - "*.pt"
    message: >
      some_deprecated_pattern is removed in Plone 6.
      Use the_replacement instead.
    severity: WARNING
```

## 2. Severity levels

`ERROR`
: Removed APIs that will break at runtime.

`WARNING`
: Deprecated patterns that still work but should be updated.

## 3. Test

Run semgrep manually against a test file to verify your rule matches:

```bash
semgrep --config src/plone_codemod/semgrep_rules/plone6_deprecated.yaml /path/to/test/file
```

Then run the full test suite:

```bash
uv run pytest tests/ -v
```
