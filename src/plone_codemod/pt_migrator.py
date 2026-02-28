"""Migrate Plone page templates (.pt files).

Safe automated fixes:
- context/main_template → context/@@main_template (acquisition → browser view)
- here/ → context/ (deprecated alias)

Optional Bootstrap 3→5 migration (--bootstrap flag):
- data-toggle → data-bs-toggle (and other data attributes)
- CSS class renames (pull-right → float-end, panel → card, etc.)
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml


CONFIG_PATH = Path(__file__).resolve().parent / "migration_config.yaml"


def load_config(config_path: Path = CONFIG_PATH) -> dict[str, Any]:
    with open(config_path) as fh:
        return yaml.safe_load(fh)


def migrate_pt_content(
    content: str,
    replacements: list[dict[str, str]],
) -> str:
    """Apply page template replacements."""
    result = content
    for entry in replacements:
        result = result.replace(entry["old"], entry["new"])
    return result


def migrate_bootstrap_content(
    content: str,
    data_attributes: list[dict[str, str]],
    css_classes: list[dict[str, str]],
) -> str:
    """Apply Bootstrap 3→5 migrations to HTML/PT content."""
    result = content
    for entry in data_attributes:
        result = result.replace(entry["old"], entry["new"])
    for entry in css_classes:
        result = result.replace(entry["old"], entry["new"])
    return result


def _migrate_files(
    root: Path,
    pattern: str,
    transformer: Callable[..., str],
    dry_run: bool = False,
    **kwargs: Any,
) -> list[Path]:
    """Walk directory, apply transformer to matching files."""
    modified = []
    for filepath in sorted(root.rglob(pattern)):
        content = filepath.read_text(encoding="utf-8")
        new_content = transformer(content, **kwargs)
        if new_content != content:
            modified.append(filepath)
            if not dry_run:
                filepath.write_text(new_content, encoding="utf-8")
    return modified


def migrate_pt_files(
    root: Path,
    config_path: Path = CONFIG_PATH,
    dry_run: bool = False,
) -> list[Path]:
    """Migrate .pt files with safe Plone 6 fixes."""
    config = load_config(config_path)
    replacements = config.get("pagetemplates", [])
    if not replacements:
        return []
    return _migrate_files(
        root,
        "*.pt",
        migrate_pt_content,
        dry_run=dry_run,
        replacements=replacements,
    )


def migrate_bootstrap_files(
    root: Path,
    config_path: Path = CONFIG_PATH,
    dry_run: bool = False,
) -> list[Path]:
    """Migrate Bootstrap 3→5 in .pt, .html, and .xml files."""
    config = load_config(config_path)
    bs_config = config.get("bootstrap", {})
    data_attributes = bs_config.get("data_attributes", [])
    css_classes = bs_config.get("css_classes", [])

    if not data_attributes and not css_classes:
        return []

    modified = []
    for pattern in ("*.pt", "*.html"):
        modified.extend(
            _migrate_files(
                root,
                pattern,
                migrate_bootstrap_content,
                dry_run=dry_run,
                data_attributes=data_attributes,
                css_classes=css_classes,
            )
        )
    return modified
