"""Tests for the CLI orchestrator, focusing on the libcst subprocess invocation."""

import subprocess
import sys


class TestPhase1SubprocessInvocation:
    """Verify that Phase 1 runs the libcst codemod successfully via subprocess.

    The key issue this tests: libcst's ``codemod`` command needs ``-x`` to
    treat the command as a direct module import rather than searching the
    ``.libcst.codemod.yaml`` modules list.  Without ``-x``, users get:

        Could not find plone_codemod.import_migrator in any configured modules
    """

    def test_phase1_transforms_import(self, tmp_path):
        """End-to-end: Phase 1 rewrites imports in a fresh directory."""
        src = tmp_path / "src"
        src.mkdir()
        test_file = src / "example.py"
        test_file.write_text(
            "from Products.CMFPlone.utils import safe_unicode\n"
            "\n"
            "text = safe_unicode(value)\n"
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "plone_codemod.cli",
                str(src),
                "--skip-zcml",
                "--skip-xml",
                "--skip-pt",
                "--skip-audit",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        content = test_file.read_text()
        assert "from plone.base.utils import safe_text" in content
        assert "safe_text(value)" in content
        assert "safe_unicode" not in content

    def test_phase1_no_libcst_config_file_created(self, tmp_path):
        """The -x flag means no .libcst.codemod.yaml is needed in source dir."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "example.py").write_text(
            "from Products.CMFPlone.utils import base_hasattr\n"
        )

        subprocess.run(
            [
                sys.executable,
                "-m",
                "plone_codemod.cli",
                str(src),
                "--skip-zcml",
                "--skip-xml",
                "--skip-pt",
                "--skip-audit",
            ],
            capture_output=True,
            text=True,
        )

        assert not (src / ".libcst.codemod.yaml").exists()

    def test_phase1_dry_run_does_not_modify(self, tmp_path):
        """Dry run should not modify any files."""
        src = tmp_path / "src"
        src.mkdir()
        test_file = src / "example.py"
        original = "from Products.CMFPlone.utils import safe_unicode\n"
        test_file.write_text(original)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "plone_codemod.cli",
                str(src),
                "--dry-run",
                "--skip-zcml",
                "--skip-xml",
                "--skip-pt",
                "--skip-audit",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert test_file.read_text() == original
