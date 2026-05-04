"""CLI entrypoint."""

from __future__ import annotations

import sys
from typing import Any

import click

from peer_atlas_cli.commands.add_program import add_program_cmd
from peer_atlas_cli.commands.clear_programs import clear_programs_cmd
from peer_atlas_cli.commands.merge_patch import merge_patch_cmd
from peer_atlas_cli.commands.reconsider_node import reconsider_node_cmd
from peer_atlas_cli.commands.test_evidence_url import test_evidence_url_cmd
from peer_atlas_cli.commands.remove_last_program import remove_last_program_cmd
from peer_atlas_cli.commands.refresh_sources import refresh_sources_cmd
from peer_atlas_cli.commands.validate import validate_cmd
from peer_atlas_cli.config import load_env
from peer_atlas_cli.llm_transcript import begin_cli_llm_session
from peer_atlas_cli.repo_root import find_repo_root


class PeerAtlasGroup(click.Group):
    """Clears ``.peer-atlas/llm-last-session/`` and loads env before each subcommand."""

    def invoke(self, ctx: click.Context) -> Any:
        try:
            root = find_repo_root()
        except FileNotFoundError:
            return super().invoke(ctx)
        load_env(root)
        begin_cli_llm_session(root, argv=sys.argv)
        return super().invoke(ctx)


@click.group(cls=PeerAtlasGroup)
@click.version_option()
def main() -> None:
    """MDes Peer Program Atlas — corpus tools."""


main.add_command(validate_cmd, "validate")
main.add_command(refresh_sources_cmd, "refresh-sources")
main.add_command(clear_programs_cmd, "clear-programs")
main.add_command(merge_patch_cmd, "merge-patch")
main.add_command(remove_last_program_cmd, "remove-last-program")
main.add_command(add_program_cmd, "add-program")
main.add_command(reconsider_node_cmd, "reconsider-node")
main.add_command(test_evidence_url_cmd, "test-evidence-url")


if __name__ == "__main__":
    main()
