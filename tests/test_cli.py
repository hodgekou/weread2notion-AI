from argparse import Namespace

from weread2notion.cli import build_parser


def test_dry_run_flag_is_available_without_notion_command_changes():
    args = build_parser().parse_args(["sync", "--dry-run"])
    assert isinstance(args, Namespace)
    assert args.command == "sync"
    assert args.dry_run is True
