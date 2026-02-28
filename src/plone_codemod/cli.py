#!/usr/bin/env python3
"""Plone 5.2 → 6.x Code Migration Runner.

Orchestrates all migration phases:
1. Python imports (libcst codemod)
2. ZCML dotted names
3. GenericSetup XML
4. Page templates (.pt)
5. Bootstrap 3→5 (opt-in via --bootstrap)
6. Audit (semgrep, optional)
7. Namespace packages → PEP 420 (opt-in via --namespaces)
8. setup.py → pyproject.toml (opt-in via --packaging)

Usage:
    plone-codemod ./src/
    plone-codemod ./src/ --dry-run
    plone-codemod ./src/ --bootstrap
    plone-codemod ./src/ --namespaces --packaging
    plone-codemod ./src/ --config custom_config.yaml
    plone-codemod ./src/ --skip-python --skip-audit
"""

from pathlib import Path
from plone_codemod.pt_migrator import migrate_bootstrap_files
from plone_codemod.pt_migrator import migrate_pt_files
from plone_codemod.zcml_migrator import migrate_genericsetup_files
from plone_codemod.zcml_migrator import migrate_zcml_files

import argparse
import shutil
import subprocess
import sys


_PKG_DIR = Path(__file__).resolve().parent


def run_python_migration(
    source_dir: Path,
    config_path: Path,
    dry_run: bool = False,
) -> None:
    """Run libcst-based Python import migration."""
    print("\n=== Phase 1: Python import migration (libcst) ===")

    try:
        import libcst  # noqa: F401
    except ImportError:
        print("  ERROR: libcst not installed. Run: pip install libcst pyyaml")
        return

    # Ensure .libcst.codemod.yaml exists in the source dir
    codemod_yaml = source_dir / ".libcst.codemod.yaml"
    if not codemod_yaml.exists():
        print(f"  Initializing libcst in {source_dir}")
        subprocess.run(
            [sys.executable, "-m", "libcst.tool", "initialize", str(source_dir)],
            check=False,
        )

    from plone_codemod.import_migrator import load_mappings

    mappings = load_mappings(config_path)
    print(f"  Loaded {len(mappings)} import mappings from {config_path}")

    # Group by unique (old_module, old_name) to avoid duplicate runs
    seen = set()
    unique_mappings = []
    for mp in mappings:
        key = (mp.old_module, mp.old_name)
        if key not in seen:
            seen.add(key)
            unique_mappings.append(mp)

    print(f"  Running PloneImportMigrator on {source_dir} ...")

    if dry_run:
        print("  [DRY RUN] Would apply all import migrations")
        for mp in unique_mappings[:10]:
            print(f"    {mp.old_module}.{mp.old_name} → {mp.new_module}.{mp.new_name}")
        if len(unique_mappings) > 10:
            print(f"    ... and {len(unique_mappings) - 10} more")
        return

    # Run the codemod via subprocess to ensure clean module state
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "libcst.tool",
            "codemod",
            "plone_codemod.import_migrator.PloneImportMigrator",
            str(source_dir),
        ],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0 and result.stderr:
        print(f"  stderr: {result.stderr}", file=sys.stderr)


def run_zcml_migration(
    source_dir: Path,
    config_path: Path,
    dry_run: bool = False,
) -> None:
    """Migrate ZCML files."""
    print("\n=== Phase 2: ZCML migration ===")
    modified = migrate_zcml_files(source_dir, config_path, dry_run=dry_run)
    _report(modified, "ZCML file", dry_run)


def run_genericsetup_migration(
    source_dir: Path,
    config_path: Path,
    dry_run: bool = False,
) -> None:
    """Migrate GenericSetup XML files."""
    print("\n=== Phase 3: GenericSetup XML migration ===")
    modified = migrate_genericsetup_files(source_dir, config_path, dry_run=dry_run)
    _report(modified, "XML file", dry_run)


def run_pt_migration(
    source_dir: Path,
    config_path: Path,
    dry_run: bool = False,
) -> None:
    """Migrate page templates."""
    print("\n=== Phase 4: Page template migration ===")
    modified = migrate_pt_files(source_dir, config_path, dry_run=dry_run)
    _report(modified, "page template", dry_run)


def run_bootstrap_migration(
    source_dir: Path,
    config_path: Path,
    dry_run: bool = False,
) -> None:
    """Migrate Bootstrap 3→5 in templates."""
    print("\n=== Phase 5: Bootstrap 3 → 5 migration ===")
    modified = migrate_bootstrap_files(source_dir, config_path, dry_run=dry_run)
    _report(modified, "file", dry_run)


