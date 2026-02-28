"""Tests for the libcst-based Python import migrator."""
import pytest

from codemods.import_migrator import transform_code


class TestSimpleImportMigration:
    """Test single import statement migrations."""

    def test_safe_unicode_to_safe_text(self):
        before = "from Products.CMFPlone.utils import safe_unicode\n"
        after = transform_code(before)
        assert after == "from plone.base.utils import safe_text\n"

    def test_safe_encode_to_safe_bytes(self):
        before = "from Products.CMFPlone.utils import safe_encode\n"
        after = transform_code(before)
        assert after == "from plone.base.utils import safe_bytes\n"

    def test_getNavigationRoot_module_and_name(self):
        before = "from Products.CMFPlone.browser.navtree import getNavigationRoot\n"
        after = transform_code(before)
        assert after == "from plone.base.navigationroot import get_navigation_root\n"

    def test_getNavigationRoot_alt_import(self):
        before = "from plone.app.layout.navigation.root import getNavigationRoot\n"
        after = transform_code(before)
        assert after == "from plone.base.navigationroot import get_navigation_root\n"

    def test_getNavigationRootObject(self):
        before = "from plone.app.layout.navigation.root import getNavigationRootObject\n"
        after = transform_code(before)
        assert after == "from plone.base.navigationroot import get_navigation_root_object\n"

    def test_INavigationRoot(self):
        before = "from plone.app.layout.navigation.interfaces import INavigationRoot\n"
        after = transform_code(before)
        assert after == "from plone.base.interfaces.siteroot import INavigationRoot\n"

    def test_IPloneSiteRoot(self):
        before = "from Products.CMFPlone.interfaces import IPloneSiteRoot\n"
        after = transform_code(before)
        assert after == "from plone.base.interfaces import IPloneSiteRoot\n"

    def test_safeToInt_rename(self):
        before = "from Products.CMFPlone.utils import safeToInt\n"
        after = transform_code(before)
        assert after == "from plone.base.utils import safe_int\n"

    def test_getEmptyTitle_rename(self):
        before = "from Products.CMFPlone.utils import getEmptyTitle\n"
        after = transform_code(before)
        assert after == "from plone.base.utils import get_empty_title\n"

    def test_createObjectByType_rename(self):
        before = "from Products.CMFPlone.utils import _createObjectByType\n"
        after = transform_code(before)
        assert after == "from plone.base.utils import unrestricted_construct_instance\n"

    def test_language_schema_special_case(self):
        """ILanguageSchema goes to plone.i18n, NOT plone.base."""
        before = "from Products.CMFPlone.interfaces.controlpanel import ILanguageSchema\n"
        after = transform_code(before)
        assert after == "from plone.i18n.interfaces import ILanguageSchema\n"

    def test_PloneMessageFactory(self):
        before = "from Products.CMFPlone import PloneMessageFactory\n"
        after = transform_code(before)
        assert "plone.base" in after
        assert "PloneMessageFactory" in after

    def test_directlyProvides_to_zope(self):
        before = "from Products.CMFPlone.utils import directlyProvides\n"
        after = transform_code(before)
        assert after == "from zope.interface import directlyProvides\n"

    def test_name_unchanged_module_changes(self):
        """Names that don't change should still get new module path."""
        before = "from Products.CMFPlone.utils import safe_hasattr\n"
        after = transform_code(before)
        assert after == "from plone.base.utils import safe_hasattr\n"

    def test_dexterity_schema_move(self):
        before = "from plone.dexterity.utils import portalTypeToSchemaName\n"
        after = transform_code(before)
        assert after == "from plone.dexterity.schema import portalTypeToSchemaName\n"


class TestMixedImports:
    """Test imports with multiple names, some migrating, some not."""

    def test_mixed_same_destination(self):
        """Both names migrate to the same new module."""
        before = "from Products.CMFPlone.utils import safe_unicode, base_hasattr\n"
        after = transform_code(before)
        assert "from plone.base.utils import" in after
        assert "safe_text" in after
        assert "base_hasattr" in after

    def test_all_names_migrate_same_module(self):
        before = "from Products.CMFPlone.utils import safe_unicode, safe_encode\n"
        after = transform_code(before)
        assert "from plone.base.utils import" in after
        assert "safe_text" in after
        assert "safe_bytes" in after

    def test_mixed_different_destinations(self):
        """Names that migrate to different new modules produce multiple imports."""
        before = "from Products.CMFPlone.utils import safe_unicode, directlyProvides\n"
        after = transform_code(before)
        assert "from plone.base.utils import safe_text" in after
        assert "from zope.interface import directlyProvides" in after


