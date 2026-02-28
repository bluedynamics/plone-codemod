"""Migrate setup.py/setup.cfg to pyproject.toml (PEP 621).

Plone packages traditionally use setup.py (imperative) or setup.cfg
(declarative) for packaging metadata.  PEP 621 standardizes metadata
in pyproject.toml, and modern build backends (hatchling, flit) require
it.  This module automates the conversion so developers don't have to
manually translate hundreds of setup() kwargs.

Uses hatchling as the target build backend because it handles src-layout,
namespace packages (PEP 420), and dynamic versioning via hatch-vcs
out of the box — all common patterns in the Plone ecosystem.

The migration also converts legacy tool configurations (flake8, isort,
pycodestyle) to their ruff equivalents, since ruff supersedes these
tools and its config lives natively in pyproject.toml.
"""

from pathlib import Path

import ast
import configparser
import tomlkit
import tomlkit.items


# ---------------------------------------------------------------------------
# setup.py parsing (AST-based)
# ---------------------------------------------------------------------------


def parse_setup_py(path: Path) -> dict:
    """Extract metadata from setup.py using AST parsing.

    AST parsing (rather than executing setup.py) is essential because
    setup.py files often import from the package itself or have side
    effects — executing them would require a full build environment.
    The trade-off is that dynamic expressions (e.g. ``version=get_version()``)
    cannot be resolved; these are collected as warnings so the user
    knows what to fix manually.

    Returns a dict with keys matching setup() keyword arguments.
    """
    content = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(content, filename=str(path))
    except SyntaxError:
        return {}

    # Collect module-level variable assignments
    module_vars = _collect_module_vars(tree)

    # Find the setup() call
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_setup_call(node):
            return _extract_setup_kwargs(node, module_vars)

    return {}


def _collect_module_vars(tree: ast.Module) -> dict:
    """Collect simple module-level variable assignments.

    Many setup.py files define ``VERSION = "1.0"`` or
    ``LONG_DESCRIPTION = open('README.rst').read()`` at module level
    and then reference these variables inside the setup() call.  By
    collecting them first we can resolve ``ast.Name`` references during
    keyword extraction.
    """
    module_vars: dict = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                val = _eval_node(node.value, module_vars)
                if val is not _UNRESOLVED:
                    module_vars[target.id] = val
    return module_vars


_UNRESOLVED = object()  # Sentinel — identity-compared, never equal to real values.


def _eval_node(node: ast.expr, module_vars: dict) -> object:
    """Try to statically evaluate an AST node to a Python value.

    Returns ``_UNRESOLVED`` for anything that cannot be determined at
    parse time (function calls, complex expressions, etc.).  Using a
    sentinel object instead of None lets us distinguish "resolved to None"
    from "could not resolve".

    Covers the patterns actually seen in Plone setup.py files:
    constants, variables, lists, dicts, ``dict()``, ``find_packages()``,
    string concatenation, ``open(...).read()`` file references,
    ``"...".format(read("README.rst"), ...)`` format calls, and
    helper functions like ``read("README.rst")`` with doc-filename args.
    """
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name) and node.id in module_vars:
        return module_vars[node.id]

    if isinstance(node, ast.List):
        items = [_eval_node(el, module_vars) for el in node.elts]
        if _UNRESOLVED in items:
            return _UNRESOLVED
        return items

    if isinstance(node, ast.Tuple):
        items = [_eval_node(el, module_vars) for el in node.elts]
        if _UNRESOLVED in items:
            return _UNRESOLVED
        return tuple(items)

    if isinstance(node, ast.Dict):
        keys = []
        vals = []
        for k, v in zip(node.keys, node.values, strict=True):
            ek = _eval_node(k, module_vars) if k else _UNRESOLVED
            ev = _eval_node(v, module_vars)
            if ek is _UNRESOLVED or ev is _UNRESOLVED:
                return _UNRESOLVED
            keys.append(ek)
            vals.append(ev)
        return dict(zip(keys, vals, strict=True))

    # dict() call: e.g. dict(test=[...], docs=[...])
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "dict"
    ):
        result = {}
        for kw in node.keywords:
            if kw.arg is None:
                return _UNRESOLVED
            val = _eval_node(kw.value, module_vars)
            if val is _UNRESOLVED:
                return _UNRESOLVED
            result[kw.arg] = val
        return result

    # find_packages() / find_packages('src')
    if isinstance(node, ast.Call) and _is_find_packages(node):
        if node.args:
            where = _eval_node(node.args[0], module_vars)
            if where is not _UNRESOLVED:
                return f"find_packages:{where}"
        return "find_packages:."

    # String concatenation: 'a' + 'b'
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _eval_node(node.left, module_vars)
        right = _eval_node(node.right, module_vars)
        if isinstance(left, str) and isinstance(right, str):
            # Propagate __file__: reference (the first file is typically README)
            if left.startswith("__file__:"):
                return left
            return left + right
        return _UNRESOLVED

    # open('README.rst').read() pattern → detect file reference
    if isinstance(node, ast.Call):
        chain = _detect_file_read_chain(node)
        if chain:
            return f"__file__:{chain}"

    # "{}...".format(read("README.rst"), ...) → extract file ref from first arg
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
        and isinstance(node.func.value, ast.Constant)
        and isinstance(node.func.value.value, str)
        and node.args
    ):
        first = _eval_node(node.args[0], module_vars)
        if isinstance(first, str) and first.startswith("__file__:"):
            return first

    # Calls with doc-filename args: read("README.rst"), read("CHANGES.rst")
    # Common pattern in Plone setup.py files using helper functions.
    if isinstance(node, ast.Call) and node.args:
        first_arg = node.args[0]
        if (
            isinstance(first_arg, ast.Constant)
            and isinstance(first_arg.value, str)
            and _is_doc_filename(first_arg.value)
        ):
            return f"__file__:{first_arg.value}"

    return _UNRESOLVED


