"""
Loader robusto do token OAuth do Google compartilhado por Ads, Meta e GA4.

Prioriza o arquivo local `.google_token.json`. No deploy (Streamlit Cloud),
lê a variável/secret `GOOGLE_TOKEN_JSON`, aceitando TANTO JSON cru QUANTO
base64. O base64 evita o inferno de aspas/escape ao colar JSON em secrets TOML
(causa comum de `json.JSONDecodeError: Expecting value`).
"""
import os
import json
import base64
from pathlib import Path

_TOKEN_FILE = Path(__file__).parent.parent / ".google_token.json"
_CLIENT_SECRETS = Path(__file__).parent.parent / "client_secret.json"

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]


def token_file() -> Path:
    return _TOKEN_FILE


def get_token_text() -> str:
    """Retorna o conteúdo JSON do token como texto, ou "" se indisponível.

    - Se `.google_token.json` existir, devolve o conteúdo dele (uso local).
    - Senão, lê `GOOGLE_TOKEN_JSON`: se começar com '{' trata como JSON cru;
      caso contrário tenta decodificar de base64.
    """
    if _TOKEN_FILE.exists():
        return _TOKEN_FILE.read_text()

    raw = os.environ.get("GOOGLE_TOKEN_JSON", "").strip()
    if not raw:
        return ""

    if raw.startswith("{"):
        return raw

    # Tenta base64 (tolera padding faltando)
    try:
        decoded = base64.b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8").strip()
        if decoded.startswith("{"):
            json.loads(decoded)  # valida antes de devolver
            return decoded
    except Exception:
        pass

    # Devolve como veio para o chamador estourar com mensagem clara
    return raw


def reauth() -> None:
    """Abre o navegador para reautorizar o Google OAuth e salva o novo token.

    Chamado automaticamente quando o refresh token é inválido (invalid_grant).
    Isso ocorre quando o app está em modo "Testing" no Google Cloud Console
    (tokens expiram em 7 dias) ou quando o acesso foi revogado manualmente.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    _TOKEN_FILE.unlink(missing_ok=True)
    flow = InstalledAppFlow.from_client_secrets_file(
        str(_CLIENT_SECRETS), _SCOPES, redirect_uri="http://localhost"
    )
    creds = flow.run_local_server(port=0, prompt="consent")
    _TOKEN_FILE.write_text(creds.to_json())
    return creds
