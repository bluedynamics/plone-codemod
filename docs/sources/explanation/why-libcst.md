# Why libcst Instead of sed/regex

<!-- diataxis: explanation -->

Many migration guides suggest using `sed` or `find ... -exec sed` to rewrite imports. plone-codemod uses [libcst](https://github.com/Instagram/LibCST) instead. Here is why.

## The problem with text-based replacement

Consider this import:

```python
from Products.CMFPlone.utils import (
    safe_unicode,
    base_hasattr,
    directlyProvides,
)
```

A `sed` command to replace `Products.CMFPlone.utils` with `plone.base.utils` would produce:

```python
from plone.base.utils import (
    safe_unicode,
    base_hasattr,
    directlyProvides,
)
```

This is wrong: `directlyProvides` moved to `zope.interface`, not `plone.base.utils`. And `safe_unicode` was renamed to `safe_text`, but `sed` does not know about usage sites.

## What libcst does differently

libcst parses Python into a **concrete syntax tree** -- like an AST but preserving whitespace, comments, and formatting. This allows plone-codemod to:

1. **Inspect each imported name individually** -- even within a multi-name import statement.

2. **Split imports** when names move to different modules:

   ```python
   # Before
   from Products.CMFPlone.utils import safe_unicode, directlyProvides

   # After
   from plone.base.utils import safe_text
   from zope.interface import directlyProvides
   ```

3. **Track which names come from which module** so usage sites are only renamed when the name was actually imported from the old location:

   ```python
   from Products.CMFPlone.utils import safe_unicode
   from my.package import safe_unicode as my_safe_unicode

   text = safe_unicode(value)       # Renamed to safe_text(value)
   other = my_safe_unicode(value)   # Left alone
   ```

4. **Preserve aliases**:

   ```python
   from Products.CMFPlone.utils import safe_unicode as su
   # → from plone.base.utils import safe_text as su
   ```

## Trade-offs

libcst is slower than `sed` and adds a dependency. But for a migration that runs once per project, correctness matters more than speed. A single wrong rename can introduce a subtle bug that takes hours to debug.

## The hybrid approach

plone-codemod uses libcst only for Python files where correctness is critical. For ZCML, GenericSetup XML, and page templates, simple string replacement is sufficient and fast -- these formats do not have the same scoping and aliasing concerns as Python.
