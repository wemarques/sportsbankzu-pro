import os
import zipfile
import subprocess
import shutil
from pathlib import Path

# Configurações
FUNCTION_NAME = "sportsbank-pro-backend"
REGION = "us-east-1" # Ajuste se necessário
ROOT_DIR = Path("c:/painel_apostas/sportsbank-pro")
SRC_DIR = ROOT_DIR / "sportsbankzu-pro"
BUILD_DIR = ROOT_DIR / "lambda_build"
ZIP_FILE = ROOT_DIR / "sportsbank_lambda.zip"

def prepare_build():
    print(f"Limpando diretório de build: {BUILD_DIR}")
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)

    print("Instalando dependências para Linux (Lambda)...")
    # Instala dependências diretamente no diretório de build, forçando plataforma Linux
    subprocess.run([
        "pip", "install", 
        "-r", str(SRC_DIR / "backend" / "requirements.txt"), 
        "--target", str(BUILD_DIR),
        "--platform", "manylinux2014_x86_64",
        "--only-binary=:all:",
        "--python-version", "3.11",
        "--upgrade"
    ], check=True)

    print("Copiando código do backend...")
    # Copia a pasta backend para o build
    shutil.copytree(SRC_DIR / "backend", BUILD_DIR / "backend", dirs_exist_ok=True)
    
    # Remove pastas desnecessárias para o Lambda (ex: __pycache__)
    for pycache in BUILD_DIR.rglob("__pycache__"):
        shutil.rmtree(pycache)

def create_zip():
    print(f"Criando arquivo ZIP: {ZIP_FILE}")
    if ZIP_FILE.exists():
        ZIP_FILE.unlink()
        
    with zipfile.ZipFile(ZIP_FILE, 'w', zipfile.ZIP_DEFLATED) as z:
        for file_path in BUILD_DIR.rglob('*'):
            if file_path.is_file():
                z.write(file_path, file_path.relative_to(BUILD_DIR))

S3_BUCKET = "meu-bucket-sportsbank"
S3_KEY = "deploy/sportsbank_lambda.zip"

def deploy_to_aws_via_s3():
    print(f"Enviando ZIP para S3: s3://{S3_BUCKET}/{S3_KEY}")
    try:
        # 1. Upload para S3
        subprocess.run([
            "aws", "s3", "cp", 
            str(ZIP_FILE), 
            f"s3://{S3_BUCKET}/{S3_KEY}"
        ], check=True)
        
        # 2. Update Lambda via S3
        print(f"Atualizando Lambda {FUNCTION_NAME} a partir do S3...")
        subprocess.run([
            "aws", "lambda", "update-function-code",
            "--function-name", FUNCTION_NAME,
            "--s3-bucket", S3_BUCKET,
            "--s3-key", S3_KEY
        ], check=True)
        print("Deploy realizado com sucesso via S3!")
    except Exception as e:
        print(f"Erro ao realizar deploy via S3: {e}")

if __name__ == "__main__":
    try:
        prepare_build()
        create_zip()
        deploy_to_aws_via_s3()
    except Exception as e:
        print(f"Falha no processo: {e}")