def _is_find_packages(node: ast.Call) -> bool:
    """Detect ``find_packages()`` / ``find_namespace_packages()`` calls.

    The return value from these calls can't be statically evaluated to
    a package list, but we can record the ``where`` argument to configure
    hatchling's ``[tool.hatch.build.targets.wheel]`` packages path.
    """
    func = node.func
    if isinstance(func, ast.Name) and func.id == "find_packages":
        return True
    if isinstance(func, ast.Attribute) and func.attr == "find_packages":
        return True
    return isinstance(func, ast.Name) and func.id == "find_namespace_packages"


def _detect_file_read_chain(node: ast.Call) -> str | None:
    """Detect ``open('file').read()`` or ``Path('file').read_text()`` patterns.

    Many setup.py files use ``long_description=open('README.rst').read()``.
    We can't evaluate this at parse time, but we can extract the filename
    and use it as the ``readme`` field in pyproject.toml.
    """
    if isinstance(node.func, ast.Attribute) and node.func.attr in ("read", "read_text"):
        inner = node.func.value
        if isinstance(inner, ast.Call):
            if (
                isinstance(inner.func, ast.Name)
                and inner.func.id == "open"
                and inner.args
            ):
                arg = inner.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    return arg.value
            if (
                isinstance(inner.func, ast.Name)
                and inner.func.id == "Path"
                and inner.args
            ):
                arg = inner.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    return arg.value
    return None


def _is_doc_filename(filename: str) -> bool:
    """Return True if *filename* looks like a documentation file.

    Used to detect helper functions like ``read("README.rst")`` that
    read documentation files — a very common pattern in Plone setup.py
    files.  Only matches well-known documentation filenames to avoid
    false positives on unrelated function calls.
    """
    base = filename.split(".")[0].upper() if "." in filename else filename.upper()
    return base in ("README", "CHANGES", "CHANGELOG", "HISTORY", "NEWS")


def _is_setup_call(node: ast.Call) -> bool:
    """Match both ``setup(...)`` and ``setuptools.setup(...)``."""
    func = node.func
    if isinstance(func, ast.Name) and func.id == "setup":
        return True
    return isinstance(func, ast.Attribute) and func.attr == "setup"


def _extract_setup_kwargs(node: ast.Call, module_vars: dict) -> dict:
    """Extract keyword arguments from a ``setup()`` call.

    Unresolvable values are recorded in ``_warnings`` rather than
    raising, so the migration can proceed with partial metadata and
    the user gets actionable feedback about what to fix.
    """
    result: dict = {}
    result["_warnings"] = []

    for kw in node.keywords:
        if kw.arg is None:
            # **kwargs expansion — skip
            continue
        val = _eval_node(kw.value, module_vars)
        if val is _UNRESOLVED:
            result["_warnings"].append(f"Could not resolve value for '{kw.arg}'")
        else:
            result[kw.arg] = val

    return result


