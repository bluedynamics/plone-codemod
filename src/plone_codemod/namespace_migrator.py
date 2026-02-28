"""Migrate from pkg_resources/pkgutil namespace packages to PEP 420 implicit.

Plone packages historically use explicit namespace packages (pkg_resources or
pkgutil style) to split packages like ``plone.app.*`` across multiple
distributions.  Since Python 3.3 (PEP 420), implicit namespace packages
make these declarations unnecessary — the mere absence of ``__init__.py``
is enough.  Removing the old declarations is a prerequisite for modern
packaging (hatchling/flit) because setuptools' ``namespace_packages``
kwarg has no equivalent in PEP 621.

Detects and removes namespace declarations from ``__init__.py`` files:
- pkg_resources style: ``__import__('pkg_resources').declare_namespace(...)``
- pkgutil style: ``from pkgutil import extend_path; __path__ = ...``

Also cleans up ``namespace_packages`` from setup.py/setup.cfg.
"""

from pathlib import Path

import ast
import re


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

# pkg_resources: __import__('pkg_resources').declare_namespace(__name__)
_RE_PKG_RESOURCES = re.compile(
    r"""^\s*__import__\(\s*['"]pkg_resources['"]\s*\)"""
    r"""\s*\.\s*declare_namespace\(\s*__name__\s*\)""",
)

# pkgutil: from pkgutil import extend_path
_RE_PKGUTIL_IMPORT = re.compile(
    r"^\s*from\s+pkgutil\s+import\s+extend_path\s*$",
)

# pkgutil: __path__ = extend_path(__path__, __name__)
_RE_PKGUTIL_PATH = re.compile(
    r"^\s*__path__\s*=\s*extend_path\(\s*__path__\s*,\s*__name__\s*\)",
)


