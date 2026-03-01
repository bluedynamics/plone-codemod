# plone-codemod

<!-- diataxis: landing -->

Automated code migration tool for upgrading Plone add-ons and projects from Plone 5.2 to Plone 6.x.

Unlike simple `sed`/`find` scripts, plone-codemod uses [libcst](https://github.com/Instagram/LibCST) (a concrete syntax tree parser) to correctly handle multi-line imports, aliased imports, mixed imports, and scoped usage-site renaming.

**Key capabilities:**

- Rewrites 129+ Python import paths and renames usage sites
- Updates ZCML dotted names and GenericSetup XML
- Migrates page templates (`here/` to `context/`, `main_template` to `@@main_template`)
- Bootstrap 3 to 5 CSS class and data-attribute migration (opt-in)
- PEP 420 namespace package migration (opt-in)
- `setup.py`/`setup.cfg` to PEP 621 `pyproject.toml` conversion (opt-in)
- 35+ semgrep audit rules for issues that need manual attention

**Requirements:** Python 3.12+

## Documentation

::::{grid} 2
:gutter: 3

:::{grid-item-card} Tutorials
:link: tutorials/index
:link-type: doc

**Learning-oriented** -- Step-by-step lessons to build skills.

*Start here if you are new to plone-codemod.*
:::

:::{grid-item-card} How-To Guides
:link: how-to/index
:link-type: doc

**Goal-oriented** -- Solutions to specific problems.

*Use these when you need to accomplish something.*
:::

:::{grid-item-card} Reference
:link: reference/index
:link-type: doc

**Information-oriented** -- All options and formats documented.

*Consult when you need detailed information.*
:::

:::{grid-item-card} Explanation
:link: explanation/index
:link-type: doc

**Understanding-oriented** -- Architecture and design decisions.

*Read to deepen your understanding of how it works.*
:::

::::

## Quick Start

```bash
# Install
pip install plone-codemod

# Preview what would change
plone-codemod /path/to/your/src/ --dry-run

# Apply all default migrations
plone-codemod /path/to/your/src/

# Full modernization
plone-codemod /path/to/your/src/ --namespaces --packaging
```

After running, review changes with `git diff` and commit.

```{toctree}
---
maxdepth: 3
caption: Documentation
titlesonly: true
hidden: true
---
tutorials/index
how-to/index
reference/index
explanation/index
```
