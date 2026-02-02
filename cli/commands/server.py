"""Server and deployment commands: serve, deploy, validate."""

import subprocess
import sys
import time

import click


@click.group()
def server():
    """Start servers, deploy, and validate deployments."""


@server.command()
@click.option("--host", "-h", default="0.0.0.0", help="Host to bind to")
@click.option("--port", "-p", default=5001, type=int, help="Port number")
@click.option("--reload", "do_reload", is_flag=True, help="Enable auto-reload for development")
@click.option("--workers", "-w", default=1, type=int, help="Number of worker processes")
def api(host, port, do_reload, workers):
    """Start the FastAPI backend server.

    Example: sportsbank server api --port 8000 --reload
    """
    cmd = [
        sys.executable, "-m", "uvicorn",
        "backend.main:app",
        "--host", host,
        "--port", str(port),
        "--workers", str(workers),
    ]
    if do_reload:
        cmd.append("--reload")

    click.echo(f"Starting API server on {host}:{port}")
    if do_reload:
        click.echo("Auto-reload enabled")
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        click.echo("\nServer stopped.")
    except FileNotFoundError:
        click.secho("uvicorn not found. Install it: pip install uvicorn", fg="red")


@server.command()
@click.option("--port", "-p", default=8501, type=int, help="Port number")
def streamlit(port):
    """Start the Streamlit frontend.

    Example: sportsbank server streamlit --port 8501
    """
    cmd = [
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", str(port),
    ]
    click.echo(f"Starting Streamlit on port {port}")
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        click.echo("\nStreamlit stopped.")
    except FileNotFoundError:
        click.secho("streamlit not found. Install it: pip install streamlit", fg="red")


@server.command()
@click.option("--port-api", default=5001, type=int, help="API server port")
@click.option("--port-ui", default=8501, type=int, help="Streamlit port")
def dev(port_api, port_ui):
    """Start both API and Streamlit in development mode.

    Example: sportsbank server dev
    """
    import threading

    click.echo(f"Starting dev environment: API on :{port_api}, Streamlit on :{port_ui}")

    def run_api():
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--host", "0.0.0.0",
            "--port", str(port_api),
            "--reload",
        ])

    def run_streamlit():
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", str(port_ui),
        ])

    api_thread = threading.Thread(target=run_api, daemon=True)
    ui_thread = threading.Thread(target=run_streamlit, daemon=True)

    api_thread.start()
    ui_thread.start()

    try:
        while api_thread.is_alive() or ui_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\nStopping dev environment.")


@server.command()
def deploy():
    """Deploy backend to AWS Lambda via S3.

    Builds the Lambda package, uploads to S3, and updates the function.
    """
    click.echo("Starting Lambda deployment...")
    try:
        subprocess.run(
            [sys.executable, "scripts/deploy_lambda.py"],
            check=True,
        )
        click.secho("Deployment complete.", fg="green")
    except subprocess.CalledProcessError as e:
        click.secho(f"Deployment failed (exit code {e.returncode}).", fg="red")
    except FileNotFoundError:
        click.secho("Deploy script not found at scripts/deploy_lambda.py", fg="red")


@server.command()
@click.option("--backend-url", "-b", prompt="Backend URL", help="Backend base URL")
@click.option("--timeout", "-t", default=5, type=int, help="Request timeout in seconds")
def validate(backend_url, timeout):
    """Validate a deployed backend by testing key endpoints.

    Example: sportsbank server validate --backend-url https://api.example.com
    """
    try:
        import requests
    except ImportError:
        click.secho("requests library required. Install it: pip install requests", fg="red")
        return

    endpoints = [
        ("/health", "Health Check"),
        ("/discover", "Discover Leagues"),
        ("/leagues/", "List Leagues"),
    ]

    backend_url = backend_url.rstrip("/")
    click.echo(f"Validating: {backend_url}")
    click.echo()

    passed = 0
    failed = 0
    for path, name in endpoints:
        url = f"{backend_url}{path}"
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                click.secho(f"  PASS  {name} ({path})", fg="green")
                passed += 1
            else:
                click.secho(f"  FAIL  {name} ({path}) -> HTTP {resp.status_code}", fg="red")
                failed += 1
        except requests.exceptions.Timeout:
            click.secho(f"  FAIL  {name} ({path}) -> Timeout", fg="red")
            failed += 1
        except requests.exceptions.ConnectionError:
            click.secho(f"  FAIL  {name} ({path}) -> Connection refused", fg="red")
            failed += 1
        except Exception as e:
            click.secho(f"  FAIL  {name} ({path}) -> {e}", fg="red")
            failed += 1

    click.echo()
    if failed == 0:
        click.secho(f"All {passed} endpoints OK.", fg="green")
    else:
        click.secho(f"{passed} passed, {failed} failed.", fg="red")