def is_namespace_declaration(line: str) -> bool:
    """Return True if *line* is a namespace package declaration.

    Operates on individual lines (not multi-line content) because the
    regexes use ``^`` anchors.  Blank lines and comments are excluded
    so callers can iterate over a file and classify each line.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    return bool(
        _RE_PKG_RESOURCES.match(line)
        or _RE_PKGUTIL_IMPORT.match(line)
        or _RE_PKGUTIL_PATH.match(line)
    )


def has_namespace_declaration(content: str) -> bool:
    """Return True if *content* contains any namespace declaration."""
    return any(is_namespace_declaration(line) for line in content.splitlines())


def is_only_namespace_init(content: str) -> bool:
    """Return True if the file contains only namespace declarations.

    This distinction matters because namespace-only ``__init__.py`` files
    should be *deleted* entirely (PEP 420 requires their absence), while
    files that mix namespace declarations with real code (e.g. package-level
    API imports) should only have the declaration *stripped*.

    Allows comments, blank lines, try/except wrappers, and encoding cookies
    alongside the declaration — these are all part of the boilerplate.
    """
    if not has_namespace_declaration(content):
        return False
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if is_namespace_declaration(line):
            continue
        # try / except / pass are part of the common wrapper
        if stripped in ("try:", "except ImportError:", "except:", "pass"):
            continue
        # Any other real code → not namespace-only
        return False
    return True


# ---------------------------------------------------------------------------
# Removal
# ---------------------------------------------------------------------------


def remove_namespace_declaration(content: str) -> str:
    """Remove namespace declarations from *content*, preserving other code.

    Uses a line-by-line state machine rather than simple regex substitution
    because declarations can span multiple lines in structured patterns
    (try/except blocks, import + assignment pairs) and we need to remove
    the entire construct — including surrounding blank lines — without
    leaving awkward whitespace gaps.

    Handles:
    - Simple single-line declarations
    - try/except ImportError wrappers around pkg_resources (very common in
      Plone ecosystem — the try/except was needed for editable installs)
    - pkgutil import + ``__path__`` assignment pairs (always appear together)
    """
    lines = content.splitlines(keepends=True)
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Detect try/except wrapper for pkg_resources
        if stripped == "try:":
            # Look ahead for the pkg_resources pattern inside try block
            block = _collect_try_except_block(lines, i)
            if block is not None:
                # Check each line in the block for pkg_resources
                if any(_RE_PKG_RESOURCES.match(ln) for ln in lines[i : i + block]):
                    i += block
                    # Skip trailing blank lines after the block
                    while i < len(lines) and not lines[i].strip():
                        i += 1
                    continue

        # Simple pkg_resources line
        if _RE_PKG_RESOURCES.match(line):
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            continue

        # pkgutil import line
        if _RE_PKGUTIL_IMPORT.match(line):
            i += 1
            # Also consume the __path__ = extend_path(...) line that follows
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines) and _RE_PKGUTIL_PATH.match(lines[i]):
                i += 1
                while i < len(lines) and not lines[i].strip():
                    i += 1
            continue

        # Standalone __path__ = extend_path(...) (shouldn't happen alone, but be safe)
        if _RE_PKGUTIL_PATH.match(line):
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            continue

        result.append(line)
        i += 1

    # Strip leading blank lines from result
    text = "".join(result)
    return text.strip("\n") + "\n" if text.strip() else ""


def _collect_try_except_block(lines: list[str], start: int) -> int | None:
    """Return the number of lines in a try/except block starting at *start*.

    Many Plone packages wrap the pkg_resources declaration in
    ``try: ... except ImportError: pass`` so the package still works
    when installed without pkg_resources.  We need to detect the full
    block boundary so ``remove_namespace_declaration`` can strip the
    entire construct, not just the inner declaration line.

    Returns None if the structure doesn't look like a simple try/except
    block (e.g. has an else/finally clause or complex body).
    """
    if start >= len(lines):
        return None
    if lines[start].strip() != "try:":
        return None

    i = start + 1
    # Skip body of try (indented lines)
    while i < len(lines) and (lines[i].strip() == "" or _is_indented(lines[i])):
        i += 1

    # Expect except line
    if i >= len(lines):
        return None
    stripped = lines[i].strip()
    if not stripped.startswith("except"):
        return None
    i += 1

    # Skip body of except (indented lines — typically just 'pass')
    while i < len(lines) and (lines[i].strip() == "" or _is_indented(lines[i])):
        i += 1

    return i - start


def _is_indented(line: str) -> bool:
    """Return True if line starts with whitespace (is indented)."""
    return bool(line) and line[0] in (" ", "\t") and line.strip() != ""


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------


def find_namespace_init_files(
    project_dir: Path,
) -> list[tuple[Path, bool]]:
    """Find ``__init__.py`` files with namespace declarations.

    Walks the project tree to find all namespace init files, skipping
    build artifacts (``.egg-info``, ``build/``, ``dist/``) and hidden
    directories that should never be migrated.

    Returns list of ``(path, delete_entirely)`` tuples.  The boolean
    tells the caller whether to *delete* the file (namespace-only) or
    *edit* it (mixed content) — see ``is_only_namespace_init``.
    """
    results = []
    for init_file in sorted(project_dir.rglob("__init__.py")):
        # Skip hidden dirs, build dirs, egg-info
        parts = init_file.relative_to(project_dir).parts
        if any(p.startswith(".") or p in ("build", "dist") or p.endswith(".egg-info") for p in parts):
            continue
        try:
            content = init_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if has_namespace_declaration(content):
            results.append((init_file, is_only_namespace_init(content)))
    return results


def clean_setup_py_namespaces(project_dir: Path, dry_run: bool = False) -> bool:
    """Remove ``namespace_packages`` and related ``setup_requires`` from setup.py.

    Uses AST to *verify* the keyword exists (reliable detection), then
    does text-level removal (preserves formatting).  Pure-AST rewriting
    would lose comments and whitespace; pure-regex could false-positive
    on commented-out code.  The hybrid approach gives us the best of both.

    Also removes ``setup_requires=['setuptools']`` because that dependency
    only existed to support the pkg_resources namespace mechanism.
    """
    setup_py = project_dir / "setup.py"
    if not setup_py.exists():
        return False

    content = setup_py.read_text(encoding="utf-8")

    # Use AST to verify the keyword exists, then do text-level removal
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False

    has_ns_packages = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_setup_call(node):
            for kw in node.keywords:
                if kw.arg == "namespace_packages":
                    has_ns_packages = True

    if not has_ns_packages:
        return False

    # Text-level removal: namespace_packages=[...] (possibly multi-line)
    new_content = _remove_setup_kwarg(content, "namespace_packages")

    # Also remove setup_requires=['setuptools'] if present (only needed for pkg_resources ns)
    new_content = _remove_setup_kwarg(new_content, "setup_requires")

    if new_content == content:
        return False

    if not dry_run:
        setup_py.write_text(new_content, encoding="utf-8")
    return True


def clean_setup_cfg_namespaces(project_dir: Path, dry_run: bool = False) -> bool:
    """Remove ``namespace_packages`` from setup.cfg ``[options]``.

    The ``namespace_packages`` option in setup.cfg has no PEP 621
    equivalent — it must simply be removed.  The regex handles
    continuation lines (indented values on subsequent lines) that
    are common in multi-namespace packages.
    """
    setup_cfg = project_dir / "setup.cfg"
    if not setup_cfg.exists():
        return False

    content = setup_cfg.read_text(encoding="utf-8")
    # Match the namespace_packages line and any continuation lines (indented)
    pattern = re.compile(
        r"^namespace_packages\s*=.*(?:\n[ \t]+\S.*)*\n?",
        re.MULTILINE,
    )
    new_content = pattern.sub("", content)

    if new_content == content:
        return False

    if not dry_run:
        setup_cfg.write_text(new_content, encoding="utf-8")
    return True


def _is_setup_call(node: ast.Call) -> bool:
    """Check if an AST Call node is a ``setup()`` call.

    Matches both bare ``setup(...)`` and qualified ``setuptools.setup(...)``
    because Plone packages use both import styles.
    """
    func = node.func
    if isinstance(func, ast.Name) and func.id == "setup":
        return True
    if isinstance(func, ast.Attribute) and func.attr == "setup":
        return True
    return False


def _remove_setup_kwarg(content: str, kwarg_name: str) -> str:
    """Remove a keyword argument from a ``setup()`` call in source text.

    Uses cascading regex patterns (single-line list, multi-line list,
    simple value) because setup.py files in the wild use all three
    formats.  Each pattern is tried in order; the first match wins.
    This is intentionally text-level (not AST-based) to preserve the
    surrounding formatting and comments.
    """
    # Pattern: kwarg_name=[...] or kwarg_name=<value>, possibly multi-line
    # We match from kwarg_name= to the closing bracket/comma
    pattern = re.compile(
        rf"^(\s*){kwarg_name}\s*=\s*\[.*?\][ \t]*,?[ \t]*\n?",
        re.MULTILINE | re.DOTALL,
    )
    result = pattern.sub("", content)
    if result != content:
        return result

    # Try multi-line: kwarg_name=[\n  ...\n],
    pattern_ml = re.compile(
        rf"^\s*{kwarg_name}\s*=\s*\[.*?\]\s*,?\s*$",
        re.MULTILINE | re.DOTALL,
    )
    result = pattern_ml.sub("", content)
    if result != content:
        return result

    # Simple value: kwarg_name='something',
    pattern_simple = re.compile(
        rf"^\s*{kwarg_name}\s*=.*,?\s*$\n?",
        re.MULTILINE,
    )
    return pattern_simple.sub("", content)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def migrate_namespaces(
    project_dir: Path,
    _source_dir: Path | None = None,
    dry_run: bool = False,
) -> dict:
    """Run the full namespace migration.

    Processes ``__init__.py`` files first, then cleans setup.py/setup.cfg.
    This order doesn't strictly matter for correctness, but it ensures
    that if the process is interrupted, the ``__init__.py`` files (the
    most important part) are already fixed.

    This phase is designed to run *before* the packaging migration
    (Phase 8), so that ``namespace_packages`` is already gone from
    setup.py by the time it gets parsed for pyproject.toml generation.

    Returns dict with ``deleted_files``, ``modified_files`` lists.
    """
    deleted: list[Path] = []
    modified: list[Path] = []

    # 1. Find and process __init__.py files
    init_files = find_namespace_init_files(project_dir)
    for filepath, delete_entirely in init_files:
        if delete_entirely:
            if not dry_run:
                filepath.unlink()
            deleted.append(filepath)
        else:
            content = filepath.read_text(encoding="utf-8")
            new_content = remove_namespace_declaration(content)
            if new_content != content:
                if not dry_run:
                    filepath.write_text(new_content, encoding="utf-8")
                modified.append(filepath)

    # 2. Clean setup.py
    if clean_setup_py_namespaces(project_dir, dry_run):
        modified.append(project_dir / "setup.py")

    # 3. Clean setup.cfg
    if clean_setup_cfg_namespaces(project_dir, dry_run):
        modified.append(project_dir / "setup.cfg")

    return {"deleted_files": deleted, "modified_files": modified}
