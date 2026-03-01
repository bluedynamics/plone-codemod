# Semgrep Audit Rules

<!-- diataxis: reference -->

The audit phase (Phase 6) runs 35+ semgrep rules to detect issues that cannot be auto-fixed and need manual attention. Install with `pip install plone-codemod[audit]`.

Rules are defined in `src/plone_codemod/semgrep_rules/plone6_deprecated.yaml`.

## Deprecated Imports (ERROR)

| Rule ID | Pattern | Replacement |
|---------|---------|-------------|
| `plone6-deprecated-cmfplone-utils-import` | `from Products.CMFPlone.utils import ...` | `plone.base.utils` |
| `plone6-deprecated-cmfplone-interfaces-import` | `from Products.CMFPlone.interfaces import ...` | `plone.base.interfaces` |
| `plone6-deprecated-cmfplone-interfaces-cp-import` | `from Products.CMFPlone.interfaces.controlpanel import ...` | `plone.base.interfaces.controlpanel` |
| `plone6-deprecated-navtree-import` | `from Products.CMFPlone.browser.navtree import ...` | `plone.base.navigationroot` |
| `plone6-deprecated-navigation-root-import` | `from plone.app.layout.navigation.root import ...` | `plone.base.navigationroot` |
| `plone6-deprecated-navigation-interfaces-import` | `from plone.app.layout.navigation.interfaces import INavigationRoot` | `plone.base.interfaces.siteroot` |
| `plone6-deprecated-plonebatch-import` | `from Products.CMFPlone.PloneBatch import ...` | `plone.base.batch` |
| `plone6-deprecated-message-factory-import` | `from Products.CMFPlone import PloneMessageFactory` | `plone.base.PloneMessageFactory` |

## Deprecated Function Calls (WARNING)

| Rule ID | Pattern | Replacement |
|---------|---------|-------------|
| `plone6-deprecated-safe-unicode-call` | `safe_unicode(...)` | `safe_text()` from `plone.base.utils` |
| `plone6-deprecated-getNavigationRoot-call` | `getNavigationRoot(...)` | `get_navigation_root()` from `plone.base.navigationroot` |
| `plone6-deprecated-getNavigationRootObject-call` | `getNavigationRootObject(...)` | `get_navigation_root_object()` |
| `plone6-deprecated-safeToInt-call` | `safeToInt(...)` | `safe_int()` from `plone.base.utils` |
| `plone6-deprecated-getEmptyTitle-call` | `getEmptyTitle(...)` | `get_empty_title()` from `plone.base.utils` |

## Removed APIs (ERROR)

| Rule ID | Pattern | Replacement |
|---------|---------|-------------|
| `plone6-removed-getFolderContents` | `obj.getFolderContents(...)` | `obj.restrictedTraverse("@@contentlisting")()` |
| `plone6-removed-queryCatalog` | `obj.queryCatalog(...)` | `plone.api.content.find()` or direct catalog queries |
| `plone6-deprecated-getViewTemplateId` | `obj.getViewTemplateId(...)` | `@@plone_context_state` `view_template_id()` |

## ZCML / GenericSetup XML (WARNING)

| Rule ID | Pattern | Files |
|---------|---------|-------|
| `plone6-zcml-deprecated-cmfplone-ref` | `Products.CMFPlone` | `*.zcml` |
| `plone6-xml-deprecated-cmfplone-ref` | `Products.CMFPlone` | `*/profiles/*/*.xml`, `**/registry.xml` |
| `plone6-zcml-deprecated-navigation-interfaces` | `plone.app.layout.navigation.interfaces.INavigationRoot` | `*.zcml` |

## Page Template Issues

| Rule ID | Pattern | Severity | Fix |
|---------|---------|----------|-----|
| `plone6-pt-main-template-no-view` | `context/main_template/macros` | ERROR | Use `context/@@main_template/macros/master` |
| `plone6-pt-here-main-template` | `here/main_template/macros` | ERROR | Use `context/@@main_template/macros/master` |
| `plone6-pt-portal-properties` | `portal_properties` | ERROR | Use `plone.app.registry` |
| `plone6-pt-site-properties` | `site_properties` | ERROR | Use `plone.app.registry` |
| `plone6-pt-pretty-title-or-id` | `pretty_title_or_id` | WARNING | Use `context/Title` |
| `plone6-pt-queryCatalog` | `queryCatalog` | ERROR | Use `plone.api.content.find()` |
| `plone6-pt-getFolderContents` | `getFolderContents` | ERROR | Use `@@contentlisting` |
| `plone6-pt-getIcon` | `getIcon` | WARNING | Use `@@iconresolver` |
| `plone6-pt-normalizeString` | `normalizeString` | WARNING | Use `plone.i18n.normalizer` |
| `plone6-pt-checkPermission-builtin` | `checkPermission(` | WARNING | Use `@@plone_context_state/is_editable` |
| `plone6-pt-prefs-main-template-no-view` | `context/prefs_main_template/macros` | ERROR | Use `context/@@prefs_main_template/macros/master` |
| `plone6-pt-plone-utils-acquisition` | `plone_utils` | WARNING | Use `plone.api` or a view method |
| `plone6-pt-modules-pythonscripts` | `Products.PythonScripts.standard` | WARNING | Use Python stdlib |

## Bootstrap 3 Detection (WARNING)

| Rule ID | Pattern | Files | Fix |
|---------|---------|-------|-----|
| `plone6-bs3-glyphicon` | `glyphicon` | `*.pt`, `*.html` | Use Bootstrap Icons or `@@iconresolver` |
| `plone6-bs3-data-toggle` | `data-toggle=` | `*.pt`, `*.html` | Run with `--bootstrap` to auto-fix |
| `plone6-bs3-panel-class` | `panel-default` | `*.pt`, `*.html` | Run with `--bootstrap` to auto-fix |

## Standalone Usage

You can run the semgrep rules independently:

```bash
semgrep --config src/plone_codemod/semgrep_rules/ /path/to/your/src/
```