# ---------------------------------------------------------------------------
# setup.cfg parsing
# ---------------------------------------------------------------------------


def parse_setup_cfg(path: Path) -> dict:
    """Extract metadata and options from setup.cfg.

    Uses ``configparser`` because setup.cfg is an INI-format file.
    Handles the setuptools-specific conventions: multi-line lists in
    ``install_requires``, the ``find:``/``find_namespace:`` shorthand
    for packages, and the ``[options.packages.find]`` sub-section.
    """
    cfg = configparser.ConfigParser()
    cfg.read(str(path), encoding="utf-8")

    result: dict = {}

    # [metadata] section
    if cfg.has_section("metadata"):
        for key in cfg.options("metadata"):
            result[key] = cfg.get("metadata", key)

    # [options] section
    if cfg.has_section("options"):
        for key in cfg.options("options"):
            val = cfg.get("options", key)
            if key in ("install_requires", "setup_requires", "tests_require"):
                result[key] = _parse_cfg_list(val)
            elif key == "python_requires":
                result["python_requires"] = val
            elif key in ("zip_safe", "include_package_data"):
                result[key] = val.lower() in ("true", "1", "yes")
            elif key == "package_dir":
                result[key] = val
            elif key == "packages":
                if val.strip().startswith("find:") or val.strip().startswith(
                    "find_namespace:"
                ):
                    result["packages"] = "find_packages:."
                else:
                    result[key] = _parse_cfg_list(val)
            else:
                result[key] = val

    # [options.packages.find] section
    if cfg.has_section("options.packages.find"):
        where = cfg.get("options.packages.find", "where", fallback=None)
        if where:
            result["packages"] = f"find_packages:{where.strip()}"

    # [options.extras_require] section
    if cfg.has_section("options.extras_require"):
        extras = {}
        for key in cfg.options("options.extras_require"):
            extras[key] = _parse_cfg_list(cfg.get("options.extras_require", key))
        result["extras_require"] = extras

    # [options.entry_points] section
    if cfg.has_section("options.entry_points"):
        eps = {}
        for key in cfg.options("options.entry_points"):
            eps[key] = _parse_cfg_list(cfg.get("options.entry_points", key))
        result["entry_points"] = eps

    return result


def _parse_cfg_list(value: str) -> list[str]:
    """Parse a setup.cfg multi-line list value into a list of strings."""
    items = []
    for line in value.strip().splitlines():
        line = line.strip()
        if line:
            items.append(line)
    return items


# ---------------------------------------------------------------------------
# Tool config conversion (setup.cfg → pyproject.toml)
# ---------------------------------------------------------------------------


def convert_tool_configs(path: Path) -> dict:
    """Extract tool configuration sections from setup.cfg and convert them.

    With the move to pyproject.toml, tool configs that lived in setup.cfg
    need a new home.  Rather than blindly copying flake8/isort/pycodestyle
    sections, we convert them to ruff equivalents — ruff supersedes all
    three tools and is the standard linter in the modern Plone stack.

    Pytest and coverage configs are moved as-is to their native
    ``[tool.pytest.ini_options]`` / ``[tool.coverage.*]`` sections.
    ``[bdist_wheel]`` is dropped because PEP 517 handles wheel building.

    Returns a dict suitable for merging into pyproject.toml's ``[tool.*]``.
    """
    cfg = configparser.ConfigParser()
    cfg.read(str(path), encoding="utf-8")

    tools: dict = {}

    # flake8 → ruff
    if cfg.has_section("flake8"):
        ruff, ruff_lint = _convert_flake8(cfg)
        tools.setdefault("ruff", {}).update(ruff)
        tools.setdefault("ruff", {}).setdefault("lint", {}).update(ruff_lint)

    # isort → ruff.lint.isort
    if cfg.has_section("isort"):
        isort_cfg = _convert_isort(cfg)
        tools.setdefault("ruff", {}).setdefault("lint", {}).setdefault(
            "isort", {}
        ).update(isort_cfg)

    # pycodestyle / pep8 → ruff
    for section in ("pycodestyle", "pep8"):
        if cfg.has_section(section):
            ruff, ruff_lint = _convert_pycodestyle(cfg, section)
            tools.setdefault("ruff", {}).update(ruff)
            tools.setdefault("ruff", {}).setdefault("lint", {}).update(ruff_lint)

    # pydocstyle → ruff.lint.pydocstyle
    if cfg.has_section("pydocstyle"):
        pydoc_cfg = _convert_pydocstyle(cfg)
        tools.setdefault("ruff", {}).setdefault("lint", {}).setdefault(
            "pydocstyle", {}
        ).update(pydoc_cfg)

    # tool:pytest / pytest → pytest.ini_options
    for section in ("tool:pytest", "pytest"):
        if cfg.has_section(section):
            tools["pytest"] = {"ini_options": _convert_pytest(cfg, section)}
            break

    # coverage:run → coverage.run
    if cfg.has_section("coverage:run"):
        tools.setdefault("coverage", {})["run"] = _convert_coverage_section(
            cfg, "coverage:run"
        )

    # coverage:report → coverage.report
    if cfg.has_section("coverage:report"):
        tools.setdefault("coverage", {})["report"] = _convert_coverage_section(
            cfg, "coverage:report"
        )

    # check-manifest → check-manifest
    if cfg.has_section("check-manifest"):
        tools["check-manifest"] = dict(cfg.items("check-manifest"))

    return tools


