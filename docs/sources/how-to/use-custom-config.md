# Use a Custom Configuration File

<!-- diataxis: how-to -->

The `--config` flag lets you supply your own `migration_config.yaml` instead of the bundled one.

## Replace the bundled config

```bash
plone-codemod ./src/ --config my_config.yaml
```

This replaces all built-in rules with only the rules in your file. Useful when you need a completely different migration mapping (e.g., for a non-standard Plone setup or a different version range).

## Create a project-specific config

1. Copy the bundled config as a starting point:

   ```bash
   cp $(python -c "import plone_codemod; print(plone_codemod.__file__.replace('__init__.py', 'migration_config.yaml'))") my_config.yaml
   ```

2. Edit `my_config.yaml` -- add, remove, or modify rules as needed.

3. Run with your config:

   ```bash
   plone-codemod ./src/ --config my_config.yaml
   ```

## Config file format

See {doc}`../reference/config-format` for the complete YAML schema.
