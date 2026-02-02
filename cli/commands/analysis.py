"""Analysis commands: quadro-resumo, predict, audit."""

import json
import sys

import click


@click.group()
def analysis():
    """Run predictions and generate match analysis."""


@analysis.command("quadro")
@click.argument("league")
@click.option("--date", "-d", default="today", help="Date filter: today, tomorrow, week")
@click.option("--format", "formato", type=click.Choice(["detalhado", "whatsapp"]), default="detalhado", help="Output format")
@click.option("--no-simples", is_flag=True, help="Exclude individual match analysis")
@click.option("--no-duplas", is_flag=True, help="Exclude double bets")
@click.option("--triplas", is_flag=True, help="Include triple bets")
@click.option("--no-governanca", is_flag=True, help="Exclude governance section")
def quadro(league, date, formato, no_simples, no_duplas, triplas, no_governanca):
    """Generate the professional summary board (Quadro-Resumo) for a league.

    Example: sportsbank analysis quadro premier-league
    """
    from backend.services.quadro_service import build_quadro_response

    result = build_quadro_response(
        league=league,
        date=date,
        incluir_simples=not no_simples,
        incluir_duplas=not no_duplas,
        incluir_triplas=triplas,
        incluir_governanca=not no_governanca,
        formato=formato,
    )

    click.echo(result.get("quadro_texto", ""))
    click.echo()
    click.echo(
        f"Matches: {result.get('jogos_count', 0)} | "
        f"Doubles: {result.get('duplas_count', 0)} | "
        f"Triples: {result.get('triplas_count', 0)} | "
        f"Regime: {result.get('regime', 'N/A')} | "
        f"Volatility: {result.get('volatilidade', 'N/A')}"
    )


@analysis.command("predict")
@click.argument("league")
@click.option("--date", "-d", default="today", help="Date filter: today, tomorrow, week")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table", help="Output format")
def predict(league, date, fmt):
    """Show predictions with market suggestions for each match.

    Example: sportsbank analysis predict premier-league --date tomorrow
    """
    from backend.main import (
        load_fixtures_from_csv,
        generate_mock_fixtures,
        calcular_regime_e_volatilidade,
        selecionar_mercados_jogo,
    )

    jogos = load_fixtures_from_csv(league, date)
    if not jogos:
        jogos = generate_mock_fixtures(league, date)

    if not jogos:
        click.secho("No matches found.", fg="yellow")
        return

    regime, volatilidade = calcular_regime_e_volatilidade(league, jogos)
    click.echo(f"League Regime: {regime} | Volatility: {volatilidade}")
    click.echo()

    results = []
    for jogo in jogos:
        mercados = selecionar_mercados_jogo(jogo, regime, volatilidade)
        entry = {
            "home": jogo.get("homeTeam"),
            "away": jogo.get("awayTeam"),
            "datetime": jogo.get("datetime", "")[:16],
            "lambda_home": jogo.get("stats", {}).get("lambdaHome"),
            "lambda_away": jogo.get("stats", {}).get("lambdaAway"),
            "markets": mercados,
        }
        results.append(entry)

    if fmt == "json":
        click.echo(json.dumps(results, indent=2, default=str))
        return

    for entry in results:
        dt_str = entry["datetime"].replace("T", " ")
        click.echo(f"{entry['home']} vs {entry['away']}  ({dt_str})")
        lh = entry.get("lambda_home")
        la = entry.get("lambda_away")
        if lh is not None and la is not None:
            click.echo(f"  Lambda: Home={lh:.3f}  Away={la:.3f}  Total={lh + la:.3f}")
        for m in entry.get("markets", []):
            status_color = "green" if m.get("status") == "SAFE" else "yellow" if "SAFE" in str(m.get("status", "")) else "white"
            odd = m.get("odd_minima")
            odd_str = f" @{odd}" if odd else ""
            click.secho(
                f"  -> {m.get('mercado', ''):<20} [{m.get('status', '')}]  "
                f"prob {m.get('prob_min', 0)}-{m.get('prob_max', 0)}%{odd_str}",
                fg=status_color,
            )
            if m.get("alerta"):
                click.secho(f"     ! {m['alerta']}", fg="yellow")
        click.echo()

    click.echo(f"Total: {len(results)} matches analyzed")


@analysis.command("audit")
@click.argument("league")
@click.option("--date", "-d", default="today", help="Date filter")
@click.option("--match-index", "-m", type=int, default=0, help="Index of match to audit (0-based)")
def audit(league, date, match_index):
    """Run AI audit on a specific match using Mistral.

    Example: sportsbank analysis audit premier-league --match-index 0
    """
    from backend.main import load_fixtures_from_csv, generate_mock_fixtures
    from backend.ai.mistral_auditor import MistralAuditor

    jogos = load_fixtures_from_csv(league, date)
    if not jogos:
        jogos = generate_mock_fixtures(league, date)

    if not jogos:
        click.secho("No matches found.", fg="yellow")
        return

    if match_index >= len(jogos):
        click.secho(f"Match index {match_index} out of range (0-{len(jogos) - 1}).", fg="red")
        return

    jogo = jogos[match_index]
    click.echo(f"Auditing: {jogo.get('homeTeam')} vs {jogo.get('awayTeam')}")
    click.echo()

    try:
        auditor = MistralAuditor()
        result = auditor.audit_match_calculation(jogo)
        if isinstance(result, dict):
            click.echo(json.dumps(result, indent=2, default=str))
        else:
            click.echo(str(result))
    except Exception as e:
        click.secho(f"Audit failed: {e}", fg="red")
        click.echo("Make sure MISTRAL_API_KEY is set in your environment.")