def _convert_flake8(cfg: configparser.ConfigParser) -> tuple[dict, dict]:
    """Convert ``[flake8]`` to ruff top-level and ``ruff.lint`` settings.

    ``max-line-length`` maps to ruff's top-level ``line-length`` (not
    lint-specific), while ``ignore``/``select`` map to ``ruff.lint.*``.
    """
    ruff: dict = {}
    ruff_lint: dict = {}

    for key, val in cfg.items("flake8"):
        if key == "max-line-length" or key == "max_line_length":
            ruff["line-length"] = int(val)
        elif key == "ignore":
            ruff_lint["ignore"] = [s.strip() for s in val.split(",") if s.strip()]
        elif key == "select":
            ruff_lint["select"] = [s.strip() for s in val.split(",") if s.strip()]
        elif key == "extend-ignore" or key == "extend_ignore":
            ruff_lint["extend-ignore"] = [
                s.strip() for s in val.split(",") if s.strip()
            ]
        elif key == "exclude":
            ruff["exclude"] = _parse_cfg_list(val)

    return ruff, ruff_lint


def _convert_isort(cfg: configparser.ConfigParser) -> dict:
    """Convert ``[isort]`` to ``ruff.lint.isort`` settings.

    Key names are translated from Python underscore style to ruff's
    kebab-case.  The ``profile`` option has no ruff equivalent and is
    silently dropped.
    """
    result: dict = {}
    key_map = {
        "known_first_party": "known-first-party",
        "known_third_party": "known-third-party",
        "force_single_line": "force-single-line",
        "lines_after_imports": "lines-after-imports",
        "lines_between_types": "lines-between-types",
        "from_first": "from-first",
        "no_sections": "no-sections",
        "order_by_type": "order-by-type",
    }

    for key, val in cfg.items("isort"):
        if key in key_map:
            # Lists
            if key in ("known_first_party", "known_third_party"):
                result[key_map[key]] = [s.strip() for s in val.split(",") if s.strip()]
            # Booleans
            elif key in (
                "force_single_line",
                "from_first",
                "no_sections",
                "order_by_type",
            ):
                result[key_map[key]] = val.lower() in ("true", "1", "yes")
            # Integers
            elif key in ("lines_after_imports", "lines_between_types"):
                result[key_map[key]] = int(val)
            else:
                result[key_map[key]] = val
        elif key == "profile":
            # ruff isort doesn't have profile; skip
            pass

    return result


def _convert_pycodestyle(
    cfg: configparser.ConfigParser, section: str
) -> tuple[dict, dict]:
    """Convert [pycodestyle] or [pep8] to ruff settings."""
    ruff: dict = {}
    ruff_lint: dict = {}

    for key, val in cfg.items(section):
        if key == "max-line-length" or key == "max_line_length":
            ruff["line-length"] = int(val)
        elif key == "ignore":
            ruff_lint["ignore"] = [s.strip() for s in val.split(",") if s.strip()]
        elif key == "exclude":
            ruff["exclude"] = _parse_cfg_list(val)

    return ruff, ruff_lint


