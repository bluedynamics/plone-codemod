"""Tests for the namespace package migrator (PEP 420)."""

from pathlib import Path
from plone_codemod.namespace_migrator import clean_setup_cfg_namespaces
from plone_codemod.namespace_migrator import clean_setup_py_namespaces
from plone_codemod.namespace_migrator import find_namespace_init_files
from plone_codemod.namespace_migrator import has_namespace_declaration
from plone_codemod.namespace_migrator import is_namespace_declaration
from plone_codemod.namespace_migrator import is_only_namespace_init
from plone_codemod.namespace_migrator import migrate_namespaces
from plone_codemod.namespace_migrator import remove_namespace_declaration

import tempfile


class TestIsNamespaceDeclaration:
    """Test single-line namespace declaration detection."""

    def test_pkg_resources_single_quotes(self):
        assert is_namespace_declaration(
            "__import__('pkg_resources').declare_namespace(__name__)"
        )

    def test_pkg_resources_double_quotes(self):
        assert is_namespace_declaration(
            '__import__("pkg_resources").declare_namespace(__name__)'
        )

    def test_pkg_resources_indented(self):
        assert is_namespace_declaration(
            "    __import__('pkg_resources').declare_namespace(__name__)"
        )

    def test_pkgutil_import(self):
        assert is_namespace_declaration("from pkgutil import extend_path")

    def test_pkgutil_path_assignment(self):
        assert is_namespace_declaration(
            "__path__ = extend_path(__path__, __name__)"
        )

    def test_not_a_comment(self):
        assert not is_namespace_declaration(
            "# __import__('pkg_resources').declare_namespace(__name__)"
        )

    def test_not_blank_line(self):
        assert not is_namespace_declaration("")
        assert not is_namespace_declaration("   ")

    def test_not_regular_code(self):
        assert not is_namespace_declaration("import os")
        assert not is_namespace_declaration("x = 1")

    def test_not_regular_import(self):
        assert not is_namespace_declaration("from pathlib import Path")


class TestHasNamespaceDeclaration:
    """Test content-level namespace detection."""

    def test_detects_pkg_resources_in_content(self):
        content = "# namespace\n__import__('pkg_resources').declare_namespace(__name__)\n"
        assert has_namespace_declaration(content)

    def test_detects_pkgutil_in_content(self):
        content = "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n"
        assert has_namespace_declaration(content)

    def test_no_match_in_regular_code(self):
        content = "from importlib.metadata import version\n__version__ = version('my-pkg')\n"
        assert not has_namespace_declaration(content)

    def test_empty_content(self):
        assert not has_namespace_declaration("")

    def test_empty_init(self):
        assert not has_namespace_declaration("# empty\n")


class TestIsOnlyNamespaceInit:
    """Test whether a file contains only namespace declarations."""

    def test_only_pkg_resources(self):
        content = "__import__('pkg_resources').declare_namespace(__name__)\n"
        assert is_only_namespace_init(content)

    def test_pkg_resources_with_comment(self):
        content = "# this is a namespace package\n__import__('pkg_resources').declare_namespace(__name__)\n"
        assert is_only_namespace_init(content)

    def test_pkg_resources_with_encoding_cookie(self):
        content = "# -*- coding: utf-8 -*-\n__import__('pkg_resources').declare_namespace(__name__)\n"
        assert is_only_namespace_init(content)

    def test_try_except_wrapper(self):
        content = """\
try:
    __import__('pkg_resources').declare_namespace(__name__)
except ImportError:
    pass
"""
        assert is_only_namespace_init(content)

    def test_pkgutil_style(self):
        content = "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n"
        assert is_only_namespace_init(content)

    def test_not_only_namespace_with_real_code(self):
        content = """\
__import__('pkg_resources').declare_namespace(__name__)
from .utils import helper
"""
        assert not is_only_namespace_init(content)

    def test_not_only_namespace_with_version(self):
        content = """\
__import__('pkg_resources').declare_namespace(__name__)
__version__ = "1.0"
"""
        assert not is_only_namespace_init(content)

    def test_empty_file(self):
        assert not is_only_namespace_init("")

    def test_just_comments(self):
        assert not is_only_namespace_init("# just a comment\n")


