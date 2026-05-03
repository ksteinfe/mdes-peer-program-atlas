"""CLI entrypoint."""

from __future__ import annotations

import click

from peer_atlas_cli.commands.add_program import add_program_cmd
from peer_atlas_cli.commands.clear_programs import clear_programs_cmd
from peer_atlas_cli.commands.merge_patch import merge_patch_cmd
from peer_atlas_cli.commands.reconsider_node import reconsider_node_cmd
from peer_atlas_cli.commands.validate import validate_cmd
from peer_atlas_cli.config import load_env
from peer_atlas_cli.repo_root import find_repo_root


@click.group()
@click.version_option()
def main() -> None:
    """MDes Peer Program Atlas — corpus tools."""
    try:
        root = find_repo_root()
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e
    load_env(root)


main.add_command(validate_cmd, "validate")
main.add_command(clear_programs_cmd, "clear-programs")
main.add_command(merge_patch_cmd, "merge-patch")
main.add_command(add_program_cmd, "add-program")
main.add_command(reconsider_node_cmd, "reconsider-node")


if __name__ == "__main__":
    main()
