"""
Setup do EventBridge rule para snapshot diario de standings (#173).

Cria uma rule que dispara a Lambda sportsbank-pro-backend
todos os dias as 06:00 UTC (03:00 BRT) com o payload de snapshot_standings.

Por que 06:00 UTC: depois do batch_audit (23:00 UTC) e late_audit (05:00 UTC),
fora do horario de pico de jogos.

Uso:
    python scripts/setup_standings_snapshot.py           # Cria a rule
    python scripts/setup_standings_snapshot.py --disable # Desabilita
    python scripts/setup_standings_snapshot.py --delete  # Remove
    python scripts/setup_standings_snapshot.py --status  # Verifica
    python scripts/setup_standings_snapshot.py --invoke  # Dispara manualmente
"""

import json
import subprocess
import sys

RULE_NAME = "sportsbank-standings-snapshot"
LAMBDA_FUNCTION = "sportsbank-pro-backend"
REGION = "us-east-1"
# 06:00 UTC = 03:00 BRT — fora do horario de jogos
SCHEDULE = "cron(0 6 * * ? *)"

EVENT_INPUT = json.dumps({
    "source": "eventbridge",
    "action": "snapshot_standings",
})


def run_aws(args: list, capture: bool = True) -> str:
    cmd = ["aws"] + args + ["--region", REGION]
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if result.returncode != 0:
        print(f"Erro: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip() if capture else ""


def get_lambda_arn() -> str:
    return run_aws([
        "lambda", "get-function",
        "--function-name", LAMBDA_FUNCTION,
        "--query", "Configuration.FunctionArn",
        "--output", "text",
    ])


def create_rule():
    print(f"Criando rule '{RULE_NAME}' com schedule: {SCHEDULE}")
    run_aws([
        "events", "put-rule",
        "--name", RULE_NAME,
        "--schedule-expression", SCHEDULE,
        "--state", "ENABLED",
        "--description", "SportsBankZU Pro - Snapshot diario de standings (#173)",
    ], capture=False)

    lambda_arn = get_lambda_arn()
    account_id = lambda_arn.split(":")[4]

    print("Adicionando permissao para EventBridge invocar Lambda...")
    try:
        run_aws([
            "lambda", "add-permission",
            "--function-name", LAMBDA_FUNCTION,
            "--statement-id", f"{RULE_NAME}-permission",
            "--action", "lambda:InvokeFunction",
            "--principal", "events.amazonaws.com",
            "--source-arn", f"arn:aws:events:{REGION}:{account_id}:rule/{RULE_NAME}",
        ])
    except SystemExit:
        print("(Permissao ja existe, continuando...)")

    targets = json.dumps([{
        "Id": "sportsbank-standings-target",
        "Arn": lambda_arn,
        "Input": EVENT_INPUT,
    }])

    print("Configurando target...")
    run_aws([
        "events", "put-targets",
        "--rule", RULE_NAME,
        "--targets", targets,
    ], capture=False)

    print(f"\nRule '{RULE_NAME}' criada com sucesso!")
    print(f"  Schedule: {SCHEDULE} (06:00 UTC / 03:00 BRT)")
    print(f"  Target: {LAMBDA_FUNCTION}")
    print(f"  Payload: {EVENT_INPUT}")
    print()
    print("Verificar S3_BUCKET na config do Lambda:")
    print(f"  aws lambda get-function-configuration --function-name {LAMBDA_FUNCTION} "
          "--query 'Environment.Variables.S3_BUCKET' --region us-east-1")


def disable_rule():
    print(f"Desabilitando rule '{RULE_NAME}'...")
    run_aws(["events", "disable-rule", "--name", RULE_NAME], capture=False)


def delete_rule():
    print(f"Removendo targets de '{RULE_NAME}'...")
    try:
        run_aws([
            "events", "remove-targets",
            "--rule", RULE_NAME,
            "--ids", "sportsbank-standings-target",
        ], capture=False)
    except SystemExit:
        pass

    print(f"Deletando rule '{RULE_NAME}'...")
    run_aws(["events", "delete-rule", "--name", RULE_NAME], capture=False)

    try:
        run_aws([
            "lambda", "remove-permission",
            "--function-name", LAMBDA_FUNCTION,
            "--statement-id", f"{RULE_NAME}-permission",
        ])
    except SystemExit:
        pass


def check_status():
    print(f"Verificando rule '{RULE_NAME}'...")
    try:
        out = run_aws([
            "events", "describe-rule",
            "--name", RULE_NAME,
        ])
        rule = json.loads(out)
        print(f"  Nome: {rule.get('Name')}")
        print(f"  Estado: {rule.get('State')}")
        print(f"  Schedule: {rule.get('ScheduleExpression')}")
        print(f"  Descricao: {rule.get('Description', '')}")

        out2 = run_aws([
            "events", "list-targets-by-rule",
            "--rule", RULE_NAME,
        ])
        targets = json.loads(out2)
        for t in targets.get("Targets", []):
            print(f"  Target: {t.get('Arn')}")
            print(f"  Input: {t.get('Input', 'default')}")
    except SystemExit:
        print(f"Rule '{RULE_NAME}' nao encontrada.")


def invoke_now():
    """Dispara a Lambda manualmente para testar o snapshot."""
    print(f"Invocando {LAMBDA_FUNCTION} manualmente com snapshot_standings...")
    out_file = "snapshot_response.json"
    run_aws([
        "lambda", "invoke",
        "--function-name", LAMBDA_FUNCTION,
        "--payload", EVENT_INPUT,
        "--cli-binary-format", "raw-in-base64-out",
        out_file,
    ], capture=False)
    print(f"Resposta salva em {out_file}")
    try:
        with open(out_file, "r") as f:
            print(f.read())
    except Exception:
        pass


if __name__ == "__main__":
    if "--disable" in sys.argv:
        disable_rule()
    elif "--delete" in sys.argv:
        delete_rule()
    elif "--status" in sys.argv:
        check_status()
    elif "--invoke" in sys.argv:
        invoke_now()
    else:
        create_rule()
