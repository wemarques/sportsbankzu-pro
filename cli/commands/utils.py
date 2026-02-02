"""Utility commands: hash-password, adjust-thresholds, test."""

import hashlib
import subprocess
import sys

import click


@click.group()
def utils():
    """Utility tools: password hashing, threshold tuning, tests."""


@utils.command("hash-password")
@click.argument("password", required=False)
def hash_password(password):
    """Generate a SHA-256 password hash for config.yaml.

    Pass a password as argument, or omit to be prompted securely.

    Example: sportsbank utils hash-password mypassword
    """
    if not password:
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)

    hashed = hashlib.sha256(password.encode()).hexdigest()
    click.echo()
    click.echo(f"SHA-256: {hashed}")
    click.echo()
    click.echo("Add to config.yaml:")
    click.echo(f'  password: "{hashed}"')


@utils.command("adjust-thresholds")
@click.option("--dry-run", is_flag=True, help="Show thresholds without applying changes")
def adjust_thresholds(dry_run):
    """Run threshold adjustment for prediction markets.

    Example: sportsbank utils adjust-thresholds --dry-run
    """
    default_thresholds = {
        "home_win": {"SAFE": 0.60, "NEUTRO": 0.45},
        "over25": {"SAFE": 0.65, "NEUTRO": 0.50},
        "btts": {"SAFE": 0.55, "NEUTRO": 0.40},
        "under35": {"SAFE": 0.70, "NEUTRO": 0.60},
        "under45": {"SAFE": 0.75, "NEUTRO": 0.65},
    }

    if dry_run:
        click.echo("Current default thresholds:")
        click.echo()
        click.echo(f"  {'Market':<15} {'SAFE':>8} {'NEUTRO':>8}")
        click.echo("  " + "-" * 31)
        for market, levels in default_thresholds.items():
            click.echo(f"  {market:<15} {levels['SAFE']:>8.2f} {levels['NEUTRO']:>8.2f}")
        return

    click.echo("Adjusting thresholds...")
    try:
        from backend.audit import adjust_thresholds as do_adjust
        do_adjust(default_thresholds)
        click.secho("Thresholds adjusted.", fg="green")
    except ImportError:
        click.secho("backend.audit module not available.", fg="red")
    except Exception as e:
        click.secho(f"Failed: {e}", fg="red")


@utils.command("test")
@click.option("--coverage", is_flag=True, help="Run with coverage report")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.argument("path", required=False)
def test(coverage, verbose, path):
    """Run the test suite with pytest.

    Optionally pass a specific test path.

    Example: sportsbank utils test --coverage -v tests/
    """
    cmd = [sys.executable, "-m", "pytest"]
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    if coverage:
        cmd.extend(["--cov=backend", "--cov-report=term-missing"])
    if path:
        cmd.append(path)

    click.echo(f"Running: {' '.join(cmd)}")
    click.echo()
    result = subprocess.run(cmd)
    raise SystemExit(result.returncode)


@utils.command("migrate-db")
@click.option("--source", type=click.Choice(["sqlite", "postgres"]), default="sqlite", help="Source database type")
@click.option("--target", type=click.Choice(["postgres"]), default="postgres", help="Target database type")
def migrate_db(source, target):
    """Run database migration (SQLite to PostgreSQL).

    Example: sportsbank utils migrate-db --source sqlite --target postgres
    """
    click.echo(f"Migrating from {source} to {target}...")
    try:
        subprocess.run(
            [sys.executable, "migrate_sqlite_to_postgres.py"],
            check=True,
        )
        click.secho("Migration complete.", fg="green")
    except subprocess.CalledProcessError as e:
        click.secho(f"Migration failed (exit code {e.returncode}).", fg="red")
    except FileNotFoundError:
        click.secho("Migration script not found.", fg="red")


@utils.command("check-db")
def check_db():
    """Test PostgreSQL database connectivity.

    Example: sportsbank utils check-db
    """
    click.echo("Testing database connection...")
    try:
        subprocess.run(
            [sys.executable, "test_postgres_connection.py"],
            check=True,
        )
        click.secho("Connection OK.", fg="green")
    except subprocess.CalledProcessError as e:
        click.secho(f"Connection test failed (exit code {e.returncode}).", fg="red")
    except FileNotFoundError:
        click.secho("Connection test script not found.", fg="red")
