# Configuration Format

<!-- diataxis: reference -->

All migration rules are defined in `migration_config.yaml`. The bundled config ships with the package and covers Plone 5.2 to 6.2. You can supply your own via `--config`.

## Top-Level Structure

```yaml
version: "5.2-to-6.2"

imports:
  - old: old.module.OldName
    new: new.module.NewName

genericsetup:
  view_replacements:
    old_view_name: new_view_name

pagetemplates:
  - old: "old pattern"
    new: "new pattern"

bootstrap:
  data_attributes:
    - old: "data-old="
      new: "data-new="
  css_classes:
    - old: "old-class"
      new: "new-class"

python2_cleanup:
  - pattern: "from __future__ import"
    action: remove_line
```

## Sections

### `imports`

A list of Python import migrations. Each entry has:

`old`
: Fully-qualified name in the old location (e.g., `Products.CMFPlone.utils.safe_unicode`).

`new`
: Fully-qualified name in the new location (e.g., `plone.base.utils.safe_text`).

The tool splits on the last `.` to determine module vs. name. When `old_name != new_name`, all usage sites in the file are also renamed.

```yaml
imports:
  # Module path changes, name stays the same
  - old: Products.CMFPlone.utils.base_hasattr
    new: plone.base.utils.base_hasattr

  # Module path AND name change — usages are renamed too
  - old: Products.CMFPlone.utils.safe_unicode
    new: plone.base.utils.safe_text
```

### `genericsetup`

#### `view_replacements`

A mapping of old view names to new view names, applied in GenericSetup XML profile files.

```yaml
genericsetup:
  view_replacements:
    folder_summary_view: folder_listing
    folder_tabular_view: folder_listing
    folder_full_view: folder_listing
    atct_album_view: folder_listing
```

Dotted-name replacements in GenericSetup XML are derived automatically from the `imports` section.

### `pagetemplates`

A list of string replacements applied to `.pt` files.

```yaml
pagetemplates:
  - old: "context/main_template/macros/master"
    new: "context/@@main_template/macros/master"

  - old: "here/"
    new: "context/"
```

### `bootstrap`

Only applied when `--bootstrap` is passed.

#### `data_attributes`

String replacements for HTML data attributes.

```yaml
bootstrap:
  data_attributes:
    - old: "data-toggle="
      new: "data-bs-toggle="
```

#### `css_classes`

String replacements for CSS class names.

```yaml
bootstrap:
  css_classes:
    - old: "pull-right"
      new: "float-end"
    - old: "panel panel-default"
      new: "card"
```

### `python2_cleanup`

Listed for completeness. These patterns are better handled by [pyupgrade](https://github.com/asottile/pyupgrade) and are not processed by plone-codemod.

## Bundled Config Coverage

| Category | Count |
|----------|-------|
| `Products.CMFPlone.utils` to `plone.base.utils` | 18 functions |
| `Products.CMFPlone.interfaces` to `plone.base.interfaces` | 60+ interfaces |
| Control panel interfaces | 20+ |
| TinyMCE interfaces | 5 |
| Navigation root functions | 3 |
| Syndication interfaces | 4 |
| `plone.dexterity.utils` to `plone.dexterity.schema` | 4 |
| Message factory, batch, permissions, defaultpage, i18n | 10+ |
| Page template patterns | 5 |
| Bootstrap data attributes | 17 |
| Bootstrap CSS class renames | 30+ |