def _convert_pydocstyle(cfg: configparser.ConfigParser) -> dict:
    """Convert [pydocstyle] to ruff.lint.pydocstyle settings."""
    result: dict = {}
    for key, val in cfg.items("pydocstyle"):
        if key == "convention":
            result["convention"] = val
        elif key in ("match-dir", "match_dir"):
            result["match-dir"] = val
    return result


def _convert_pytest(cfg: configparser.ConfigParser, section: str) -> dict:
    """Convert [tool:pytest] or [pytest] to tool.pytest.ini_options."""
    result: dict = {}
    for key, val in cfg.items(section):
        if key in ("testpaths", "python_files", "python_classes", "python_functions"):
            result[key] = _parse_cfg_list(val)
        elif key == "addopts":
            result[key] = val.strip()
        elif key == "markers":
            result[key] = _parse_cfg_list(val)
        else:
            result[key] = val
    return result


def _convert_coverage_section(cfg: configparser.ConfigParser, section: str) -> dict:
    """Convert [coverage:run] or [coverage:report] to tool.coverage.* settings."""
    result: dict = {}
    for key, val in cfg.items(section):
        if key in ("source", "omit", "include"):
            result[key] = _parse_cfg_list(val)
        elif key in ("show_missing", "branch"):
            result[key] = val.lower() in ("true", "1", "yes")
        elif key == "fail_under":
            result[key] = float(val)
        else:
            result[key] = val
    return result


# ---------------------------------------------------------------------------
# Metadata merging
# ---------------------------------------------------------------------------


def merge_metadata(setup_py_data: dict, setup_cfg_data: dict) -> dict:
    """Merge metadata from setup.py and setup.cfg.

    setup.cfg takes precedence for overlapping keys.  This matches
    setuptools' own behavior: when both files define the same field,
    setup.cfg wins.  Many Plone packages define some metadata in
    setup.py and override or extend it in setup.cfg.
    """
    result = dict(setup_py_data)
    for key, val in setup_cfg_data.items():
        if val is not None and val != "" and val != []:
            result[key] = val
    return result


# ---------------------------------------------------------------------------
# pyproject.toml generation
# ---------------------------------------------------------------------------


def generate_pyproject_toml(
    metadata: dict,
    existing_pyproject: str | None = None,
    tool_configs: dict | None = None,
) -> str:
    """Generate pyproject.toml content from extracted metadata.

    Uses ``tomlkit`` (not ``tomli_w``) because tomlkit preserves comments,
    formatting, and ordering when merging into an existing file — important
    when the project already has a pyproject.toml with ``[tool.ruff]`` or
    other manual configuration.

    If existing_pyproject is given, merges into it preserving existing sections.
    """
    doc = (
        tomlkit.parse(existing_pyproject) if existing_pyproject else tomlkit.document()
    )

    # Build system
    if "build-system" not in doc:
        bs = tomlkit.table()
        requires = tomlkit.array()
        requires.append("hatchling")
        if _is_dynamic_version(metadata):
            requires.append("hatch-vcs")
        bs.add("requires", requires)
        bs.add("build-backend", "hatchling.build")
        doc.add("build-system", bs)

    # [project]
    if "project" not in doc:
        project = tomlkit.table()
        _populate_project_table(project, metadata)
        doc.add("project", project)

    # [project.optional-dependencies]
    extras = metadata.get("extras_require", {})
    if extras and "project" in doc:
        opt_deps = tomlkit.table()
        for group, deps in extras.items():
            arr = tomlkit.array()
            for dep in deps:
                arr.append(dep)
            opt_deps.add(group, arr)
        doc["project"].add("optional-dependencies", opt_deps)
    # [project.urls]
    url = metadata.get("url") or metadata.get("home_page")
    project_urls = metadata.get("project_urls")
    if (url or project_urls) and "project" in doc:
        urls = tomlkit.table()
        if url:
            urls.add("Homepage", url)
        if isinstance(project_urls, dict):
            for k, v in project_urls.items():
                if k not in urls:
                    urls.add(k, v)
        doc["project"].add("urls", urls)
    # Entry points
    _add_entry_points(doc, metadata)

    # [tool.hatch.build.targets.wheel]
    packages_val = metadata.get("packages", "")
    if isinstance(packages_val, str) and packages_val.startswith("find_packages:"):
        where = packages_val.split(":", 1)[1]
        if where and where != ".":
            _ensure_hatch_wheel_config(doc, metadata, where)

    # [tool.hatch.version]
    if _is_dynamic_version(metadata):
        hatch = doc.setdefault("tool", tomlkit.table()).setdefault(
            "hatch", tomlkit.table()
        )
        version_tbl = tomlkit.table()
        version_tbl.add("source", "vcs")
        hatch.add("version", version_tbl)

    # Tool configurations from setup.cfg
    if tool_configs:
        tool_section = doc.setdefault("tool", tomlkit.table())
        for tool_name, tool_cfg in tool_configs.items():
            if tool_name not in tool_section:
                tool_section.add(tool_name, _dict_to_tomlkit(tool_cfg))

    return tomlkit.dumps(doc)


