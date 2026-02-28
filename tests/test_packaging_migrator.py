"""Tests for the setup.py → pyproject.toml packaging migrator."""

from pathlib import Path
from plone_codemod.packaging_migrator import cleanup_old_files
from plone_codemod.packaging_migrator import cleanup_pre_commit_check_manifest
from plone_codemod.packaging_migrator import convert_tool_configs
from plone_codemod.packaging_migrator import generate_pyproject_toml
from plone_codemod.packaging_migrator import merge_metadata
from plone_codemod.packaging_migrator import migrate_packaging
from plone_codemod.packaging_migrator import parse_setup_cfg
from plone_codemod.packaging_migrator import parse_setup_py

import tempfile
import tomlkit


# ---------------------------------------------------------------------------
# setup.py parsing
# ---------------------------------------------------------------------------


class TestParseSetupPy:
    """Test AST-based setup.py parsing."""

    def test_simple_setup(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup
setup(
    name='my-package',
    version='1.0.0',
    description='A test package',
)
""")
        result = parse_setup_py(setup_py)
        assert result["name"] == "my-package"
        assert result["version"] == "1.0.0"
        assert result["description"] == "A test package"

    def test_variable_references(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup
VERSION = '2.0.0'
setup(
    name='my-package',
    version=VERSION,
)
""")
        result = parse_setup_py(setup_py)
        assert result["version"] == "2.0.0"

    def test_find_packages_src(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup, find_packages
setup(
    name='my-package',
    packages=find_packages('src'),
)
""")
        result = parse_setup_py(setup_py)
        assert result["packages"] == "find_packages:src"

    def test_find_packages_no_arg(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup, find_packages
setup(
    name='my-package',
    packages=find_packages(),
)
""")
        result = parse_setup_py(setup_py)
        assert result["packages"] == "find_packages:."

    def test_extras_require_dict_call(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup
setup(
    name='my-package',
    extras_require=dict(
        test=['pytest'],
        docs=['sphinx'],
    ),
)
""")
        result = parse_setup_py(setup_py)
        assert result["extras_require"] == {"test": ["pytest"], "docs": ["sphinx"]}

    def test_extras_require_dict_literal(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup
setup(
    name='my-package',
    extras_require={
        'test': ['pytest'],
    },
)
""")
        result = parse_setup_py(setup_py)
        assert result["extras_require"] == {"test": ["pytest"]}

    def test_entry_points_string_format(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup
setup(
    name='my-package',
    entry_points=\"\"\"
        [z3c.autoinclude.plugin]
        target = plone
    \"\"\",
)
""")
        result = parse_setup_py(setup_py)
        assert isinstance(result["entry_points"], str)

    def test_entry_points_dict_format(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup
setup(
    name='my-package',
    entry_points={
        'console_scripts': ['my-cmd = my_package.cli:main'],
    },
)
""")
        result = parse_setup_py(setup_py)
        assert result["entry_points"] == {
            "console_scripts": ["my-cmd = my_package.cli:main"]
        }

    def test_long_description_from_file(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup
setup(
    name='my-package',
    long_description=open('README.rst').read(),
)
""")
        result = parse_setup_py(setup_py)
        assert result["long_description"] == "__file__:README.rst"

    def test_long_description_read_helper(self, tmp_path):
        """Test read("README.rst") helper pattern."""
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
import os

def read(*rnames):
    with open(os.path.join(os.path.dirname(__file__), *rnames)) as f:
        return f.read()

from setuptools import setup
setup(
    name='my-package',
    long_description=read('README.rst'),
)
""")
        result = parse_setup_py(setup_py)
        assert result["long_description"] == "__file__:README.rst"

    def test_long_description_format_with_read(self, tmp_path):
        """Test '{}'.format(read('README'), read('CHANGES')) pattern."""
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
import os

def read(*rnames):
    with open(os.path.join(os.path.dirname(__file__), *rnames)) as f:
        return f.read()