class TestRemoveNamespaceDeclaration:
    """Test removal of namespace declarations from content."""

    def test_remove_simple_pkg_resources(self):
        content = "__import__('pkg_resources').declare_namespace(__name__)\n"
        result = remove_namespace_declaration(content)
        assert result == ""

    def test_remove_pkg_resources_preserves_other_code(self):
        content = """\
__import__('pkg_resources').declare_namespace(__name__)

from .utils import helper

__version__ = "1.0"
"""
        result = remove_namespace_declaration(content)
        assert "__import__" not in result
        assert "from .utils import helper" in result
        assert '__version__ = "1.0"' in result

    def test_remove_try_except_wrapper(self):
        content = """\
try:
    __import__('pkg_resources').declare_namespace(__name__)
except ImportError:
    pass
"""
        result = remove_namespace_declaration(content)
        assert result == ""

    def test_remove_try_except_preserves_other_code(self):
        content = """\
try:
    __import__('pkg_resources').declare_namespace(__name__)
except ImportError:
    pass

logger = logging.getLogger(__name__)
"""
        result = remove_namespace_declaration(content)
        assert "try:" not in result
        assert "except" not in result
        assert "logger = logging.getLogger(__name__)" in result

    def test_remove_pkgutil_style(self):
        content = "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n"
        result = remove_namespace_declaration(content)
        assert result == ""

    def test_remove_pkgutil_preserves_other_code(self):
        content = """\
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)

import logging
"""
        result = remove_namespace_declaration(content)
        assert "extend_path" not in result
        assert "import logging" in result

    def test_remove_with_comments_and_blanks(self):
        content = """\
# namespace package
__import__('pkg_resources').declare_namespace(__name__)
"""
        result = remove_namespace_declaration(content)
        assert "__import__" not in result
        assert "# namespace package" in result