def _populate_project_table(project: tomlkit.items.Table, metadata: dict) -> None:
    """Populate the ``[project]`` table with PEP 621 metadata.

    Translates setup() keyword names to their PEP 621 equivalents
    (e.g. ``install_requires`` -> ``dependencies``,
    ``python_requires`` -> ``requires-python``).

    ``setuptools`` is stripped from runtime dependencies because it's
    a build-time dependency, not a runtime one — having it in
    ``install_requires`` was a legacy pattern from namespace packages.
    """
    name = metadata.get("name", "")
    if name:
        project.add("name", name)

    # Version: static or dynamic
    version = metadata.get("version")
    if _is_dynamic_version(metadata):
        dynamic = tomlkit.array()
        dynamic.append("version")
        project.add("dynamic", dynamic)
    elif version and isinstance(version, str):
        project.add("version", version)

    description = metadata.get("description", "")
    if description:
        project.add("description", description)

    # Readme
    readme = _detect_readme(metadata)
    if readme:
        project.add("readme", readme)

    # License
    license_val = metadata.get("license")
    if license_val:
        project.add("license", _normalize_license(license_val))

    # Python requires
    python_requires = metadata.get("python_requires")
    if python_requires:
        project.add("requires-python", python_requires)

    # Classifiers
    classifiers = metadata.get("classifiers")
    if classifiers and isinstance(classifiers, list):
        arr = tomlkit.array()
        arr.multiline(True)
        for c in classifiers:
            arr.append(c)
        project.add("classifiers", arr)

    # Keywords
    keywords = metadata.get("keywords")
    if keywords:
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        if isinstance(keywords, list):
            arr = tomlkit.array()
            for k in keywords:
                arr.append(k)
            project.add("keywords", arr)

    # Authors
    author = metadata.get("author")
    author_email = metadata.get("author_email")
    if author or author_email:
        authors = tomlkit.array()
        entry = tomlkit.inline_table()
        if author:
            entry.append("name", author)
        if author_email:
            entry.append("email", author_email)
        authors.append(entry)
        project.add("authors", authors)

    # Dependencies
    install_requires = metadata.get("install_requires", [])
    if install_requires:
        deps = tomlkit.array()
        deps.multiline(True)
        for dep in install_requires:
            # Skip setuptools from runtime deps
            if dep.strip().lower().startswith("setuptools"):
                continue
            deps.append(dep)
        if deps:
            project.add("dependencies", deps)


def _is_dynamic_version(metadata: dict) -> bool:
    """Check if version should be dynamic (from VCS or file read).

    When the version isn't a simple string literal (or is absent),
    we configure ``dynamic = ["version"]`` with hatch-vcs so the
    version is derived from git tags at build time — a common and
    recommended pattern for Plone packages.
    """
    version = metadata.get("version")
    if version is None:
        return True
    return isinstance(version, str) and version.startswith("__file__:")


def _detect_readme(metadata: dict) -> str | None:
    """Detect the readme file from metadata."""
    # Check if long_description references files
    long_desc = metadata.get("long_description", "")
    if isinstance(long_desc, str) and long_desc.startswith("__file__:"):
        filename = long_desc.split(":", 1)[1]
        return filename

    # Check long_description_content_type
    content_type = metadata.get("long_description_content_type", "")

    # Try common filenames
    for name in ("README.rst", "README.md", "README.txt", "README"):
        if content_type:
            return name
    return None


