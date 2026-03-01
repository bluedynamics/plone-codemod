# plone-codemod

Automated code migration tool for upgrading Plone add-ons and projects from Plone 5.2 to Plone 6.x.

Unlike simple `sed`/`find` scripts, plone-codemod uses [libcst](https://github.com/Instagram/LibCST) (a concrete syntax tree parser) to correctly handle multi-line imports, aliased imports, mixed imports, and scoped usage-site renaming.

**What it covers:**

- 129+ Python import rewrites with usage-site renaming
- ZCML dotted-name updates
- GenericSetup XML interface and view replacements
- Page template fixes (`here/` to `context/`, `main_template` to `@@main_template`)
- Bootstrap 3 to 5 migration (opt-in)
- PEP 420 namespace package migration (opt-in)
- `setup.py`/`setup.cfg` to PEP 621 `pyproject.toml` conversion (opt-in)
- 35+ semgrep audit rules for issues needing manual attention

## Installation

```bash
pip install plone-codemod

# Or with uv
uv pip install plone-codemod

# Optional: for audit phase
pip install plone-codemod[audit]
```

## Quick Start

```bash
# Preview what would change (no files modified)
plone-codemod /path/to/your/src/ --dry-run

# Apply all default migrations
plone-codemod /path/to/your/src/

# Include Bootstrap 3 to 5
plone-codemod /path/to/your/src/ --bootstrap

# Full modernization (namespace packages + pyproject.toml)
plone-codemod /path/to/your/src/ --namespaces --packaging
```

After running, review changes with `git diff` and commit.

## Documentation

Full documentation: **https://bluedynamics.github.io/plone-codemod/**

- [Tutorial: Migrate your first add-on](https://bluedynamics.github.io/plone-codemod/tutorials/migrate-your-addon.html)
- [CLI Reference](https://bluedynamics.github.io/plone-codemod/reference/cli.html)
- [Configuration Format](https://bluedynamics.github.io/plone-codemod/reference/config-format.html)
- [How to contribute new rules](https://bluedynamics.github.io/plone-codemod/how-to/add-import-rule.html)

## Development

```bash
git clone https://github.com/bluedynamics/plone-codemod.git
cd plone-codemod
uv venv && uv pip install -e ".[dev]"
uv run pytest tests/ -v
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

GPL-2.0 -- same as Plone.
