"""
Rode este script UMA VEZ no terminal para autorizar o acesso ao Google Sheets.
Ele vai abrir o navegador, você faz login, e o token é salvo em .google_token.json.
Depois disso o dashboard funciona sem precisar rodar isso de novo.
"""
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]
TOKEN_FILE = Path(__file__).parent / ".google_token.json"
CLIENT_SECRETS = Path(__file__).parent / "client_secret.json"

creds = None
if TOKEN_FILE.exists():
    import json as _json
    # Lê os escopos REAIS gravados no arquivo (não os pedidos) para detectar
    # tokens antigos sem analytics.readonly. Passar SCOPES ao construtor faz
    # creds.scopes refletir o que foi pedido, mascarando o que o token tem.
    _saved = set(_json.loads(TOKEN_FILE.read_text()).get("scopes", []))
    if not set(SCOPES).issubset(_saved):
        print(f"Escopos insuficientes no token ({sorted(_saved)}) — forçando nova autorização.")
        creds = None
    else:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        print("Token renovado com sucesso.")
    else:
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
        print("Autorização concluída com sucesso.")
    TOKEN_FILE.write_text(creds.to_json())

print(f"Token salvo em: {TOKEN_FILE}")
print("Pode fechar este terminal e usar o dashboard normalmente.")
