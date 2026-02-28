"""Tests for the page template and Bootstrap migrators."""
import pytest
from pathlib import Path
import tempfile

from templates.pt_migrator import (
    migrate_pt_content,
    migrate_bootstrap_content,
    migrate_pt_files,
    migrate_bootstrap_files,
    load_config,
)


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def pt_replacements(config):
    return config.get("pagetemplates", [])


@pytest.fixture
def bs_data_attrs(config):
    return config.get("bootstrap", {}).get("data_attributes", [])


@pytest.fixture
def bs_css_classes(config):
    return config.get("bootstrap", {}).get("css_classes", [])


class TestPageTemplateMigration:
    """Test safe page template fixes."""

    def test_main_template_acquisition_to_view(self, pt_replacements):
        before = '<html metal:use-macro="context/main_template/macros/master">'
        after = migrate_pt_content(before, pt_replacements)
        assert "context/@@main_template/macros/master" in after
        assert "context/main_template/macros" not in after

    def test_here_main_template_to_view(self, pt_replacements):
        before = '<html metal:use-macro="here/main_template/macros/master">'
        after = migrate_pt_content(before, pt_replacements)
        assert "context/@@main_template/macros/master" in after

    def test_prefs_main_template(self, pt_replacements):
        before = '<html metal:use-macro="context/prefs_main_template/macros/master">'
        after = migrate_pt_content(before, pt_replacements)
        assert "context/@@prefs_main_template/macros/master" in after

    def test_here_prefs_main_template(self, pt_replacements):
        before = '<html metal:use-macro="here/prefs_main_template/macros/master">'
        after = migrate_pt_content(before, pt_replacements)
        assert "context/@@prefs_main_template/macros/master" in after

    def test_here_to_context(self, pt_replacements):
        before = 'tal:define="items here/getFolderContents"'
        after = migrate_pt_content(before, pt_replacements)
        assert "context/getFolderContents" in after
        assert "here/" not in after

    def test_already_uses_view_adapter(self, pt_replacements):
        before = '<html metal:use-macro="context/@@main_template/macros/master">'
        after = migrate_pt_content(before, pt_replacements)
        assert after == before

    def test_preserves_unrelated_content(self, pt_replacements):
        before = '<div tal:content="view/title">Title</div>'
        after = migrate_pt_content(before, pt_replacements)
        assert after == before

    def test_multiple_replacements_in_one_file(self, pt_replacements):
        before = """<html metal:use-macro="context/main_template/macros/master">
<body>
  <div tal:define="x here/title">
    <span tal:content="here/description" />
  </div>
</body>
</html>"""
        after = migrate_pt_content(before, pt_replacements)
        assert "context/@@main_template" in after
        assert "context/title" in after
        assert "context/description" in after
        assert "here/" not in after


