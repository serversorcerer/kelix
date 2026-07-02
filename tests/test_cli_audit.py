"""V-SIMPLE CLI audit against value ledger (REQ-VM1, KV11)."""

from __future__ import annotations

import io
import subprocess
import sys

import pytest

from kelix.cli import main

SCRAPPED_SUBCOMMANDS = ("sync",)
HAPPY_PATH_SUBCOMMANDS = ("init", "plan", "run")
SECONDARY_SUBCOMMANDS = ("lint", "status", "stop")


def _capture_help() -> str:
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        with pytest.raises(SystemExit):
            main(["--help"])
    finally:
        sys.stdout = old_stdout
    return buf.getvalue()


def test_kelix_help_lists_happy_path_and_omits_scrapped():
    help_text = _capture_help()

    for name in HAPPY_PATH_SUBCOMMANDS:
        assert name in help_text, f"happy-path subcommand {name!r} missing from --help"

    for name in SCRAPPED_SUBCOMMANDS:
        assert name not in help_text, f"scrapped subcommand {name!r} still in --help"


def test_secondary_subcommands_marked_in_help():
    help_text = _capture_help()

    for name in SECONDARY_SUBCOMMANDS:
        assert name in help_text
        assert "(secondary)" in help_text


def test_kelix_help_subcommand_order_puts_happy_path_first():
    help_text = _capture_help()

    pos = {name: help_text.index(name) for name in HAPPY_PATH_SUBCOMMANDS}
    assert pos["init"] < pos["plan"] < pos["run"]


def test_cli_has_no_sync_references():
    result = subprocess.run(
        ["rg", "-i", "kelix sync|cmd_sync|add_parser\\(\"sync", "src/kelix/cli.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert result.stdout.strip() == ""