def _normalize_license(license_val: str) -> str:
    """Normalize license string to SPDX identifier where possible.

    PEP 639 requires SPDX license expressions in pyproject.toml.
    Old setup.py files use free-form strings ("GPL", "GNU General
    Public License v2 (GPLv2)", etc.) that must be mapped to the
    corresponding SPDX identifier.
    """
    mapping = {
        "gpl": "GPL-2.0-only",
        "gpl2": "GPL-2.0-only",
        "gpl v2": "GPL-2.0-only",
        "gpl version 2": "GPL-2.0-only",
        "gnu general public license (gpl)": "GPL-2.0-only",
        "gnu general public license v2 (gplv2)": "GPL-2.0-only",
        "gnu general public license v2 or later (gplv2+)": "GPL-2.0-or-later",
        "bsd": "BSD-3-Clause",
        "mit": "MIT",
        "apache": "Apache-2.0",
        "apache 2.0": "Apache-2.0",
        "lgpl": "LGPL-2.1-only",
    }
    normalized = mapping.get(license_val.strip().lower())
    return normalized if normalized else license_val


def _add_entry_points(doc: tomlkit.TOMLDocument, metadata: dict) -> None:
    """Add entry points to the pyproject.toml document.

    PEP 621 splits entry points into three locations:
    - ``console_scripts`` -> ``[project.scripts]``
    - ``gui_scripts`` -> ``[project.gui-scripts]``
    - everything else -> ``[project.entry-points.GROUP]``

    The ``z3c.autoinclude.plugin`` group is particularly important for
    Plone — it's how add-ons register themselves for automatic ZCML
    loading.
    """
    entry_points = metadata.get("entry_points")
    if not entry_points:
        return

    # Handle string-format entry_points (INI-style)
    if isinstance(entry_points, str):
        entry_points = _parse_entry_points_string(entry_points)

    if not isinstance(entry_points, dict):
        return

    project = doc.get("project")
    if not project:
        return

    for group, entries in entry_points.items():
        if group == "console_scripts":
            scripts = tomlkit.table()
            for entry in entries:
                name, _, value = entry.partition("=")
                scripts.add(name.strip(), value.strip())
            project.add("scripts", scripts)
        elif group == "gui_scripts":
            scripts = tomlkit.table()
            for entry in entries:
                name, _, value = entry.partition("=")
                scripts.add(name.strip(), value.strip())
            project.add("gui-scripts", scripts)
        else:
            eps = doc.setdefault("project", tomlkit.table())
            ep_section = eps.setdefault("entry-points", tomlkit.table())
            group_table = tomlkit.table()
            for entry in entries:
                name, _, value = entry.partition("=")
                group_table.add(name.strip(), value.strip())
            ep_section.add(group, group_table)


def _parse_entry_points_string(text: str) -> dict:
    """Parse INI-style entry_points string format.

    Older setup.py files pass ``entry_points`` as a multi-line string
    rather than a dict.  The format is identical to INI/configparser
    syntax, so we reuse ``configparser`` to parse it.

    Example input::

        [console_scripts]
        my-command = my_package.cli:main
        [z3c.autoinclude.plugin]
        target = plone
    """
    cfg = configparser.ConfigParser()
    cfg.read_string(text)
    result = {}
    for section in cfg.sections():
        entries = []
        for key, val in cfg.items(section):
            entries.append(f"{key} = {val}")
        result[section] = entries
    return result


def _ensure_hatch_wheel_config(
    doc: tomlkit.TOMLDocument, metadata: dict, where: str
) -> None:
    """Add ``[tool.hatch.build.targets.wheel]`` with packages config.

    Hatchling needs to know where to find packages when using src-layout
    (``packages = ["src/plone"]``).  Without this, ``hatch build`` would
    fail to find the package directory.  We derive the top-level package
    name from the project name (e.g. ``plone.app.foo`` -> ``plone``).
    """
    tool = doc.setdefault("tool", tomlkit.table())
    hatch = tool.setdefault("hatch", tomlkit.table())
    build = hatch.setdefault("build", tomlkit.table())
    targets = build.setdefault("targets", tomlkit.table())

    if "wheel" not in targets:
        wheel = tomlkit.table()
        # Determine the actual package directory
        name = metadata.get("name", "unknown")
        # Convert dotted name to directory: plone.app.foo → plone (top-level in src)
        top_level = name.split(".")[0] if "." in name else name.replace("-", "_")
        packages_arr = tomlkit.array()
        packages_arr.append(f"{where}/{top_level}")
        wheel.add("packages", packages_arr)
        targets.add("wheel", wheel)