class TestAliasedImports:
    """Test that aliased imports are preserved correctly."""

    def test_alias_preserved(self):
        before = "from Products.CMFPlone.utils import safe_unicode as su\n"
        after = transform_code(before)
        assert "safe_text as su" in after
        assert "plone.base.utils" in after

    def test_alias_with_module_change(self):
        before = "from plone.app.layout.navigation.root import getNavigationRoot as gnr\n"
        after = transform_code(before)
        assert "get_navigation_root as gnr" in after
        assert "plone.base.navigationroot" in after


class TestUsageSiteRenaming:
    """Test that function/class usage sites are renamed correctly."""

    def test_function_call_renamed(self):
        before = (
            "from Products.CMFPlone.utils import safe_unicode\n"
            "\n"
            "x = safe_unicode(value)\n"
        )
        after = transform_code(before)
        assert "safe_text(value)" in after
        assert "safe_unicode" not in after

    def test_multiple_usage_sites(self):
        before = (
            "from Products.CMFPlone.utils import safe_unicode\n"
            "\n"
            "a = safe_unicode(x)\n"
            "b = safe_unicode(y)\n"
        )
        after = transform_code(before)
        assert after.count("safe_text") == 3  # import + 2 usages

    def test_usage_not_renamed_when_aliased(self):
        """When imported with alias, usage sites keep the alias (no rename)."""
        before = (
            "from Products.CMFPlone.utils import safe_unicode as su\n"
            "\n"
            "x = su(value)\n"
        )
        after = transform_code(before)
        # The alias 'su' should still work
        assert "su(value)" in after

    def test_getNavigationRoot_call_renamed(self):
        before = (
            "from plone.app.layout.navigation.root import getNavigationRoot\n"
            "\n"
            "root = getNavigationRoot(context)\n"
        )
        after = transform_code(before)
        assert "get_navigation_root(context)" in after
        assert "plone.base.navigationroot" in after

    def test_no_rename_without_import(self):
        """Names not imported from old modules should not be renamed."""
        before = (
            "from mypackage import safe_unicode\n"
            "\n"
            "x = safe_unicode(value)\n"
        )
        after = transform_code(before)
        # Should be unchanged
        assert after == before


class TestStarImports:
    """Test star import handling."""

    def test_star_import_module_rename(self):
        before = "from Products.CMFPlone.utils import *\n"
        after = transform_code(before)
        assert "from plone.base.utils import *" in after


class TestNoMigrationNeeded:
    """Test that code without old imports is unchanged."""

    def test_already_migrated(self):
        before = "from plone.base.utils import safe_text\n"
        after = transform_code(before)
        assert after == before

    def test_unrelated_import(self):
        before = "from os.path import join\n"
        after = transform_code(before)
        assert after == before

    def test_no_imports(self):
        before = "x = 1\ny = 2\n"
        after = transform_code(before)
        assert after == before


class TestEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_multiline_import(self):
        before = (
            "from Products.CMFPlone.utils import (\n"
            "    safe_unicode,\n"
            "    base_hasattr,\n"
            ")\n"
        )
        after = transform_code(before)
        assert "safe_text" in after
        assert "base_hasattr" in after
        assert "plone.base.utils" in after

    def test_preserves_other_code(self):
        before = (
            "import os\n"
            "from Products.CMFPlone.utils import safe_unicode\n"
            "import sys\n"
            "\n"
            "x = safe_unicode('hello')\n"
        )
        after = transform_code(before)
        assert "import os" in after
        assert "import sys" in after
        assert "safe_text('hello')" in after

    def test_realistic_plone_view(self):
        """Full realistic Plone view migration."""
        before = (
            "from Products.CMFPlone.utils import safe_unicode\n"
            "from plone.app.layout.navigation.root import getNavigationRoot\n"
            "from plone.app.layout.navigation.interfaces import INavigationRoot\n"
            "from Products.CMFPlone.interfaces import IPloneSiteRoot\n"
            "\n"
            "\n"
            "def my_view(context, request):\n"
            "    root = getNavigationRoot(context)\n"
            "    text = safe_unicode(context.title)\n"
            "    return text\n"
        )
        after = transform_code(before)

        # All old imports gone
        assert "Products.CMFPlone" not in after
        assert "plone.app.layout.navigation" not in after

        # New imports present
        assert "from plone.base.utils import safe_text" in after
        assert "from plone.base.navigationroot import get_navigation_root" in after
        assert "from plone.base.interfaces.siteroot import INavigationRoot" in after
        assert "from plone.base.interfaces import IPloneSiteRoot" in after

        # Usage sites renamed
        assert "get_navigation_root(context)" in after
        assert "safe_text(context.title)" in after
