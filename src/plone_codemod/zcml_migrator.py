"""Migrate dotted names in ZCML and GenericSetup XML files.

ZCML files contain Python dotted names in attributes like class=, for=,
provides=, interface=, etc. This module rewrites those based on the
migration_config.yaml mappings.

GenericSetup XML (registry.xml, types/*.xml) also contains dotted name
references and view name references that need updating.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml


CONFIG_PATH = Path(__file__).resolve().parent / "migration_config.yaml"

# ZCML/XML attributes that may contain Python dotted names
DOTTED_NAME_ATTRS = [
    "class",
    "factory",
    "for",
    "handler",
    "interface",
    "layer",
    "provides",
    "schema",
    "type",
    "component",
    "permission",
    "view",
    "menu",
]


def load_config(config_path: Path = CONFIG_PATH) -> dict[str, Any]:
    with open(config_path) as fh:
        return yaml.safe_load(fh)


def _build_replacements(entries: list[dict[str, str]]) -> list[tuple[str, str]]:
    """Build sorted replacement pairs (longest old first to avoid partial matches)."""
    pairs = [(e["old"], e["new"]) for e in entries]
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def migrate_zcml_content(content: str, replacements: list[tuple[str, str]]) -> str:
    """Apply dotted-name replacements to ZCML content."""
    result = content
    for old, new in replacements:
        # Match dotted names inside attribute values (quoted)
        # We replace anywhere the old string appears inside quotes
        result = result.replace(old, new)
    return result


def migrate_genericsetup_content(
    content: str,
    replacements: list[tuple[str, str]],
    view_replacements: dict[str, str] | None = None,
) -> str:
    """Apply dotted-name + view replacements to GenericSetup XML content."""
    result = content
    for old, new in replacements:
        result = result.replace(old, new)

    if view_replacements:
        for old_view, new_view in view_replacements.items():
            # Replace view names in XML element values and attributes
            # e.g. <element value="folder_summary_view" />
            # e.g. <property name="default_view">folder_summary_view</property>
            result = result.replace(f'"{old_view}"', f'"{new_view}"')
            result = result.replace(f">{old_view}<", f">{new_view}<")

    return result


def migrate_file(
    filepath: Path, transformer: Callable[..., str], **kwargs: Any
) -> bool:
    """Read file, apply transformer, write back if changed. Returns True if modified."""
    content = filepath.read_text(encoding="utf-8")
    new_content = transformer(content, **kwargs)
    if new_content != content:
        filepath.write_text(new_content, encoding="utf-8")
        return True
    return False


def migrate_zcml_files(
    root: Path,
    config_path: Path = CONFIG_PATH,
    dry_run: bool = False,
) -> list[Path]:
    """Walk directory and migrate all .zcml files."""
    config = load_config(config_path)
    replacements = _build_replacements(config.get("zcml", []))

    modified = []
    for zcml_file in sorted(root.rglob("*.zcml")):
        if dry_run:
            content = zcml_file.read_text(encoding="utf-8")
            new_content = migrate_zcml_content(content, replacements)
            if new_content != content:
                modified.append(zcml_file)
        else:
            if migrate_file(zcml_file, migrate_zcml_content, replacements=replacements):
                modified.append(zcml_file)

    return modified


def migrate_genericsetup_files(
    root: Path,
    config_path: Path = CONFIG_PATH,
    dry_run: bool = False,
) -> list[Path]:
    """Walk directory and migrate GenericSetup XML files (profiles/**/*.xml)."""
    config = load_config(config_path)
    gs_config = config.get("genericsetup", {})

    # Build dotted-name replacements
    dotted_entries = gs_config.get("dotted_names", [])
    replacements = _build_replacements(dotted_entries)

    # View replacements
    view_replacements = gs_config.get("view_replacements")

    modified = []
    # Look for XML files in profiles/ directories and also top-level XML
    for xml_file in sorted(root.rglob("*.xml")):
        # Skip non-GenericSetup files
        if ".zcml" in xml_file.suffixes:
            continue
        # Focus on profiles directories and registry files
        parts_str = str(xml_file)
        if "profiles" not in parts_str and "registry.xml" not in xml_file.name:
            continue

        if dry_run:
            content = xml_file.read_text(encoding="utf-8")
            new_content = migrate_genericsetup_content(
                content, replacements, view_replacements
            )
            if new_content != content:
                modified.append(xml_file)
        else:
            if migrate_file(
                xml_file,
                migrate_genericsetup_content,
                replacements=replacements,
                view_replacements=view_replacements,
            ):
                modified.append(xml_file)

    return modified
