"""Tests for the ZCML and GenericSetup XML migrator."""
import pytest
from pathlib import Path
import tempfile

from zcml.zcml_migrator import (
    migrate_zcml_content,
    migrate_genericsetup_content,
    migrate_zcml_files,
    migrate_genericsetup_files,
    _build_replacements,
    load_config,
)


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def zcml_replacements(config):
    return _build_replacements(config.get("zcml", []))


@pytest.fixture
def gs_replacements(config):
    gs_config = config.get("genericsetup", {})
    return _build_replacements(gs_config.get("dotted_names", []))


@pytest.fixture
def view_replacements(config):
    return config.get("genericsetup", {}).get("view_replacements")


class TestZCMLMigration:
    """Test ZCML dotted name replacements."""

    def test_INavigationRoot_in_for_attribute(self, zcml_replacements):
        before = '<adapter for="plone.app.layout.navigation.interfaces.INavigationRoot" />'
        after = migrate_zcml_content(before, zcml_replacements)
        assert 'plone.base.interfaces.siteroot.INavigationRoot' in after
        assert 'plone.app.layout.navigation' not in after

    def test_IPatternsSettings_in_provides(self, zcml_replacements):
        before = '<adapter provides="Products.CMFPlone.interfaces.IPatternsSettings" />'
        after = migrate_zcml_content(before, zcml_replacements)
        assert 'plone.base.interfaces.patterns.IPatternsSettings' in after

    def test_controlpanel_prefix(self, zcml_replacements):
        before = '<record interface="Products.CMFPlone.interfaces.controlpanel.IEditingSchema" />'
        after = migrate_zcml_content(before, zcml_replacements)
        assert 'plone.base.interfaces.controlpanel.IEditingSchema' in after

    def test_language_schema_special_case(self, zcml_replacements):
        before = '<record interface="Products.CMFPlone.interfaces.controlpanel.ILanguageSchema" />'
        after = migrate_zcml_content(before, zcml_replacements)
        assert 'plone.i18n.interfaces.ILanguageSchema' in after

    def test_multiple_replacements_in_one_file(self, zcml_replacements):
        before = """<configure>
    <adapter
        for="plone.app.layout.navigation.interfaces.INavigationRoot"
        provides="Products.CMFPlone.interfaces.IPatternsSettings"
        factory=".patterns.MyPatterns" />
    <adapter
        for="plone.app.layout.navigation.interfaces.INavigationRoot"
        factory=".other.OtherAdapter" />
</configure>"""
        after = migrate_zcml_content(before, zcml_replacements)
        assert after.count('plone.base.interfaces.siteroot.INavigationRoot') == 2
        assert 'plone.base.interfaces.patterns.IPatternsSettings' in after

    def test_no_change_when_nothing_matches(self, zcml_replacements):
        before = '<adapter for="my.custom.IMyInterface" />'
        after = migrate_zcml_content(before, zcml_replacements)
        assert after == before

    def test_preserves_xml_structure(self, zcml_replacements):
        before = """<configure xmlns="http://namespaces.zope.org/zope"
           xmlns:browser="http://namespaces.zope.org/browser">
    <browser:page
        name="myview"
        for="plone.app.layout.navigation.interfaces.INavigationRoot"
        class=".views.MyView"
        permission="zope2.View"
        />
</configure>"""
        after = migrate_zcml_content(before, zcml_replacements)
        assert 'xmlns="http://namespaces.zope.org/zope"' in after
        assert 'class=".views.MyView"' in after
        assert 'permission="zope2.View"' in after


class TestGenericSetupMigration:
    """Test GenericSetup XML replacements."""

    def test_registry_interface_replacement(self, gs_replacements, view_replacements):
        before = """<registry>
  <records interface="Products.CMFPlone.interfaces.controlpanel.IEditingSchema" prefix="plone">
    <value key="visible_ids">True</value>
  </records>
</registry>"""
        after = migrate_genericsetup_content(before, gs_replacements, view_replacements)
        assert 'plone.base.interfaces.controlpanel.IEditingSchema' in after
        assert 'Products.CMFPlone' not in after

    def test_folder_summary_view_replacement(self, gs_replacements, view_replacements):
        before = """<object name="Folder">
  <property name="default_view">folder_summary_view</property>
</object>"""
        after = migrate_genericsetup_content(before, gs_replacements, view_replacements)
        assert ">folder_listing<" in after
        assert "folder_summary_view" not in after

    def test_view_in_attribute(self, gs_replacements, view_replacements):
        before = '<element value="folder_summary_view" />'
        after = migrate_genericsetup_content(before, gs_replacements, view_replacements)
        assert '"folder_listing"' in after

    def test_folder_tabular_view_replacement(self, gs_replacements, view_replacements):
        before = '<element value="folder_tabular_view" />'
        after = migrate_genericsetup_content(before, gs_replacements, view_replacements)
        assert '"folder_listing"' in after

    def test_atct_album_view_replacement(self, gs_replacements, view_replacements):
        before = '<element value="atct_album_view" />'
        after = migrate_genericsetup_content(before, gs_replacements, view_replacements)
        assert '"folder_listing"' in after

    def test_no_change_when_nothing_matches(self, gs_replacements, view_replacements):
        before = '<records interface="my.custom.IMySchema" />'
        after = migrate_genericsetup_content(before, gs_replacements, view_replacements)
        assert after == before


class TestFileOperations:
    """Test file-level migration operations."""

    def test_migrate_zcml_files_in_directory(self, config):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            zcml_file = root / "configure.zcml"
            zcml_file.write_text(
                '<adapter for="plone.app.layout.navigation.interfaces.INavigationRoot" />'
            )

            modified = migrate_zcml_files(root)
            assert len(modified) == 1
            content = zcml_file.read_text()
            assert "plone.base.interfaces.siteroot.INavigationRoot" in content

    def test_migrate_zcml_dry_run(self, config):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            original = '<adapter for="plone.app.layout.navigation.interfaces.INavigationRoot" />'
            zcml_file = root / "configure.zcml"
            zcml_file.write_text(original)

            modified = migrate_zcml_files(root, dry_run=True)
            assert len(modified) == 1
            # File should NOT be changed in dry run
            assert zcml_file.read_text() == original

    def test_migrate_genericsetup_files_in_profiles(self, config):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles = root / "profiles" / "default"
            profiles.mkdir(parents=True)
            xml_file = profiles / "registry.xml"
            xml_file.write_text(
                '<records interface="Products.CMFPlone.interfaces.controlpanel.IEditingSchema" />'
            )

            modified = migrate_genericsetup_files(root)
            assert len(modified) == 1
            content = xml_file.read_text()
            assert "plone.base.interfaces.controlpanel.IEditingSchema" in content

    def test_skips_non_profile_xml(self, config):
        """XML files outside profiles/ directories should be skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xml_file = root / "random.xml"
            xml_file.write_text(
                '<records interface="Products.CMFPlone.interfaces.controlpanel.IEditingSchema" />'
            )

            modified = migrate_genericsetup_files(root)
            assert len(modified) == 0
