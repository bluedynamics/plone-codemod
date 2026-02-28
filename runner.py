#!/usr/bin/env python3
"""Plone 5.2 → 6.x Code Migration Runner.

Orchestrates all migration phases:
1. Python imports (libcst codemod)
2. ZCML dotted names
3. GenericSetup XML
4. Audit (semgrep, optional)

Usage:
    python runner.py ./src/
    python runner.py ./src/ --dry-run
    python runner.py ./src/ --config custom_config.yaml
    python runner.py ./src/ --skip-python --skip-audit
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Allow running from the plone-codemod directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from zcml.zcml_migrator import migrate_genericsetup_files, migrate_zcml_files


def run_python_migration(
    source_dir: Path,
    config_path: Path,
    dry_run: bool = False,
) -> None:
    """Run libcst-based Python import migration."""
    print("\n=== Phase 1: Python import migration (libcst) ===")

    # Check that libcst is available
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
        # Add our codemods directory to the module search path
        if codemod_yaml.exists():
            content = codemod_yaml.read_text()
            if "modules" not in content:
                codemod_yaml.write_text(
                    content.rstrip()
                    + f"\nmodules:\n  - '{Path(__file__).resolve().parent}'\n"
                )

    # Use the built-in RenameCommand for each mapping
    # This is the most reliable approach — one rename at a time
    from codemods.import_migrator import load_mappings

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

    # Run our custom codemod which handles all mappings in a single pass
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
            "codemods.import_migrator.PloneImportMigrator",
            str(source_dir),
        ],
        cwd=str(Path(__file__).resolve().parent),
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
    prefix = "[DRY RUN] Would modify" if dry_run else "Modified"
    for f in modified:
        print(f"  {prefix}: {f}")
    if not modified:
        print("  No ZCML files needed changes.")
    else:
        print(f"  {prefix} {len(modified)} ZCML file(s).")


def run_genericsetup_migration(
    source_dir: Path,
    config_path: Path,
    dry_run: bool = False,
) -> None:
    """Migrate GenericSetup XML files."""
    print("\n=== Phase 3: GenericSetup XML migration ===")
    modified = migrate_genericsetup_files(source_dir, config_path, dry_run=dry_run)
    prefix = "[DRY RUN] Would modify" if dry_run else "Modified"
    for f in modified:
        print(f"  {prefix}: {f}")
    if not modified:
        print("  No GenericSetup XML files needed changes.")
    else:
        print(f"  {prefix} {len(modified)} XML file(s).")


def run_audit(source_dir: Path) -> None:
    """Use semgrep to find remaining unmigrated patterns."""
    print("\n=== Phase 4: Audit (semgrep) ===")
    semgrep_rules = Path(__file__).resolve().parent / "semgrep_rules"

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
        # semgrep prints info to stderr even on success
        for line in result.stderr.splitlines():
            if "error" in line.lower() or "finding" in line.lower():
                print(f"  {line}")


def main():
    parser = argparse.ArgumentParser(
        description="Plone 5.2 → 6.x Code Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python runner.py ./src/                         # Full migration
    python runner.py ./src/ --dry-run               # Preview changes
    python runner.py ./src/ --skip-python           # Only ZCML + XML
    python runner.py ./src/ --skip-audit            # Skip semgrep audit
    python runner.py ./src/ --config my_config.yaml # Custom config
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
        default=Path(__file__).resolve().parent / "migration_config.yaml",
        help="Path to migration_config.yaml (default: bundled config)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would change without writing files",
    )
    parser.add_argument("--skip-python", action="store_true", help="Skip Python import migration")
    parser.add_argument("--skip-zcml", action="store_true", help="Skip ZCML migration")
    parser.add_argument("--skip-xml", action="store_true", help="Skip GenericSetup XML migration")
    parser.add_argument("--skip-audit", action="store_true", help="Skip semgrep audit phase")

    args = parser.parse_args()

    if not args.source_dir.is_dir():
        parser.error(f"Not a directory: {args.source_dir}")

    print(f"Plone 5.2 → 6.x Migration Tool")
    print(f"Source: {args.source_dir.resolve()}")
    print(f"Config: {args.config}")
    if args.dry_run:
        print("Mode: DRY RUN (no files will be modified)")

    if not args.skip_python:
        run_python_migration(args.source_dir, args.config, args.dry_run)

    if not args.skip_zcml:
        run_zcml_migration(args.source_dir, args.config, args.dry_run)

    if not args.skip_xml:
        run_genericsetup_migration(args.source_dir, args.config, args.dry_run)

    if not args.skip_audit:
        run_audit(args.source_dir)

    print("\n=== Done ===")
    print("Review changes with: git diff")
    print("If satisfied, commit with: git add -A && git commit -m 'Migrate to Plone 6.x'")


if __name__ == "__main__":
    main()
