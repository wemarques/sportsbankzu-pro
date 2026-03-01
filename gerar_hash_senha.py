"""
Gerador de Hash de Senha para SportsBankZU Pro
Utilize este script para gerar hashes SHA-256 de senhas
"""

import hashlib

def gerar_hash_senha(senha):
    """
    Gera hash SHA256 da senha
    
    Args:
        senha (str): Senha em texto puro
    
    Returns:
        str: Hash SHA256 da senha
    """
    return hashlib.sha256(senha.encode()).hexdigest()

def main():
    print("=" * 60)
    print("🔐 GERADOR DE HASH DE SENHA - SportsBankZU Pro")
    print("=" * 60)
    print()
    
    while True:
        print("Digite a senha para gerar o hash (ou 'sair' para encerrar):")
        senha = input("Senha: ")
        
        if senha.lower() == 'sair':
            print("\n👋 Encerrando...")
            break
        
        if not senha:
            print("⚠️  Senha não pode ser vazia!\n")
            continue
        
        hash_gerado = gerar_hash_senha(senha)
        
        print("\n" + "=" * 60)
        print("✅ Hash gerado com sucesso!")
        print("=" * 60)
        print(f"Senha (texto puro): {senha}")
        print(f"Hash SHA-256:       {hash_gerado}")
        print("=" * 60)
        print()
        print("📋 Copie o hash acima e cole no arquivo config.yaml")
        print("   no campo 'password' do usuário correspondente.")
        print()
        print("Exemplo:")
        print("  credentials:")
        print("    usernames:")
        print("      seu_usuario:")
        print("        name: \"Seu Nome\"")
        print(f"        password: \"{hash_gerado}\"")
        print()
        print("=" * 60)
        print()

if __name__ == "__main__":
    main()