def _dict_to_tomlkit(d: dict) -> tomlkit.items.Table:
    """Recursively convert a plain dict to a tomlkit Table.

    Needed because tomlkit requires its own container types for
    serialization — plain dicts would lose type information
    (booleans serialized as strings, etc.).
    """
    table = tomlkit.table()
    for key, val in d.items():
        if isinstance(val, dict):
            table.add(key, _dict_to_tomlkit(val))
        elif isinstance(val, list):
            arr = tomlkit.array()
            for item in val:
                arr.append(item)
            table.add(key, arr)
        elif isinstance(val, (bool, int, float)):
            table.add(key, val)
        else:
            table.add(key, str(val))
    return table


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------


def cleanup_old_files(project_dir: Path, dry_run: bool = False) -> list[Path]:
    """Delete setup.py, setup.cfg, MANIFEST.in after migration.

    These files are no longer needed once pyproject.toml is in place.
    MANIFEST.in is also removed because hatchling uses its own inclusion
    logic (and respects .gitignore).  Keeping them around would cause
    confusion about which file is the source of truth.
    """
    deleted = []
    for name in ("setup.py", "setup.cfg", "MANIFEST.in"):
        filepath = project_dir / name
        if filepath.exists():
            if not dry_run:
                filepath.unlink()
            deleted.append(filepath)
    return deleted


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def migrate_packaging(
    project_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Run the full setup.py -> pyproject.toml migration.

    The migration is skipped entirely if an existing pyproject.toml already
    has a ``[project]`` section — this prevents overwriting a manually
    written or previously migrated configuration.

    Reads from both setup.py (AST) and setup.cfg (configparser), merges
    the results, generates pyproject.toml, and deletes the old files.

    Returns dict with ``created_files``, ``deleted_files``, ``warnings``.
    """
    result_warnings: list[str] = []
    created: list[Path] = []
    deleted: list[Path] = []

    # 1. Parse setup.py
    setup_py_data: dict = {}
    setup_py = project_dir / "setup.py"
    if setup_py.exists():
        setup_py_data = parse_setup_py(setup_py)
        result_warnings.extend(setup_py_data.pop("_warnings", []))

    # 2. Parse setup.cfg
    setup_cfg_data: dict = {}
    setup_cfg = project_dir / "setup.cfg"
    if setup_cfg.exists():
        setup_cfg_data = parse_setup_cfg(setup_cfg)

    if not setup_py_data and not setup_cfg_data:
        result_warnings.append("No setup.py or setup.cfg found to migrate")
        return {
            "created_files": created,
            "deleted_files": deleted,
            "warnings": result_warnings,
        }

    # 3. Merge metadata
    metadata = merge_metadata(setup_py_data, setup_cfg_data)

    # 4. Convert tool configs from setup.cfg
    tool_configs: dict | None = None
    if setup_cfg.exists():
        tool_configs = convert_tool_configs(setup_cfg)

    # 5. Read existing pyproject.toml (if any)
    pyproject_path = project_dir / "pyproject.toml"
    existing = None
    if pyproject_path.exists():
        existing = pyproject_path.read_text(encoding="utf-8")
        # If [project] section already exists, don't overwrite
        try:
            parsed = tomlkit.parse(existing)
            if "project" in parsed:
                result_warnings.append(
                    "pyproject.toml already has [project] section, skipping migration"
                )
                return {
                    "created_files": created,
                    "deleted_files": deleted,
                    "warnings": result_warnings,
                }
        except Exception:
            pass

    # 6. Generate pyproject.toml
    content = generate_pyproject_toml(metadata, existing, tool_configs)

    if not dry_run:
        pyproject_path.write_text(content, encoding="utf-8")
    created.append(pyproject_path)

    # 7. Clean up old files
    deleted = cleanup_old_files(project_dir, dry_run)

    return {
        "created_files": created,
        "deleted_files": deleted,
        "warnings": result_warnings,
    }
