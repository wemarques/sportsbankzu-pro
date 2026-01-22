# 🔐 Solução de Autenticação para SportsBank Pro

## 📋 Visão Geral

Esta solução permite que o site seja **público** (qualquer pessoa pode acessar a URL), mas **exige senha** para visualizar o conteúdo.

---

## 🎯 Características

✅ **Site público:** URL acessível por qualquer pessoa  
✅ **Login obrigatório:** Conteúdo protegido por senha  
✅ **Múltiplos usuários:** Suporta vários logins diferentes  
✅ **Session state:** Mantém usuário logado durante a sessão  
✅ **Logout:** Botão para sair da conta  
✅ **Seguro:** Senhas em hash (não armazenadas em texto puro)  
✅ **Fácil de configurar:** Arquivo YAML para credenciais  

---

## 📁 Estrutura de Arquivos

```
sportsbank-pro/
├── app.py                    # Arquivo principal (modificado)
├── auth.py                   # Novo arquivo de autenticação
├── config.yaml               # Novo arquivo de credenciais
├── backend/
│   └── main.py
├── requirements.txt          # Adicionar dependências
└── README.md
```

---

## 🔧 Implementação

### **1. Criar arquivo `auth.py`**

```python
import yaml
import streamlit as st
from yaml.loader import SafeLoader
import hashlib

def load_config(file_path):
    """Carrega o arquivo de configuração YAML"""
    with open(file_path) as file:
        config = yaml.load(file, Loader=SafeLoader)
        return config

def hash_password(password):
    """Gera hash SHA256 da senha"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_login(username, password, config):
    """
    Verifica se o usuário e senha correspondem às credenciais no config.
    """
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
        """Exibe formulário de login e gerencia autenticação"""
        
        # Inicializar session state
        if 'authentication_status' not in st.session_state:
            st.session_state['authentication_status'] = None
        
        # Se já está autenticado, retornar True
        if st.session_state['authentication_status']:
            return True
        
        # Exibir formulário de login
        st.markdown("# 🔐 Login - SportsBank Pro")
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("### Acesso Restrito")
            st.info("Por favor, faça login para acessar o sistema de prognósticos.")
            
            username = st.text_input("👤 Usuário", key="username_input")
            password = st.text_input("🔑 Senha", type="password", key="password_input")
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                login_button = st.button("🚀 Entrar", use_container_width=True)
            
            with col_btn2:
                if st.button("❓ Esqueci a senha", use_container_width=True):
                    st.warning("Entre em contato com o administrador do sistema.")
            
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
                        st.error("❌ Usuário ou senha incorretos")
                else:
                    st.warning("⚠️ Por favor, preencha todos os campos")
        
        return False
    
    def logout(self):
        """Exibe botão de logout na sidebar"""
        if st.session_state.get('authentication_status'):
            st.sidebar.markdown("---")
            st.sidebar.markdown(f"👤 **Usuário:** {st.session_state.get('name', 'N/A')}")
            if st.sidebar.button("🚪 Sair", use_container_width=True):
                self._reset_auth()
                st.rerun()
    
    def _reset_auth(self):
        """Limpa o session state de autenticação"""
        st.session_state['authentication_status'] = None
        st.session_state['name'] = None
        st.session_state['username'] = None
```

---

### **2. Criar arquivo `config.yaml`**

```yaml
credentials:
  usernames:
    admin:
      name: "Administrador"
      password: "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"  # senha: admin
    
    usuario1:
      name: "Usuário Teste"
      password: "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"  # senha: password
    
    wemarques:
      name: "Wellington Marques"
      password: "YOUR_PASSWORD_HASH_HERE"  # Gere seu hash abaixo

# Como gerar hash da senha:
# import hashlib
# senha = "sua_senha_aqui"
# hash_senha = hashlib.sha256(senha.encode()).hexdigest()
# print(hash_senha)
```

---

### **3. Modificar arquivo `app.py`**

Adicione estas linhas no **INÍCIO** do arquivo `app.py`:

```python
import streamlit as st
from auth import Authenticator

# Configurar página
st.set_page_config(
    page_title="SportsBank Pro",
    page_icon="⚽",
    layout="wide"
)

# Inicializar autenticador
authenticator = Authenticator('config.yaml')

# Verificar autenticação
if not authenticator.login():
    st.stop()  # Para a execução se não estiver autenticado

# Exibir botão de logout
authenticator.logout()

# ============================================
# RESTO DO CÓDIGO DO APP.PY CONTINUA AQUI
# ============================================

st.title("⚽ SportsBank Pro - Sistema de Prognósticos")
# ... resto do código ...
```

---

### **4. Atualizar `requirements.txt`**

Adicione esta linha:

```txt
PyYAML==6.0.1
```

---

## 🔑 Como Gerar Hash de Senha

Execute este código Python para gerar o hash da sua senha:

```python
import hashlib

def gerar_hash_senha(senha):
    hash_senha = hashlib.sha256(senha.encode()).hexdigest()
    return hash_senha

# Exemplo de uso
senha = "minha_senha_secreta"
hash_gerado = gerar_hash_senha(senha)
print(f"Senha: {senha}")
print(f"Hash: {hash_gerado}")
```

