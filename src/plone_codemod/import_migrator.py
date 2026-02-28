"""libcst-based codemod for migrating Plone 5.2 imports to Plone 6.x.

Reads migration mappings from migration_config.yaml and rewrites:
- Import statements (from X import Y → from A import B)
- Usage sites when names changed (safe_unicode → safe_text)
- Handles multi-line imports, aliased imports, mixed imports

Usage with libcst CLI:
    python -m libcst.tool codemod plone_codemod.import_migrator.PloneImportMigrator .

Usage programmatically:
    from plone_codemod.import_migrator import transform_code
    new_source = transform_code(old_source)
"""

from collections import defaultdict
from dataclasses import dataclass
from libcst.codemod import CodemodContext
from libcst.codemod import VisitorBasedCodemodCommand
from pathlib import Path

import libcst as cst
import yaml


CONFIG_PATH = Path(__file__).resolve().parent / "migration_config.yaml"


@dataclass(frozen=True)
class ImportMapping:
    old_module: str
    old_name: str
    new_module: str
    new_name: str


def load_mappings(config_path: Path = CONFIG_PATH) -> list[ImportMapping]:
    with open(config_path) as fh:
        config = yaml.safe_load(fh)

    mappings = []
    for entry in config.get("imports", []):
        old_parts = entry["old"].rsplit(".", 1)
        new_parts = entry["new"].rsplit(".", 1)
        if len(old_parts) != 2 or len(new_parts) != 2:
            continue
        mappings.append(
            ImportMapping(
                old_module=old_parts[0],
                old_name=old_parts[1],
                new_module=new_parts[0],
                new_name=new_parts[1],
            )
        )
    return mappings


class PloneImportMigrator(VisitorBasedCodemodCommand):
    DESCRIPTION = "Migrate Plone 5.2 imports to Plone 6.x (config-driven)"

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)

        self._mappings = load_mappings()

        # (old_module, old_name) → ImportMapping
        self._lookup: dict[tuple[str, str], ImportMapping] = {}
        for mp in self._mappings:
            self._lookup[(mp.old_module, mp.old_name)] = mp

        # Track renames needed in this file: old_name → new_name
        self._renames: dict[str, str] = {}

        # Collect new imports per SimpleStatementLine
        self._pending_imports: list[cst.SimpleStatementLine] = []

    def visit_Module(self, node: cst.Module) -> None:
        self._renames = {}
        self._pending_imports = []

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        """First pass: detect which names need renaming at usage sites."""
        module_name = self._dotted(node.module)
        if module_name is None:
            return
        if isinstance(node.names, cst.ImportStar):
            return

        for alias in node.names:
            if not isinstance(alias.name, cst.Name):
                continue
            old_name = alias.name.value
            key = (module_name, old_name)
            mp = self._lookup.get(key)
            if mp and mp.new_name != mp.old_name and alias.asname is None:
                self._renames[old_name] = mp.new_name

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> (
        cst.SimpleStatementLine
        | cst.RemovalSentinel
        | cst.FlattenSentinel[cst.BaseStatement]
    ):
        """Handle import statement rewriting at the statement line level.

        This allows us to split one import line into multiple when names
        move to different modules.
        """
        # Use original_node for lookups because leave_Name may have
        # already renamed identifiers in updated_node
        if len(original_node.body) != 1:
            return updated_node
        orig_stmt = original_node.body[0]
        if not isinstance(orig_stmt, cst.ImportFrom):
            return updated_node

        module_name = self._dotted(orig_stmt.module)
        if module_name is None:
            return updated_node

        # Handle star imports
        if isinstance(orig_stmt.names, cst.ImportStar):
            for mp in self._mappings:
                if mp.old_module == module_name:
                    new_stmt = orig_stmt.with_changes(
                        module=self._build_module(mp.new_module)
                    )
                    return updated_node.with_changes(body=[new_stmt])
            return updated_node

        # Check if any names in this import need migration
        has_migration = False
        for alias in orig_stmt.names:
            if isinstance(alias.name, cst.Name):
                key = (module_name, alias.name.value)
                if key in self._lookup:
                    has_migration = True
                    break

        if not has_migration:
            return updated_node

        # Split names into: kept (no migration) and migrated (grouped by new module)
        kept: list[cst.ImportAlias] = []
        # new_module → list of ImportAlias
        migrated: dict[str, list[cst.ImportAlias]] = defaultdict(list)

        for alias in orig_stmt.names:
            if not isinstance(alias.name, cst.Name):
                kept.append(alias)
                continue

            old_name = alias.name.value
            key = (module_name, old_name)
            mp = self._lookup.get(key)

            if mp is None:
                kept.append(alias)
                continue

            # Build new alias
            new_alias_name = cst.Name(mp.new_name)
            if alias.asname is not None:
                # Keep the alias
                new_alias = cst.ImportAlias(
                    name=new_alias_name,
                    asname=alias.asname,
                )
            else:
                new_alias = cst.ImportAlias(name=new_alias_name)

            migrated[mp.new_module].append(new_alias)

        # Build result statements
        result_stmts: list[cst.BaseStatement] = []

        # Keep remaining names in the original import
        if kept:
            # Clean trailing comma
            cleaned = []
            for i, alias in enumerate(kept):
                if i == len(kept) - 1:
                    cleaned.append(alias.with_changes(comma=cst.MaybeSentinel.DEFAULT))
                else:
                    cleaned.append(alias)
            result_stmts.append(
                updated_node.with_changes(body=[orig_stmt.with_changes(names=cleaned)])
            )

        # Add new import statements for migrated names
        for new_module in sorted(migrated.keys()):
            aliases = migrated[new_module]
            # Clean trailing comma
            cleaned = []
            for i, alias in enumerate(aliases):
                if i == len(aliases) - 1:
                    cleaned.append(alias.with_changes(comma=cst.MaybeSentinel.DEFAULT))
                else:
                    cleaned.append(alias)

            new_import = cst.ImportFrom(
                module=self._build_module(new_module),
                names=cleaned,
            )
            result_stmts.append(
                cst.SimpleStatementLine(
                    body=[new_import],
                    leading_lines=updated_node.leading_lines
                    if not result_stmts
                    else [],
                )
            )

        if not result_stmts:
            return cst.RemovalSentinel.REMOVE

        if len(result_stmts) == 1:
            return result_stmts[0]

        return cst.FlattenSentinel(result_stmts)

    def leave_Name(
        self,
        original_node: cst.Name,
        updated_node: cst.Name,
    ) -> cst.Name:
        """Rename usage sites (function calls, type references, etc.)."""
        new = self._renames.get(updated_node.value)
        if new is not None:
            return updated_node.with_changes(value=new)
        return updated_node

    # -- helpers --

    @staticmethod
    def _dotted(node: cst.BaseExpression | None) -> str | None:
        if isinstance(node, cst.Attribute):
            parent = PloneImportMigrator._dotted(node.value)
            if parent is None:
                return None
            return f"{parent}.{node.attr.value}"
        if isinstance(node, cst.Name):
            return node.value
        return None

    @staticmethod
    def _build_module(dotted: str) -> cst.Attribute | cst.Name:
        parts = dotted.split(".")
        node: cst.Attribute | cst.Name = cst.Name(parts[0])
        for part in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(part))
        return node


def transform_code(source: str, config_path: Path = CONFIG_PATH) -> str:
    """Transform a source code string. Convenience for programmatic use."""
    context = CodemodContext()
    tree = cst.parse_module(source)
    transformer = PloneImportMigrator(context)
    new_tree = tree.visit(transformer)
    return new_tree.code
