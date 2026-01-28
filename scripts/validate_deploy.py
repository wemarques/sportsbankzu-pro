"""
Script de validacao de deploy.
Testa endpoints principais e valida funcionamento.
"""
import sys
from typing import List, Tuple
import requests


def test_endpoint(url: str, name: str, timeout: int = 5) -> Tuple[bool, str]:
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            return True, f"OK: {name}"
        return False, f"Status {response.status_code}: {name}"
    except requests.exceptions.Timeout:
        return False, f"Timeout: {name}"
    except requests.exceptions.ConnectionError:
        return False, f"Conexao falhou: {name}"
    except Exception as e:
        return False, f"Erro: {name} -> {e}"


def validate_backend(backend_url: str) -> List[Tuple[bool, str]]:
    results = []
    endpoints = [
        ("/health", "Health Check"),
        ("/discover", "Discover Leagues"),
        ("/fixtures?leagues=premier-league&date=today", "Fixtures"),
    ]
    for endpoint, name in endpoints:
        url = f"{backend_url}{endpoint}"
        results.append(test_endpoint(url, name))
    return results


def validate_streamlit(streamlit_url: str) -> Tuple[bool, str]:
    return test_endpoint(streamlit_url, "Streamlit App", timeout=10)


def main() -> int:
    print("Validando deploy do SportsBank Pro
")
    backend_url = input("URL do Backend (ex: https://seu-backend.com): ").strip()
    streamlit_url = input("URL do Streamlit (ex: https://seu-app.streamlit.app): ").strip()

    print("
" + "=" * 60)
    print("VALIDANDO BACKEND")
    print("=" * 60 + "
")

    backend_results = validate_backend(backend_url)
    backend_success = all(r[0] for r in backend_results)
    for success, message in backend_results:
        print(("OK" if success else "ERRO") + ": " + message)

    print("
" + "=" * 60)
    print("VALIDANDO STREAMLIT")
    print("=" * 60 + "
")

    streamlit_success, streamlit_message = validate_streamlit(streamlit_url)
    print(("OK" if streamlit_success else "ERRO") + ": " + streamlit_message)

    print("
" + "=" * 60)
    print("RESULTADO FINAL")
    print("=" * 60 + "
")

    if backend_success and streamlit_success:
        print("Deploy validado com sucesso!")
        return 0

    print("Deploy com problemas. Verifique os erros acima.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
