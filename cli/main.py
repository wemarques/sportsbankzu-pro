"""SportsBankZU Pro CLI entry point."""

import logging

import click

from cli import __version__
from cli.commands.data import data
from cli.commands.analysis import analysis
from cli.commands.server import server
from cli.commands.utils import utils


@click.group()
@click.version_option(version=__version__, prog_name="sportsbank")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose/debug logging")
def cli(verbose):
    """SportsBankZU Pro - Professional sports prediction system.

    Use the subcommands below to manage data, run analysis,
    start servers, and perform utility tasks.
    """
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", force=True)


cli.add_command(data)
cli.add_command(analysis)
cli.add_command(server)
cli.add_command(utils)


if __name__ == "__main__":
    cli()
