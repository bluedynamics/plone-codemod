# Changelog

## 1.0.0a4 (unreleased)

- Warn about non-boilerplate `MANIFEST.in` rules that may need manual
  porting to `[tool.hatch.build]` configuration.
  [jensens]

## 1.0.0a3 (2026-02-28)

- Strip `License ::` classifiers from generated `pyproject.toml` when a
  PEP 639 license expression is present. setuptools >= 78 rejects having both.
  [jensens]

- Remove `check-manifest` hook from `.pre-commit-config.yaml` when
  `MANIFEST.in` is deleted during packaging migration.
  [jensens]

## 1.0.0a2 (2026-02-28)

- Add Phase 7: Namespace package migration (PEP 420, `--namespaces`).
  Removes `pkg_resources`/`pkgutil` namespace declarations from
  `__init__.py` files, cleans `namespace_packages` from
  `setup.py`/`setup.cfg`.
  [jensens]

- Add Phase 8: Packaging migration (`--packaging`).
  Converts `setup.py`/`setup.cfg` to PEP 621 `pyproject.toml`
  with hatchling build backend.  Includes tool config conversion
  (flake8/isort/pycodestyle to ruff, pytest, coverage sections).
  [jensens]

- Handle common `long_description` patterns in `setup.py` parsing:
  `read()` helpers, `.format()`, string concatenation,
  `str.join()`, and f-strings with file reads.
  [jensens]

- Add `CONTRIBUTORS` to recognized doc-filename whitelist.
  [jensens]

- Fix namespace migration searching in wrong directory when
  `--project-dir` differs from source dir.
  [jensens]

- Use hatch-vcs for dynamic versioning from git tags.
  [jensens]

## 1.0.0a1 (2025-05-01)

- Initial release: automated Plone 5.2 to 6.x code migration tool.
  [jensens]

- Phase 1: Python import migration via libcst codemods.
  [jensens]

- Phase 2: ZCML dotted-name migration.
  [jensens]

- Phase 3: GenericSetup XML migration.
  [jensens]

- Phase 4: Page template migration.
  [jensens]

- Phase 5: Bootstrap 3 to 5 migration (opt-in via `--bootstrap`).
  [jensens]

- Phase 6: Audit via semgrep rules (35+ detection rules).
  [jensens]
