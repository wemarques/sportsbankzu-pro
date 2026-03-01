"""
Sistema de Autenticação para SportsBankZU Pro
Autor: SportsBank Team
Data: 2026-01-22
"""


try:
    import yaml
    from yaml.loader import SafeLoader
except Exception:
    yaml = None
    SafeLoader = None
import streamlit as st
import hashlib
import os


def load_config(file_path='config.yaml'):
    """
    Carrega o arquivo de configuração YAML ou Streamlit secrets
    
    Args:
        file_path (str): Caminho para o arquivo config.yaml
    
    Returns:
        dict: Configuração carregada
    """
    # Primeiro, tentar carregar do Streamlit secrets (produção)
    try:
        if 'credentials' in st.secrets:
            # Converter secrets TOML para formato dict
            config = {
                'credentials': {
                    'usernames': {}
                }
            }
            
            # Reconstruir estrutura de credentials
            if hasattr(st.secrets, 'credentials'):
                credentials_data = st.secrets['credentials']
                if hasattr(credentials_data, 'usernames'):
                    for username in credentials_data['usernames']:
                        user_data = credentials_data['usernames'][username]
                        config['credentials']['usernames'][username] = {
                            'name': user_data['name'],
                            'password': user_data['password']
                        }
            
            return config
    except Exception as e:
        # Se falhar ao ler secrets, continuar para arquivo local
        pass
    
    # Fallback: tentar carregar do arquivo local (desenvolvimento)
    if os.path.exists(file_path):
        if yaml is None:
            raise ModuleNotFoundError(
                "PyYAML nao esta instalado. Instale PyYAML ou use Secrets do Streamlit."
            )
        with open(file_path, encoding='utf-8') as file:
            config = yaml.load(file, Loader=SafeLoader)
            return config
    
    # Se nenhum dos dois funcionar, lançar erro
    raise FileNotFoundError(
        f"Arquivo {file_path} não encontrado e Streamlit secrets não configurado. "
        "Por favor, crie o arquivo config.yaml ou configure os secrets no Streamlit Cloud."
    )


def hash_password(password):
    """
    Gera hash SHA256 da senha
    
    Args:
        password (str): Senha em texto puro
    
    Returns:
        str: Hash SHA256 da senha
    """
    return hashlib.sha256(password.encode()).hexdigest()


def check_login(username, password, config):
    """
    Verifica se o usuário e senha correspondem às credenciais no config
    
    Args:
        username (str): Nome de usuário
        password (str): Senha em texto puro
        config (dict): Configuração com credenciais
    
    Returns:
        tuple: (sucesso: bool, nome: str ou None)
    """
    credentials = config['credentials']['usernames']
    
    if username in credentials:
        password_hash = hash_password(password)
        if credentials[username]['password'] == password_hash:
            return True, credentials[username]['name']
    
    return False, None


class Authenticator:
    """
    Classe principal de autenticação para Streamlit
    """
    
    def __init__(self, config_path='config.yaml'):
        """
        Inicializa o autenticador
        
        Args:
            config_path (str): Caminho para o arquivo de configuração
        """
        self.config = load_config(config_path)
        self.credentials = self.config['credentials']
    
    def login(self):
        """
        Exibe formulário de login e gerencia autenticação
        
        Returns:
            bool: True se autenticado, False caso contrário
        """
        
        # Inicializar session state
        if 'authentication_status' not in st.session_state:
            st.session_state['authentication_status'] = None
        
        # Se já está autenticado, retornar True
        if st.session_state['authentication_status']:
            return True
        
        # Exibir formulário de login
        st.markdown("# 🔐 Login - SportsBankZU Pro")
        st.markdown("### Sistema de Prognósticos Esportivos")
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("### 🎯 Acesso Restrito")
            st.info("📊 Por favor, faça login para acessar o sistema de prognósticos e análises.")
            
            # Campos de login
            username = st.text_input(
                "👤 Usuário",
                key="username_input",
                placeholder="Digite seu usuário"
            )
            
            password = st.text_input(
                "🔑 Senha",
                type="password",
                key="password_input",
                placeholder="Digite sua senha"
            )
            
            # Botões
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                login_button = st.button("🚀 Entrar", use_container_width=True, type="primary")
            
            with col_btn2:
                if st.button("❓ Esqueci a senha", use_container_width=True):
                    st.warning("⚠️ Entre em contato com o administrador do sistema para recuperar sua senha.")
            
            # Processar login
            if login_button:
                if username and password:
                    success, name = check_login(username, password, self.config)
                    
                    if success:
                        st.session_state['authentication_status'] = True
                        st.session_state['name'] = name
                        st.session_state['username'] = username
                        st.success(f"✅ Bem-vindo(a), {name}!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.session_state['authentication_status'] = False
                        st.error("❌ Usuário ou senha incorretos. Tente novamente.")
                else:
                    st.warning("⚠️ Por favor, preencha todos os campos.")
            
            # Informações adicionais
            st.markdown("---")
            st.caption("🔒 Suas credenciais são protegidas com criptografia SHA-256.")
        
        return False
    
    def logout(self):
        """
        Exibe botão de logout na sidebar
        """
        if st.session_state.get('authentication_status'):
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 👤 Usuário Logado")
            st.sidebar.info(f"**{st.session_state.get('name', 'N/A')}**")
            st.sidebar.caption(f"@{st.session_state.get('username', 'N/A')}")
            
            if st.sidebar.button("🚪 Sair", use_container_width=True, type="secondary"):
                self._reset_auth()
                st.success("✅ Logout realizado com sucesso!")
                st.rerun()
    
    def _reset_auth(self):
        """
        Limpa o session state de autenticação
        """
        st.session_state['authentication_status'] = None
        st.session_state['name'] = None
        st.session_state['username'] = None


def gerar_hash_senha(senha):
    """
    Função auxiliar para gerar hash de senha
    Útil para criar novas credenciais
    
    Args:
        senha (str): Senha em texto puro
    
    Returns:
        str: Hash SHA256 da senha
    
    Exemplo:
        >>> gerar_hash_senha("minha_senha")
        '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8'
    """
    return hash_password(senha)


# Exemplo de uso (comentado)
if __name__ == "__main__":
    # Gerar hash de senha para adicionar ao config.yaml
    senha_teste = "admin"
    hash_gerado = gerar_hash_senha(senha_teste)
    print(f"Senha: {senha_teste}")
    print(f"Hash: {hash_gerado}")