**Copie o hash gerado** e cole no arquivo `config.yaml`.

---

## 👥 Como Adicionar Novos Usuários

Edite o arquivo `config.yaml`:

```yaml
credentials:
  usernames:
    novo_usuario:
      name: "Nome do Novo Usuário"
      password: "HASH_DA_SENHA_AQUI"
```

---

## 🚀 Como Testar Localmente

1. **Instale as dependências:**
```bash
pip install PyYAML
```

2. **Crie os arquivos:**
   - `auth.py`
   - `config.yaml`

3. **Modifique o `app.py`**

4. **Execute o Streamlit:**
```bash
streamlit run app.py
```

5. **Teste o login:**
   - Usuário: `admin`
   - Senha: `admin`

---

## 🌐 Como Publicar no Streamlit Cloud

### **Passo 1: Adicionar ao GitHub**

```bash
git add auth.py config.yaml
git commit -m "feat: adiciona sistema de autenticação"
git push
```

### **Passo 2: Configurar Secrets no Streamlit Cloud**

⚠️ **IMPORTANTE:** Não deixe `config.yaml` público com senhas reais!

**Opção A: Usar Streamlit Secrets**

1. No Streamlit Cloud, vá em **Settings → Secrets**
2. Cole este conteúdo:

```toml
[credentials.usernames.admin]
name = "Administrador"
password = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"

[credentials.usernames.usuario1]
name = "Usuário Teste"
password = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
```

3. Modifique `auth.py` para ler de secrets:

```python
def load_config(file_path=None):
    """Carrega configuração do arquivo ou do Streamlit secrets"""
    if file_path and os.path.exists(file_path):
        with open(file_path) as file:
            config = yaml.load(file, Loader=SafeLoader)
            return config
    else:
        # Usar Streamlit secrets
        return dict(st.secrets)
```

---

## 🔒 Segurança

### ✅ **Boas Práticas Implementadas:**

1. **Senhas em hash:** Nunca armazenadas em texto puro
2. **Session state:** Mantém login durante a sessão
3. **Logout:** Permite sair com segurança
4. **Secrets:** Credenciais não ficam no código

### ⚠️ **Limitações:**

- Não é autenticação de nível empresarial
- Não tem recuperação de senha automática
- Não tem 2FA (autenticação de dois fatores)
- Adequado para uso pessoal ou pequenas equipes

---

## 📊 Fluxo de Funcionamento

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Usuário acessa URL pública                               │
│    https://sportsbankzu-pro.streamlit.app                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Sistema verifica session_state['authentication_status']  │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────┐         ┌──────────────────┐
│ Não logado   │         │ Já logado        │
│ (None/False) │         │ (True)           │
└──────┬───────┘         └────────┬─────────┘
       │                          │
       ▼                          ▼
┌──────────────────┐     ┌────────────────────┐
│ Exibe formulário │     │ Exibe conteúdo do  │
│ de login         │     │ sistema            │
└──────┬───────────┘     └────────────────────┘
       │
       ▼
┌──────────────────┐
│ Usuário digita   │
│ credenciais      │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Verifica no      │
│ config.yaml      │
└──────┬───────────┘
       │
  ┌────┴────┐
  │         │
  ▼         ▼
┌────┐   ┌──────┐
│ ✅ │   │ ❌   │
│ OK │   │ Erro │
└─┬──┘   └──────┘
  │
  ▼
┌──────────────────┐
│ Define           │
│ session_state    │
│ = True           │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Recarrega página │
│ (st.rerun())     │
└──────────────────┘
```

---

## ✅ Checklist de Implementação

- [ ] Criar arquivo `auth.py`
- [ ] Criar arquivo `config.yaml`
- [ ] Gerar hash das senhas
- [ ] Modificar `app.py` (adicionar autenticação no início)
- [ ] Adicionar `PyYAML==6.0.1` no `requirements.txt`
- [ ] Testar localmente
- [ ] Fazer commit e push para GitHub
- [ ] Configurar Secrets no Streamlit Cloud (se publicar)
- [ ] Testar login no site publicado

---

## 🎯 Resultado Final

Quando implementado, o sistema funcionará assim:

1. **Usuário acessa a URL pública**
2. **Vê tela de login** (não vê o conteúdo)
3. **Digita usuário e senha**
4. **Se correto:** Acessa o sistema completo
5. **Se incorreto:** Mensagem de erro
6. **Pode fazer logout** a qualquer momento

---

## 💡 Melhorias Futuras (Opcional)

- Adicionar limite de tentativas de login
- Adicionar log de acessos
- Adicionar recuperação de senha por email
- Adicionar autenticação de dois fatores (2FA)
- Adicionar níveis de permissão (admin, usuário, visitante)
- Integrar com banco de dados para gerenciar usuários

---

Esta solução é **simples, segura e eficaz** para proteger seu sistema SportsBank Pro! 🔒⚽