def run_audit(source_dir: Path) -> None:
    """Use semgrep to find remaining unmigrated patterns."""
    print("\n=== Phase 6: Audit (semgrep) ===")
    semgrep_rules = _PKG_DIR / "semgrep_rules"

    if not shutil.which("semgrep"):
        print("  semgrep not installed. Skipping audit.")
        print("  Install with: pip install semgrep")
        print("  Or use: semgrep --config", semgrep_rules, str(source_dir))
        return

    result = subprocess.run(
        [
            "semgrep",
            "--config",
            str(semgrep_rules),
            str(source_dir),
            "--no-git-ignore",
        ],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0 and result.stderr:
        for line in result.stderr.splitlines():
            if "error" in line.lower() or "finding" in line.lower():
                print(f"  {line}")


def run_namespace_migration(
    project_dir: Path,
    dry_run: bool = False,
) -> None:
    """Phase 7: Migrate to PEP 420 implicit namespace packages."""
    print("\n=== Phase 7: Namespace package migration (PEP 420) ===")
    from plone_codemod.namespace_migrator import migrate_namespaces

    result = migrate_namespaces(project_dir, dry_run=dry_run)
    prefix = "[DRY RUN] Would delete" if dry_run else "Deleted"
    for f in result["deleted_files"]:
        print(f"  {prefix}: {f}")
    prefix = "[DRY RUN] Would modify" if dry_run else "Modified"
    for f in result["modified_files"]:
        print(f"  {prefix}: {f}")
    total = len(result["deleted_files"]) + len(result["modified_files"])
    if not total:
        print("  No namespace package declarations found.")
    else:
        print(f"  Processed {total} file(s).")


def run_packaging_migration(
    project_dir: Path,
    dry_run: bool = False,
) -> None:
    """Phase 8: Migrate setup.py → pyproject.toml."""
    print("\n=== Phase 8: setup.py → pyproject.toml migration ===")
    from plone_codemod.packaging_migrator import migrate_packaging

    result = migrate_packaging(project_dir, dry_run=dry_run)
    prefix = "[DRY RUN] Would create" if dry_run else "Created"
    for f in result["created_files"]:
        print(f"  {prefix}: {f}")
    prefix = "[DRY RUN] Would delete" if dry_run else "Deleted"
    for f in result["deleted_files"]:
        print(f"  {prefix}: {f}")
    for w in result["warnings"]:
        print(f"  WARNING: {w}")
    if not result["created_files"] and not result["deleted_files"]:
        print("  No packaging changes needed.")


def _report(modified: list[Path], label: str, dry_run: bool) -> None:
    prefix = "[DRY RUN] Would modify" if dry_run else "Modified"
    for f in modified:
        print(f"  {prefix}: {f}")
    if not modified:
        print(f"  No {label}s needed changes.")
    else:
        print(f"  {prefix} {len(modified)} {label}(s).")


def main():
    parser = argparse.ArgumentParser(
        description="Plone 5.2 → 6.x Code Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    plone-codemod ./src/                                 # Full migration (no BS)
    plone-codemod ./src/ --dry-run                       # Preview changes
    plone-codemod ./src/ --bootstrap                     # Include Bootstrap 3→5
    plone-codemod ./src/ --bootstrap --dry-run           # Preview with Bootstrap
    plone-codemod ./src/ --skip-python                   # Only ZCML + XML + PT
    plone-codemod ./src/ --skip-audit                    # Skip semgrep audit
    plone-codemod ./src/ --config my_config.yaml         # Custom config
    plone-codemod ./src/ --namespaces                    # Remove namespace pkg declarations
    plone-codemod ./src/ --packaging                     # Convert setup.py → pyproject.toml
    plone-codemod ./src/ --namespaces --packaging        # Both (recommended order)
    plone-codemod ./src/ --packaging --project-dir /path # Explicit project root
        """,
    )
    parser.add_argument(
        "source_dir",
        type=Path,
        help="Root directory of the source code to migrate",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_PKG_DIR / "migration_config.yaml",
        help="Path to migration_config.yaml (default: bundled config)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would change without writing files",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Enable Bootstrap 3→5 migration (opt-in, not run by default)",
    )
    parser.add_argument(
        "--skip-python", action="store_true", help="Skip Python import migration"
    )
    parser.add_argument("--skip-zcml", action="store_true", help="Skip ZCML migration")
    parser.add_argument(
        "--skip-xml", action="store_true", help="Skip GenericSetup XML migration"
    )
    parser.add_argument(
        "--skip-pt", action="store_true", help="Skip page template migration"
    )
    parser.add_argument(
        "--skip-audit", action="store_true", help="Skip semgrep audit phase"
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help="Project root directory (where setup.py/pyproject.toml live). "
        "Defaults to parent of source_dir.",
    )
    parser.add_argument(
        "--namespaces",
        action="store_true",
        help="Enable PEP 420 namespace package migration (opt-in)",
    )
    parser.add_argument(
        "--packaging",
        action="store_true",
        help="Enable setup.py → pyproject.toml migration (opt-in)",
    )

    args = parser.parse_args()

    if not args.source_dir.is_dir():
        parser.error(f"Not a directory: {args.source_dir}")

    print("Plone 5.2 → 6.x Migration Tool")
    print(f"Source: {args.source_dir.resolve()}")
    print(f"Config: {args.config}")
    if args.dry_run:
        print("Mode: DRY RUN (no files will be modified)")
    if args.bootstrap:
        print("Bootstrap: ENABLED (BS3 → BS5 migration)")

    project_dir = args.project_dir or args.source_dir.resolve().parent
    if args.namespaces:
        print(f"Namespaces: ENABLED (PEP 420 migration, project: {project_dir})")
    if args.packaging:
        print(f"Packaging: ENABLED (setup.py → pyproject.toml, project: {project_dir})")

    if not args.skip_python:
        run_python_migration(args.source_dir, args.config, args.dry_run)

    if not args.skip_zcml:
        run_zcml_migration(args.source_dir, args.config, args.dry_run)

    if not args.skip_xml:
        run_genericsetup_migration(args.source_dir, args.config, args.dry_run)

    if not args.skip_pt:
        run_pt_migration(args.source_dir, args.config, args.dry_run)

    if args.bootstrap:
        run_bootstrap_migration(args.source_dir, args.config, args.dry_run)

    if not args.skip_audit:
        run_audit(args.source_dir)

    # Phase 7: Namespace migration (runs before packaging so namespace_packages
    # is cleaned from setup.py before pyproject.toml generation)
    if args.namespaces:
        run_namespace_migration(project_dir, args.dry_run)

    # Phase 8: Packaging migration
    if args.packaging:
        run_packaging_migration(project_dir, args.dry_run)

    print("\n=== Done ===")
    print("Review changes with: git diff")
    print(
        "If satisfied, commit with: git add -A && git commit -m 'Migrate to Plone 6.x'"
    )


if __name__ == "__main__":
    main()