class TestFindNamespaceInitFiles:
    """Test finding namespace __init__.py files in a project."""

    def test_find_simple_namespace_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pkg = root / "src" / "plone"
            pkg.mkdir(parents=True)
            init = pkg / "__init__.py"
            init.write_text("__import__('pkg_resources').declare_namespace(__name__)\n")

            results = find_namespace_init_files(root)
            assert len(results) == 1
            assert results[0][0] == init
            assert results[0][1] is True  # delete entirely

    def test_find_nested_namespaces(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plone_dir = root / "src" / "plone"
            plone_dir.mkdir(parents=True)
            app_dir = plone_dir / "app"
            app_dir.mkdir()

            plone_init = plone_dir / "__init__.py"
            plone_init.write_text("__import__('pkg_resources').declare_namespace(__name__)\n")
            app_init = app_dir / "__init__.py"
            app_init.write_text("__import__('pkg_resources').declare_namespace(__name__)\n")

            # Actual package init with real code
            mypkg = app_dir / "mypkg"
            mypkg.mkdir()
            mypkg_init = mypkg / "__init__.py"
            mypkg_init.write_text("__version__ = '1.0'\n")

            results = find_namespace_init_files(root)
            assert len(results) == 2
            paths = {r[0] for r in results}
            assert plone_init in paths
            assert app_init in paths
            assert mypkg_init not in paths

    def test_mixed_init_not_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pkg = root / "src" / "plone"
            pkg.mkdir(parents=True)
            init = pkg / "__init__.py"
            init.write_text(
                "__import__('pkg_resources').declare_namespace(__name__)\n"
                "__version__ = '1.0'\n"
            )

            results = find_namespace_init_files(root)
            assert len(results) == 1
            assert results[0][1] is False  # edit only, not delete

    def test_skips_egg_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            egg = root / "plone.app.something.egg-info"
            egg.mkdir(parents=True)
            init = egg / "__init__.py"
            init.write_text("__import__('pkg_resources').declare_namespace(__name__)\n")

            results = find_namespace_init_files(root)
            assert len(results) == 0

    def test_skips_build_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build = root / "build" / "lib" / "plone"
            build.mkdir(parents=True)
            init = build / "__init__.py"
            init.write_text("__import__('pkg_resources').declare_namespace(__name__)\n")

            results = find_namespace_init_files(root)
            assert len(results) == 0

    def test_no_namespace_inits(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pkg = root / "src" / "mypkg"
            pkg.mkdir(parents=True)
            init = pkg / "__init__.py"
            init.write_text("__version__ = '1.0'\n")

            results = find_namespace_init_files(root)
            assert len(results) == 0


class TestCleanSetupPyNamespaces:
    """Test removal of namespace_packages from setup.py."""

    def test_removes_namespace_packages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            setup_py = root / "setup.py"
            setup_py.write_text("""\
from setuptools import setup, find_packages
setup(
    name='plone.app.something',
    namespace_packages=['plone', 'plone.app'],
    packages=find_packages('src'),
)
""")
            assert clean_setup_py_namespaces(root)
            content = setup_py.read_text()
            assert "namespace_packages" not in content
            assert "name='plone.app.something'" in content
            assert "packages=find_packages('src')" in content

    def test_dry_run_no_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            setup_py = root / "setup.py"
            original = """\
from setuptools import setup, find_packages
setup(
    name='plone.app.something',
    namespace_packages=['plone', 'plone.app'],
)
"""
            setup_py.write_text(original)
            assert clean_setup_py_namespaces(root, dry_run=True)
            assert setup_py.read_text() == original

    def test_no_namespace_packages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            setup_py = root / "setup.py"
            setup_py.write_text("from setuptools import setup\nsetup(name='mypkg')\n")
            assert not clean_setup_py_namespaces(root)

    def test_no_setup_py(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert not clean_setup_py_namespaces(Path(tmpdir))


class TestCleanSetupCfgNamespaces:
    """Test removal of namespace_packages from setup.cfg."""

    def test_removes_namespace_packages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            setup_cfg = root / "setup.cfg"
            setup_cfg.write_text("""\
[options]
packages = find:
namespace_packages =
    plone
    plone.app
zip_safe = false
""")
            assert clean_setup_cfg_namespaces(root)
            content = setup_cfg.read_text()
            assert "namespace_packages" not in content
            assert "packages = find:" in content
            assert "zip_safe = false" in content

    def test_single_line_namespace_packages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            setup_cfg = root / "setup.cfg"
            setup_cfg.write_text("""\
[options]
namespace_packages = plone
packages = find:
""")
            assert clean_setup_cfg_namespaces(root)
            content = setup_cfg.read_text()
            assert "namespace_packages" not in content
            assert "packages = find:" in content

    def test_dry_run_no_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            setup_cfg = root / "setup.cfg"
            original = "[options]\nnamespace_packages = plone\n"
            setup_cfg.write_text(original)
            assert clean_setup_cfg_namespaces(root, dry_run=True)
            assert setup_cfg.read_text() == original

    def test_no_namespace_packages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            setup_cfg = root / "setup.cfg"
            setup_cfg.write_text("[options]\npackages = find:\n")
            assert not clean_setup_cfg_namespaces(root)


class TestMigrateNamespaces:
    """Test the full namespace migration orchestrator."""

    def test_full_migration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src = root / "src"

            # Create namespace package structure
            plone_dir = src / "plone"
            plone_dir.mkdir(parents=True)
            plone_init = plone_dir / "__init__.py"
            plone_init.write_text("__import__('pkg_resources').declare_namespace(__name__)\n")

            app_dir = plone_dir / "app"
            app_dir.mkdir()
            app_init = app_dir / "__init__.py"
            app_init.write_text("__import__('pkg_resources').declare_namespace(__name__)\n")

            pkg_dir = app_dir / "mypkg"
            pkg_dir.mkdir()
            pkg_init = pkg_dir / "__init__.py"
            pkg_init.write_text("__version__ = '1.0'\n")

            # Create setup.py
            setup_py = root / "setup.py"
            setup_py.write_text("""\
from setuptools import setup, find_packages
setup(
    name='plone.app.mypkg',
    namespace_packages=['plone', 'plone.app'],
    packages=find_packages('src'),
)
""")

            result = migrate_namespaces(root, src)

            assert len(result["deleted_files"]) == 2
            assert not plone_init.exists()
            assert not app_init.exists()
            assert pkg_init.exists()
            assert "namespace_packages" not in setup_py.read_text()

    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src = root / "src"
            plone_dir = src / "plone"
            plone_dir.mkdir(parents=True)
            plone_init = plone_dir / "__init__.py"
            plone_init.write_text("__import__('pkg_resources').declare_namespace(__name__)\n")

            result = migrate_namespaces(root, src, dry_run=True)

            assert len(result["deleted_files"]) == 1
            assert plone_init.exists()  # Not actually deleted

    def test_mixed_init_edited_not_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src = root / "src"
            plone_dir = src / "plone"
            plone_dir.mkdir(parents=True)
            plone_init = plone_dir / "__init__.py"
            plone_init.write_text(
                "__import__('pkg_resources').declare_namespace(__name__)\n"
                "logger = __import__('logging').getLogger(__name__)\n"
            )

            result = migrate_namespaces(root, src)

            assert len(result["deleted_files"]) == 0
            assert len(result["modified_files"]) == 1
            assert plone_init.exists()
            content = plone_init.read_text()
            assert "__import__('pkg_resources')" not in content
            assert "logger" in content
