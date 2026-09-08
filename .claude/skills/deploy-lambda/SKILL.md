---
name: deploy-lambda
description: Deploy do backend na Lambda sportsbank-pro-backend (pre-check obrigatorio, update via S3) e recriacao da Layer scipy quando o runtime Python muda. Use ao publicar backend ou ao ver NB2 caindo para Poisson.
---

# Deploy Lambda e Layer scipy

Movido do CLAUDE.md (era sempre carregado; /doctor 2026-09-08). Conteudo integral.

## Deploy Lambda

```bash
# Pré-check OBRIGATÓRIO antes de update-function-code
MSYS_NO_PATHCONV=1 aws lambda get-function-configuration \
  --function-name sportsbank-pro-backend --region us-east-1 \
  --query '{State: State, LastUpdateStatus: LastUpdateStatus}'
# Só prosseguir se State=Active e LastUpdateStatus=Successful

MSYS_NO_PATHCONV=1 aws lambda update-function-code \
  --function-name sportsbank-pro-backend \
  --s3-bucket meu-bucket-sportsbank \
  --s3-key deploy/sportsbank_lambda.zip --region us-east-1
```

## Lambda Layer (scipy) — `arn:aws:lambda:us-east-1:838823110426:layer:scipy-numpy-layer:2`

- Layer contém **apenas scipy** (numpy está no ZIP de deploy). Usada por NB2 (cards e corners).
- Sem Layer compatível, **NB2 cai silenciosamente para Poisson** (sem erro visível).
- Mudança de runtime Python (ex.: 3.11 → 3.12) **exige recriar a Layer** — extensões C não são portáveis entre versões.

```bash
pip install scipy -t layer/python/ --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.XX --no-deps
cd layer && zip -r ../scipy-layer.zip python/ -x '*.pyc' '*__pycache__*' '*.dist-info/*' '*/tests/*'
aws lambda publish-layer-version --layer-name scipy-numpy-layer \
  --content S3Bucket=meu-bucket-sportsbank,S3Key=deploy/scipy-layer.zip \
  --compatible-runtimes python3.XX --region us-east-1
aws lambda update-function-configuration --function-name sportsbank-pro-backend \
  --layers <LAYER_ARN> --region us-east-1
```