from setuptools import setup
setup(
    name='my-package',
    long_description="{0}\\n\\n{1}".format(
        read("README.rst"),
        read("CHANGES.rst"),
    ),
)
""")
        result = parse_setup_py(setup_py)
        assert result["long_description"] == "__file__:README.rst"

    def test_long_description_concat_with_read(self, tmp_path):
        """Test read('README') + '\\n' + read('CHANGES') pattern."""
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
import os

def read(*rnames):
    with open(os.path.join(os.path.dirname(__file__), *rnames)) as f:
        return f.read()

from setuptools import setup
setup(
    name='my-package',
    long_description=read("README.rst") + "\\n\\n" + read("CHANGES.rst"),
)
""")
        result = parse_setup_py(setup_py)
        assert result["long_description"] == "__file__:README.rst"

    def test_long_description_join_pattern(self, tmp_path):
        r"""Test '\n\n'.join([open('README').read(), ...]) pattern."""
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup
setup(
    name='my-package',
    long_description="\\n\\n".join([
        open("README.rst").read(),
        open("CONTRIBUTORS.rst").read(),
        open("CHANGES.rst").read(),
    ]),
)
""")
        result = parse_setup_py(setup_py)
        assert result["long_description"] == "__file__:README.rst"

    def test_long_description_fstring_pattern(self, tmp_path):
        """Test f-string with Path().read_text() pattern."""
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from pathlib import Path
from setuptools import setup
long_description = f"{Path('README.rst').read_text()}\\n{Path('CHANGES.rst').read_text()}"
setup(
    name='my-package',
    long_description=long_description,
)
""")
        result = parse_setup_py(setup_py)
        assert result["long_description"] == "__file__:README.rst"

    def test_long_description_join_with_read_helper(self, tmp_path):
        r"""Test '\n\n'.join([read('README'), read('CONTRIBUTORS'), ...])."""
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
import os

def read(*rnames):
    with open(os.path.join(os.path.dirname(__file__), *rnames)) as f:
        return f.read()

from setuptools import setup
setup(
    name='my-package',
    long_description="\\n\\n".join([
        read("README.rst"),
        read("CONTRIBUTORS.rst"),
        read("CHANGES.rst"),
    ]),
)
""")
        result = parse_setup_py(setup_py)
        assert result["long_description"] == "__file__:README.rst"

    def test_classifiers(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup
setup(
    name='my-package',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Framework :: Plone',
    ],
)
""")
        result = parse_setup_py(setup_py)
        assert result["classifiers"] == [
            "Programming Language :: Python :: 3",
            "Framework :: Plone",
        ]

    def test_install_requires(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup
setup(
    name='my-package',
    install_requires=[
        'setuptools',
        'plone.api>=2.0',
        'zope.interface',
    ],
)
""")
        result = parse_setup_py(setup_py)
        assert result["install_requires"] == [
            "setuptools",
            "plone.api>=2.0",
            "zope.interface",
        ]

    def test_plone_typical_pattern(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup, find_packages

setup(
    name='plone.app.something',
    version='1.0',
    description='A Plone addon',
    long_description=open('README.rst').read(),
    classifiers=[
        'Framework :: Plone',
        'Programming Language :: Python :: 3',
    ],
    keywords='plone',
    author='John Doe',
    author_email='john@example.com',
    url='https://github.com/plone/plone.app.something',
    license='GPL',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    namespace_packages=['plone', 'plone.app'],
    include_package_data=True,
    zip_safe=False,
    python_requires='>=3.8',
    install_requires=[
        'setuptools',
        'plone.api>=2.0',
    ],
    extras_require=dict(
        test=['pytest'],
    ),
    entry_points=\"\"\"
        [z3c.autoinclude.plugin]
        target = plone
    \"\"\",
)
""")
        result = parse_setup_py(setup_py)
        assert result["name"] == "plone.app.something"
        assert result["version"] == "1.0"
        assert result["packages"] == "find_packages:src"
        assert result["python_requires"] == ">=3.8"
        assert result["extras_require"] == {"test": ["pytest"]}

    def test_no_setup_call(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("import os\n")
        result = parse_setup_py(setup_py)
        assert result == {}

    def test_warnings_for_unresolvable(self, tmp_path):
        setup_py = tmp_path / "setup.py"
        setup_py.write_text("""\
from setuptools import setup
setup(
    name='my-package',
    version=get_version(),
)
""")
        result = parse_setup_py(setup_py)
        assert result["name"] == "my-package"
        assert any("version" in w for w in result["_warnings"])


# ---------------------------------------------------------------------------
# setup.cfg parsing
# ---------------------------------------------------------------------------


class TestParseSetupCfg:
    """Test configparser-based setup.cfg parsing."""

    def test_simple_setup_cfg(self, tmp_path):
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""\
[metadata]
name = my-package
version = 1.0.0
description = A test package

[options]
python_requires = >=3.8
install_requires =
    plone.api>=2.0
    zope.interface
""")
        result = parse_setup_cfg(setup_cfg)
        assert result["name"] == "my-package"
        assert result["version"] == "1.0.0"
        assert result["python_requires"] == ">=3.8"
        assert result["install_requires"] == ["plone.api>=2.0", "zope.interface"]

    def test_extras_require(self, tmp_path):
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""\
[metadata]
name = my-package

[options.extras_require]
test =
    pytest
    pytest-cov
docs =
    sphinx
""")
        result = parse_setup_cfg(setup_cfg)
        assert result["extras_require"]["test"] == ["pytest", "pytest-cov"]
        assert result["extras_require"]["docs"] == ["sphinx"]

    def test_find_packages(self, tmp_path):
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""\
[metadata]
name = my-package

