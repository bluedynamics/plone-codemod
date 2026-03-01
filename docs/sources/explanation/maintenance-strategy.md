# Maintenance Strategy

<!-- diataxis: explanation -->

This page explains how plone-codemod stays current as Plone evolves -- a question raised by the community.

## Declarative rules, not hardcoded logic

All migration mappings live in `migration_config.yaml`, not in Python code. Adding a new import migration, ZCML replacement, or Bootstrap class rename means adding a YAML entry -- no code changes needed. This keeps contributions simple and reviewable.

## Versioned configurations

The config file includes a `version` field (currently `"5.2-to-6.2"`) that documents which migration path it covers. As Plone releases new versions with further API changes, new entries are added to the same file or a new config file can be created for a different version range.

## Contributing new rules

The project welcomes pull requests to extend the rule set. Each rule type has a dedicated how-to guide:

- {doc}`../how-to/add-import-rule`
- {doc}`../how-to/add-zcml-rule`
- {doc}`../how-to/add-pt-rule`
- {doc}`../how-to/add-bootstrap-rule`
- {doc}`../how-to/add-semgrep-rule`

The workflow is: add a YAML entry, add a test, run the tests, submit a PR.

## The semgrep safety net

Not every deprecated API can be auto-fixed. The semgrep audit rules (Phase 6) act as a safety net: they detect patterns that need manual attention and print actionable messages. When a new API is deprecated in Plone but cannot be migrated automatically, adding a semgrep rule ensures users are at least warned about it.

## Custom configurations

Projects with non-standard needs can use `--config` to supply their own `migration_config.yaml`. This allows teams to maintain project-specific rules without waiting for upstream changes.

## Release process

Releases are fully automated via GitHub Actions and trusted publishing:

1. **Every push to `main`** runs QA (ruff, ty) and tests (Python 3.12-3.14). If both pass, the package is built and published to [test.pypi.org](https://test.pypi.org/project/plone-codemod/) as a dev version.

2. **To release to PyPI**, a maintainer creates a GitHub Release:
   - Tag the release (the version is derived from the git tag via `hatch-vcs`)
   - Create and publish the release on GitHub
   - CI automatically runs QA + tests, builds the package, and publishes to [pypi.org](https://pypi.org/project/plone-codemod/)

3. **Pull requests and branches** run QA + tests but do not publish anything.

No manual PyPI credentials or `twine upload` are needed -- the pipeline uses PyPI trusted publishing (OIDC).

If you need a release, contact the maintainers (Jens Klein, Johannes Raggam, BlueDynamics Alliance) or open an issue.