class TestBootstrapMigration:
    """Test Bootstrap 3→5 migration."""

    def test_data_toggle(self, bs_data_attrs, bs_css_classes):
        before = '<button data-toggle="modal" data-target="#myModal">'
        after = migrate_bootstrap_content(before, bs_data_attrs, bs_css_classes)
        assert 'data-bs-toggle="modal"' in after
        assert 'data-bs-target="#myModal"' in after
        assert "data-toggle=" not in after
        assert "data-target=" not in after

    def test_data_dismiss(self, bs_data_attrs, bs_css_classes):
        before = '<button data-dismiss="modal">'
        after = migrate_bootstrap_content(before, bs_data_attrs, bs_css_classes)
        assert 'data-bs-dismiss="modal"' in after

    def test_pull_right_to_float_end(self, bs_data_attrs, bs_css_classes):
        before = '<div class="pull-right">'
        after = migrate_bootstrap_content(before, bs_data_attrs, bs_css_classes)
        assert "float-end" in after
        assert "pull-right" not in after

    def test_pull_left_to_float_start(self, bs_data_attrs, bs_css_classes):
        before = '<div class="pull-left">'
        after = migrate_bootstrap_content(before, bs_data_attrs, bs_css_classes)
        assert "float-start" in after

    def test_btn_default_to_secondary(self, bs_data_attrs, bs_css_classes):
        before = '<button class="btn btn-default">'
        after = migrate_bootstrap_content(before, bs_data_attrs, bs_css_classes)
        assert "btn-secondary" in after
        assert "btn-default" not in after

    def test_img_responsive_to_fluid(self, bs_data_attrs, bs_css_classes):
        before = '<img class="img-responsive">'
        after = migrate_bootstrap_content(before, bs_data_attrs, bs_css_classes)
        assert "img-fluid" in after

    def test_panel_to_card(self, bs_data_attrs, bs_css_classes):
        before = '<div class="panel panel-default"><div class="panel-heading">H</div><div class="panel-body">B</div></div>'
        after = migrate_bootstrap_content(before, bs_data_attrs, bs_css_classes)
        assert "card" in after
        assert "card-header" in after
        assert "card-body" in after
        assert "panel-default" not in after
        assert "panel-heading" not in after
        assert "panel-body" not in after

    def test_hidden_xs(self, bs_data_attrs, bs_css_classes):
        before = '<div class="hidden-xs">'
        after = migrate_bootstrap_content(before, bs_data_attrs, bs_css_classes)
        assert "d-none d-sm-block" in after

    def test_plone_btn_classes(self, bs_data_attrs, bs_css_classes):
        before = '<a class="plone-btn plone-btn-primary">'
        after = migrate_bootstrap_content(before, bs_data_attrs, bs_css_classes)
        assert "btn " in after
        assert "btn-primary" in after
        assert "plone-btn" not in after

    def test_no_change_when_nothing_matches(self, bs_data_attrs, bs_css_classes):
        before = '<div class="my-custom-class">Content</div>'
        after = migrate_bootstrap_content(before, bs_data_attrs, bs_css_classes)
        assert after == before

    def test_data_ride_carousel(self, bs_data_attrs, bs_css_classes):
        before = '<div data-ride="carousel">'
        after = migrate_bootstrap_content(before, bs_data_attrs, bs_css_classes)
        assert 'data-bs-ride="carousel"' in after


class TestFileOperations:
    """Test file-level migration operations."""

    def test_migrate_pt_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pt_file = root / "myview.pt"
            pt_file.write_text(
                '<html metal:use-macro="context/main_template/macros/master">'
            )

            modified = migrate_pt_files(root)
            assert len(modified) == 1
            content = pt_file.read_text()
            assert "context/@@main_template" in content

    def test_migrate_pt_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            original = '<html metal:use-macro="context/main_template/macros/master">'
            pt_file = root / "myview.pt"
            pt_file.write_text(original)

            modified = migrate_pt_files(root, dry_run=True)
            assert len(modified) == 1
            assert pt_file.read_text() == original  # NOT changed

    def test_migrate_bootstrap_only_with_flag(self):
        """Bootstrap migration only runs when explicitly called."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pt_file = root / "myview.pt"
            pt_file.write_text('<button data-toggle="modal">')

            # PT migration should NOT touch data-toggle
            modified_pt = migrate_pt_files(root)
            assert len(modified_pt) == 0

            # Bootstrap migration SHOULD fix it
            modified_bs = migrate_bootstrap_files(root)
            assert len(modified_bs) == 1
            assert "data-bs-toggle" in pt_file.read_text()

    def test_migrate_bootstrap_html_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            html_file = root / "index.html"
            html_file.write_text('<div class="pull-right">Content</div>')

            modified = migrate_bootstrap_files(root)
            assert len(modified) == 1
            assert "float-end" in html_file.read_text()

    def test_no_changes_needed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pt_file = root / "modern.pt"
            pt_file.write_text(
                '<html metal:use-macro="context/@@main_template/macros/master">'
            )

            modified = migrate_pt_files(root)
            assert len(modified) == 0