[options]
packages = find:

[options.packages.find]
where = src
""")
        result = parse_setup_cfg(setup_cfg)
        assert result["packages"] == "find_packages:src"

    def test_entry_points(self, tmp_path):
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""\
[metadata]
name = my-package

[options.entry_points]
console_scripts =
    my-cmd = my_package.cli:main
z3c.autoinclude.plugin =
    target = plone
""")
        result = parse_setup_cfg(setup_cfg)
        assert "console_scripts" in result["entry_points"]
        assert result["entry_points"]["console_scripts"] == [
            "my-cmd = my_package.cli:main"
        ]


# ---------------------------------------------------------------------------
# Metadata merging
# ---------------------------------------------------------------------------


class TestMergeMetadata:
    """Test merging of setup.py and setup.cfg metadata."""

    def test_setup_cfg_takes_precedence(self):
        py_data = {"name": "from-py", "version": "1.0", "description": "from setup.py"}
        cfg_data = {"name": "from-cfg", "version": "2.0"}
        result = merge_metadata(py_data, cfg_data)
        assert result["name"] == "from-cfg"
        assert result["version"] == "2.0"
        assert result["description"] == "from setup.py"

    def test_empty_cfg_keeps_py(self):
        py_data = {"name": "from-py", "version": "1.0"}
        result = merge_metadata(py_data, {})
        assert result["name"] == "from-py"


# ---------------------------------------------------------------------------
# pyproject.toml generation
# ---------------------------------------------------------------------------


