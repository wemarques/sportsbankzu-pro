"""Data management commands: discover, leagues, fixtures."""

import json
import os
import sys

import click


@click.group()
def data():
    """Manage data sources: discover directories, list leagues, fetch fixtures."""


@data.command()
def discover():
    """Discover available data directories and files."""
    from backend.main import get_base_root, get_data_dir

    base_root = get_base_root()
    data_dir = get_data_dir()

    click.echo(f"Root:     {base_root}")
    click.echo(f"Data dir: {data_dir}")
    click.echo(f"Root exists: {os.path.isdir(base_root)}")
    click.echo()

    if not os.path.isdir(data_dir):
        click.secho("Data directory not found.", fg="yellow")
        return

    leagues_found = 0
    for name in sorted(os.listdir(data_dir)):
        league_dir = os.path.join(data_dir, name)
        if not os.path.isdir(league_dir):
            continue
        leagues_found += 1
        csvs = [
            f
            for f in ("matches.csv", "teams.csv", "teams2.csv", "league.csv", "players.csv")
            if os.path.exists(os.path.join(league_dir, f))
        ]
        click.echo(f"  {name}/")
        if csvs:
            click.echo(f"    files: {', '.join(csvs)}")
        else:
            click.secho("    (no CSV files)", fg="yellow")

    click.echo()
    click.echo(f"Total league directories: {leagues_found}")


@data.command("leagues")
def list_leagues():
    """List all configured leagues (22 supported leagues)."""
    from backend.config.leagues_config import LEAGUES_CONFIG

    click.echo(f"{'ID':<30} {'Country':<15} {'Name':<25}")
    click.echo("-" * 70)
    for league in LEAGUES_CONFIG:
        click.echo(f"{league['id']:<30} {league['country']:<15} {league['name']:<25}")
    click.echo()
    click.echo(f"Total: {len(LEAGUES_CONFIG)} leagues")


@data.command()
@click.argument("league_ids", nargs=-1, required=True)
@click.option("--date", "-d", default="today", help="Date filter: today, tomorrow, week")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table", help="Output format")
def fixtures(league_ids, date, fmt):
    """Fetch fixtures for one or more leagues.

    Pass league IDs as arguments, e.g.: sportsbank data fixtures premier-league la-liga
    """
    from backend.main import load_fixtures_from_csv, generate_mock_fixtures

    all_fixtures = []
    for lid in league_ids:
        records = load_fixtures_from_csv(lid, date)
        if not records:
            records = generate_mock_fixtures(lid, date)
        all_fixtures.extend(records)

    if not all_fixtures:
        click.secho("No fixtures found.", fg="yellow")
        return

    if fmt == "json":
        click.echo(json.dumps(all_fixtures, indent=2, default=str))
        return

    # Table format
    click.echo(f"{'League':<22} {'Home':<25} {'Away':<25} {'Date':<18} {'Status':<10}")
    click.echo("-" * 100)
    for f in all_fixtures:
        dt_str = f.get("datetime", "")[:16].replace("T", " ")
        click.echo(
            f"{f.get('leagueName', ''):<22} "
            f"{f.get('homeTeam', ''):<25} "
            f"{f.get('awayTeam', ''):<25} "
            f"{dt_str:<18} "
            f"{f.get('status', ''):<10}"
        )
    click.echo()
    click.echo(f"Total: {len(all_fixtures)} fixtures")
