"""
#160: Setup do EventBridge rule para late_audit (jogos das Americas).

Cria uma rule que dispara a Lambda sportsbank-pro-backend
todos os dias as 05:00 UTC (02:00 BRT) com o payload de late_audit.

Pega jogos da Liga MX, MLS, Copa Libertadores etc. que terminam
depois das 23:45 BRT (cutoff do today_audit).

Uso:
    python scripts/setup_late_audit.py           # Cria a rule
    python scripts/setup_late_audit.py --disable  # Desabilita a rule
    python scripts/setup_late_audit.py --delete   # Remove a rule
    python scripts/setup_late_audit.py --status   # Verifica status
"""

import subprocess
import json
import sys

RULE_NAME = "sportsbank-late-audit"
LAMBDA_FUNCTION = "sportsbank-pro-backend"
REGION = "us-east-1"
# 05:00 UTC = 02:00 BRT — Americas late matches already finished
SCHEDULE = "cron(0 5 * * ? *)"

EVENT_INPUT = json.dumps({
    "source": "eventbridge",
    "action": "late_audit",
})


def run_aws(args: list, capture=True) -> str:
    """Run an AWS CLI command and return output."""
    cmd = ["aws"] + args + ["--region", REGION]
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if result.returncode != 0:
        print(f"Erro: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip() if capture else ""


def get_lambda_arn() -> str:
    """Fetch the Lambda function ARN."""
    out = run_aws([
        "lambda", "get-function",
        "--function-name", LAMBDA_FUNCTION,
        "--query", "Configuration.FunctionArn",
        "--output", "text",
    ])
    return out


def create_rule():
    """Create the EventBridge rule with a cron schedule."""
    print(f"Criando rule '{RULE_NAME}' com schedule: {SCHEDULE}")
    run_aws([
        "events", "put-rule",
        "--name", RULE_NAME,
        "--schedule-expression", SCHEDULE,
        "--state", "ENABLED",
        "--description", "SportsBankZU Pro - Late audit Americas (02h BRT) #160",
    ], capture=False)

    lambda_arn = get_lambda_arn()
    print(f"Lambda ARN: {lambda_arn}")

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
        "Id": "sportsbank-late-audit-target",
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
    print(f"  Schedule: {SCHEDULE} (05:00 UTC / 02:00 BRT)")
    print(f"  Target: {LAMBDA_FUNCTION}")
    print(f"  Payload: {EVENT_INPUT}")


def disable_rule():
    """Disable the EventBridge rule."""
    print(f"Desabilitando rule '{RULE_NAME}'...")
    run_aws(["events", "disable-rule", "--name", RULE_NAME], capture=False)
    print("Rule desabilitada.")


def delete_rule():
    """Remove targets and delete the EventBridge rule."""
    print(f"Removendo targets da rule '{RULE_NAME}'...")
    try:
        run_aws([
            "events", "remove-targets",
            "--rule", RULE_NAME,
            "--ids", "sportsbank-late-audit-target",
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

    print("Rule deletada com sucesso.")


def check_status():
    """Check if the rule exists and its status."""
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


if __name__ == "__main__":
    if "--disable" in sys.argv:
        disable_rule()
    elif "--delete" in sys.argv:
        delete_rule()
    elif "--status" in sys.argv:
        check_status()
    else:
        create_rule()