class TestGeneratePyprojectToml:
    """Test pyproject.toml generation."""

    def test_minimal_output(self):
        metadata = {"name": "my-package", "version": "1.0.0"}
        content = generate_pyproject_toml(metadata)
        parsed = tomlkit.parse(content)

        assert parsed["build-system"]["build-backend"] == "hatchling.build"
        assert "hatchling" in parsed["build-system"]["requires"]
        assert parsed["project"]["name"] == "my-package"
        assert parsed["project"]["version"] == "1.0.0"

    def test_full_metadata(self):
        metadata = {
            "name": "plone.app.something",
            "version": "1.0",
            "description": "A Plone addon",
            "author": "John Doe",
            "author_email": "john@example.com",
            "url": "https://github.com/plone/plone.app.something",
            "license": "GPL",
            "python_requires": ">=3.8",
            "classifiers": [
                "Framework :: Plone",
                "Programming Language :: Python :: 3",
            ],
            "install_requires": ["plone.api>=2.0", "zope.interface"],
            "packages": "find_packages:src",
        }
        content = generate_pyproject_toml(metadata)
        parsed = tomlkit.parse(content)

        assert parsed["project"]["name"] == "plone.app.something"
        assert parsed["project"]["requires-python"] == ">=3.8"
        assert parsed["project"]["license"] == "GPL-2.0-only"
        assert "plone.api>=2.0" in parsed["project"]["dependencies"]
        assert "zope.interface" in parsed["project"]["dependencies"]

    def test_setuptools_stripped_from_dependencies(self):
        metadata = {
            "name": "my-package",
            "version": "1.0",
            "install_requires": ["setuptools", "plone.api>=2.0"],
        }
        content = generate_pyproject_toml(metadata)
        parsed = tomlkit.parse(content)
        deps = list(parsed["project"]["dependencies"])
        assert "setuptools" not in deps
        assert "plone.api>=2.0" in deps

    def test_dynamic_version(self):
        metadata = {"name": "my-package"}  # no version → dynamic
        content = generate_pyproject_toml(metadata)
        parsed = tomlkit.parse(content)
        assert "version" in parsed["project"]["dynamic"]
        assert "hatch-vcs" in parsed["build-system"]["requires"]
        assert parsed["tool"]["hatch"]["version"]["source"] == "vcs"

    def test_extras(self):
        metadata = {
            "name": "my-package",
            "version": "1.0",
            "extras_require": {"test": ["pytest", "pytest-cov"], "docs": ["sphinx"]},
        }
        content = generate_pyproject_toml(metadata)
        parsed = tomlkit.parse(content)
        assert list(parsed["project"]["optional-dependencies"]["test"]) == [
            "pytest",
            "pytest-cov",
        ]
        assert list(parsed["project"]["optional-dependencies"]["docs"]) == ["sphinx"]

    def test_entry_points_console_scripts(self):
        metadata = {
            "name": "my-package",
            "version": "1.0",
            "entry_points": {"console_scripts": ["my-cmd = my_package.cli:main"]},
        }
        content = generate_pyproject_toml(metadata)
        parsed = tomlkit.parse(content)
        assert parsed["project"]["scripts"]["my-cmd"] == "my_package.cli:main"

    def test_entry_points_z3c_autoinclude(self):
        metadata = {
            "name": "my-package",
            "version": "1.0",
            "entry_points": {"z3c.autoinclude.plugin": ["target = plone"]},
        }
        content = generate_pyproject_toml(metadata)
        parsed = tomlkit.parse(content)
        assert (
            parsed["project"]["entry-points"]["z3c.autoinclude.plugin"]["target"]
            == "plone"
        )

    def test_entry_points_string_format(self):
        metadata = {
            "name": "my-package",
            "version": "1.0",
            "entry_points": """
                [z3c.autoinclude.plugin]
                target = plone
            """,
        }
        content = generate_pyproject_toml(metadata)
        parsed = tomlkit.parse(content)
        assert (
            parsed["project"]["entry-points"]["z3c.autoinclude.plugin"]["target"]
            == "plone"
        )

    def test_readme_detection(self):
        metadata = {
            "name": "my-package",
            "version": "1.0",
            "long_description": "__file__:README.rst",
        }
        content = generate_pyproject_toml(metadata)
        parsed = tomlkit.parse(content)
        assert parsed["project"]["readme"] == "README.rst"

    def test_merge_with_existing_pyproject(self):
        existing = """\
[tool.ruff]
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F"]
"""
        metadata = {"name": "my-package", "version": "1.0"}
        content = generate_pyproject_toml(metadata, existing_pyproject=existing)
        parsed = tomlkit.parse(content)
        # Existing config preserved
        assert parsed["tool"]["ruff"]["target-version"] == "py312"
        # New sections added
        assert parsed["build-system"]["build-backend"] == "hatchling.build"
        assert parsed["project"]["name"] == "my-package"

    def test_skip_when_project_exists(self):
        """If pyproject.toml already has [project], don't generate."""
        existing = """\
[project]
name = "existing-package"
"""
        # This is handled by migrate_packaging, not generate_pyproject_toml directly
        # Just verify the orchestrator handles it
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "pyproject.toml").write_text(existing)
            (root / "setup.py").write_text(
                "from setuptools import setup\nsetup(name='pkg')\n"
            )
            result = migrate_packaging(root)
            assert any("already has [project]" in w for w in result["warnings"])

    def test_license_classifiers_stripped_with_pep639(self):
        """PEP 639 license expression + License :: classifier is rejected by setuptools >= 78."""
        metadata = {
            "name": "my-package",
            "version": "1.0",
            "license": "GPL",
            "classifiers": [
                "Framework :: Plone",
                "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
                "Programming Language :: Python :: 3",
            ],
        }
        content = generate_pyproject_toml(metadata)
        parsed = tomlkit.parse(content)
        classifiers = list(parsed["project"]["classifiers"])
        assert "Framework :: Plone" in classifiers
        assert "Programming Language :: Python :: 3" in classifiers
        assert not any(c.startswith("License ::") for c in classifiers)
        assert parsed["project"]["license"] == "GPL-2.0-only"

    def test_license_classifiers_kept_without_license_field(self):
        """If no license field, keep License :: classifiers."""
        metadata = {
            "name": "my-package",
            "version": "1.0",
            "classifiers": [
                "License :: OSI Approved :: MIT License",
                "Programming Language :: Python :: 3",
            ],
        }
        content = generate_pyproject_toml(metadata)
        parsed = tomlkit.parse(content)
        classifiers = list(parsed["project"]["classifiers"])
        assert "License :: OSI Approved :: MIT License" in classifiers

    def test_no_namespace_packages_in_output(self):
        metadata = {
            "name": "my-package",
            "version": "1.0",
            "namespace_packages": ["plone", "plone.app"],
        }
        content = generate_pyproject_toml(metadata)
        assert "namespace" not in content.lower()

    def test_hatch_wheel_packages_for_src_layout(self):
        metadata = {
            "name": "plone.app.something",
            "version": "1.0",
            "packages": "find_packages:src",
        }
        content = generate_pyproject_toml(metadata)
        parsed = tomlkit.parse(content)
        packages = list(
            parsed["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
        )
        assert "src/plone" in packages

    def test_license_normalization(self):
        metadata = {"name": "my-package", "version": "1.0", "license": "GPL"}
        content = generate_pyproject_toml(metadata)
        parsed = tomlkit.parse(content)
        assert parsed["project"]["license"] == "GPL-2.0-only"


# ---------------------------------------------------------------------------
# Tool config conversion
# ---------------------------------------------------------------------------


class TestConvertToolConfigs:
    """Test setup.cfg tool section → pyproject.toml conversion."""

    def test_flake8_to_ruff(self, tmp_path):
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""\
[flake8]
max-line-length = 120
ignore = E501,W503
select = E,F,W
exclude =
    build
    dist
""")
        result = convert_tool_configs(setup_cfg)
        assert result["ruff"]["line-length"] == 120
        assert result["ruff"]["lint"]["ignore"] == ["E501", "W503"]
        assert result["ruff"]["lint"]["select"] == ["E", "F", "W"]
        assert "build" in result["ruff"]["exclude"]

    def test_isort_to_ruff(self, tmp_path):
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""\
[isort]
known_first_party = my_package
force_single_line = true
lines_after_imports = 2
""")
        result = convert_tool_configs(setup_cfg)
        isort = result["ruff"]["lint"]["isort"]
        assert isort["known-first-party"] == ["my_package"]
        assert isort["force-single-line"] is True
        assert isort["lines-after-imports"] == 2

    def test_pycodestyle_to_ruff(self, tmp_path):
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""\
[pycodestyle]
max-line-length = 100
ignore = E501
""")
        result = convert_tool_configs(setup_cfg)
        assert result["ruff"]["line-length"] == 100
        assert result["ruff"]["lint"]["ignore"] == ["E501"]

    def test_pytest_conversion(self, tmp_path):
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""\
[tool:pytest]
testpaths = tests
addopts = -v --tb=short
""")
        result = convert_tool_configs(setup_cfg)
        assert result["pytest"]["ini_options"]["testpaths"] == ["tests"]
        assert result["pytest"]["ini_options"]["addopts"] == "-v --tb=short"

    def test_coverage_conversion(self, tmp_path):
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""\
[coverage:run]
source =
    my_package
