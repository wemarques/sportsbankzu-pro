try:
    import yaml
    from yaml.loader import SafeLoader
except Exception:
    yaml = None
import streamlit as st
import hashlib
import os

def load_config(file_path='config.yaml'):
    try:
        if 'credentials' in st.secrets:
            config = {'credentials': {'usernames': {}}}
            credentials_data = st.secrets['credentials']
            if hasattr(credentials_data, 'usernames'):
                for username in credentials_data['usernames']:
                    user_data = credentials_data['usernames'][username]
                    config['credentials']['usernames'][username] = {
                        'name': user_data['name'],
                        'password': user_data['password']
                    }
            return config
    except Exception:
        pass
    if os.path.exists(file_path) and yaml:
        with open(file_path, encoding='utf-8') as file:
            config = yaml.load(file, Loader=SafeLoader)
            return config
    raise FileNotFoundError(
        f"Arquivo {file_path} não encontrado e Streamlit secrets não configurado."
    )

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_login(username, password, config):
    credentials = config['credentials']['usernames']
    if username in credentials:
        password_hash = hash_password(password)
        if credentials[username]['password'] == password_hash:
            return True, credentials[username]['name']
    return False, None

class Authenticator:
    def __init__(self, config_path='config.yaml'):
        self.config = load_config(config_path)
        self.credentials = self.config['credentials']
    def login(self):
        if 'authentication_status' not in st.session_state:
            st.session_state['authentication_status'] = None
        if st.session_state['authentication_status']:
            return True
        st.markdown("# 🔐 Login - SportsBank Pro")
        st.markdown("### Sistema de Prognósticos Esportivos")
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### 🎯 Acesso Restrito")
            st.info("📊 Por favor, faça login para acessar o sistema de prognósticos e análises.")
            username = st.text_input("👤 Usuário", key="username_input", placeholder="Digite seu usuário")
            password = st.text_input("🔑 Senha", type="password", key="password_input", placeholder="Digite sua senha")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                login_button = st.button("🚀 Entrar", use_container_width=True, type="primary")
            with col_btn2:
                if st.button("❓ Esqueci a senha", use_container_width=True):
                    st.warning("⚠️ Entre em contato com o administrador do sistema.")
            if login_button:
                if username and password:
                    success, name = check_login(username, password, self.config)
                    if success:
                        st.session_state['authentication_status'] = True
                        st.session_state['name'] = name
                        st.session_state['username'] = username
                        st.success(f"✅ Bem-vindo(a), {name}!")
                        st.rerun()
                    else:
                        st.session_state['authentication_status'] = False
                        st.error("❌ Usuário ou senha incorretos.")
                else:
                    st.warning("⚠️ Por favor, preencha todos os campos.")
        return False
    def logout(self):
        if st.session_state.get('authentication_status'):
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 👤 Usuário Logado")
            st.sidebar.info(f"**{st.session_state.get('name', 'N/A')}**")
            st.sidebar.caption(f"@{st.session_state.get('username', 'N/A')}")
            if st.sidebar.button("🚪 Sair", use_container_width=True):
                self._reset_auth()
                st.rerun()
    def _reset_auth(self):
        st.session_state['authentication_status'] = None
        st.session_state['name'] = None
        st.session_state['username'] = None