branch = true

[coverage:report]
show_missing = true
fail_under = 80
""")
        result = convert_tool_configs(setup_cfg)
        assert result["coverage"]["run"]["source"] == ["my_package"]
        assert result["coverage"]["run"]["branch"] is True
        assert result["coverage"]["report"]["show_missing"] is True
        assert result["coverage"]["report"]["fail_under"] == 80.0

    def test_bdist_wheel_dropped(self, tmp_path):
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""\
[bdist_wheel]
universal = 1
""")
        result = convert_tool_configs(setup_cfg)
        assert "bdist_wheel" not in result

    def test_pydocstyle_to_ruff(self, tmp_path):
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""\
[pydocstyle]
convention = google
""")
        result = convert_tool_configs(setup_cfg)
        assert result["ruff"]["lint"]["pydocstyle"]["convention"] == "google"

    def test_tool_configs_in_generated_toml(self, tmp_path):
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""\
[flake8]
max-line-length = 120

[tool:pytest]
testpaths = tests
""")
        tool_configs = convert_tool_configs(setup_cfg)
        metadata = {"name": "my-package", "version": "1.0"}
        content = generate_pyproject_toml(metadata, tool_configs=tool_configs)
        parsed = tomlkit.parse(content)
        assert parsed["tool"]["ruff"]["line-length"] == 120
        assert parsed["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------


class TestFileOperations:
    """Test file-level migration operations."""

    def test_cleanup_old_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "setup.py").write_text("setup()")
            (root / "setup.cfg").write_text("[metadata]")
            (root / "MANIFEST.in").write_text("include *.txt")

            deleted = cleanup_old_files(root)
            assert len(deleted) == 3
            assert not (root / "setup.py").exists()
            assert not (root / "setup.cfg").exists()
            assert not (root / "MANIFEST.in").exists()

    def test_cleanup_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "setup.py").write_text("setup()")

            deleted = cleanup_old_files(root, dry_run=True)
            assert len(deleted) == 1
            assert (root / "setup.py").exists()  # Not actually deleted

    def test_full_migration_creates_pyproject(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "setup.py").write_text("""\
from setuptools import setup, find_packages
setup(
    name='plone.app.test',
    version='1.0',
    packages=find_packages('src'),
    install_requires=['plone.api'],
)
""")
            migrate_packaging(root)
            assert (root / "pyproject.toml").exists()
            assert not (root / "setup.py").exists()

            content = (root / "pyproject.toml").read_text()
            parsed = tomlkit.parse(content)
            assert parsed["project"]["name"] == "plone.app.test"

    def test_full_migration_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "setup.py").write_text("""\
from setuptools import setup
setup(name='my-pkg', version='1.0')
""")
            result = migrate_packaging(root, dry_run=True)
            assert len(result["created_files"]) == 1
            assert len(result["deleted_files"]) == 1
            # Files not actually modified
            assert (root / "setup.py").exists()
            assert not (root / "pyproject.toml").exists()

    def test_no_setup_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = migrate_packaging(Path(tmpdir))
            assert any("No setup.py" in w for w in result["warnings"])

    def test_merge_with_existing_pyproject(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "pyproject.toml").write_text("""\
[tool.ruff]
target-version = "py312"
""")
            (root / "setup.py").write_text("""\
from setuptools import setup
setup(name='my-pkg', version='1.0')
""")
            migrate_packaging(root)
            content = (root / "pyproject.toml").read_text()
            parsed = tomlkit.parse(content)
            # Both old and new content present
            assert parsed["tool"]["ruff"]["target-version"] == "py312"
            assert parsed["project"]["name"] == "my-pkg"

    def test_cleanup_pre_commit_check_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".pre-commit-config.yaml").write_text("""\
repos:
-   repo: https://github.com/mgedmin/check-manifest
    rev: "0.49"
    hooks:
    -   id: check-manifest
-   repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
    -   id: trailing-whitespace
""")
            modified = cleanup_pre_commit_check_manifest(root)
            assert len(modified) == 1
            content = (root / ".pre-commit-config.yaml").read_text()
            assert "check-manifest" not in content
            assert "trailing-whitespace" in content
            assert "pre-commit-hooks" in content

    def test_cleanup_pre_commit_check_manifest_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            original = """\
repos:
-   repo: https://github.com/mgedmin/check-manifest
    rev: "0.49"
    hooks:
    -   id: check-manifest
"""
            (root / ".pre-commit-config.yaml").write_text(original)
            modified = cleanup_pre_commit_check_manifest(root, dry_run=True)
            assert len(modified) == 1
            assert (root / ".pre-commit-config.yaml").read_text() == original

    def test_cleanup_pre_commit_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            modified = cleanup_pre_commit_check_manifest(Path(tmpdir))
            assert modified == []

    def test_cleanup_pre_commit_no_check_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".pre-commit-config.yaml").write_text("""\
repos:
-   repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
    -   id: trailing-whitespace
""")
            modified = cleanup_pre_commit_check_manifest(root)
            assert modified == []

    def test_manifest_in_boilerplate_no_warnings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "setup.py").write_text(
                "from setuptools import setup\nsetup(name='pkg', version='1.0')\n"
            )
            (root / "MANIFEST.in").write_text("""\
# comment
graft src
graft docs
recursive-include docs *
include *.rst
include *.txt
include LICENSE
include pyproject.toml
global-exclude *.pyc
global-exclude *.pyo
""")
            result = migrate_packaging(root)
            manifest_warnings = [w for w in result["warnings"] if "MANIFEST.in" in w]
            assert manifest_warnings == []

    def test_manifest_in_custom_rules_warn(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "setup.py").write_text(
                "from setuptools import setup\nsetup(name='pkg', version='1.0')\n"
            )
            (root / "MANIFEST.in").write_text("""\
graft src
include *.rst
prune design
recursive-exclude news *
include some_custom_file.dat
""")
            result = migrate_packaging(root)
            manifest_warnings = [w for w in result["warnings"] if "MANIFEST.in" in w]
            assert len(manifest_warnings) == 3
            assert any("prune design" in w for w in manifest_warnings)
            assert any("recursive-exclude news" in w for w in manifest_warnings)
            assert any("some_custom_file.dat" in w for w in manifest_warnings)

    def test_full_migration_removes_check_manifest_hook(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "setup.py").write_text("""\
from setuptools import setup
setup(name='my-pkg', version='1.0')
""")
            (root / ".pre-commit-config.yaml").write_text("""\
repos:
-   repo: https://github.com/mgedmin/check-manifest
    rev: "0.49"
    hooks:
    -   id: check-manifest
-   repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
    -   id: trailing-whitespace
""")
            result = migrate_packaging(root)
            assert any("pre-commit" in str(f) for f in result["modified_files"])
            content = (root / ".pre-commit-config.yaml").read_text()
            assert "check-manifest" not in content
            assert "trailing-whitespace" in content
