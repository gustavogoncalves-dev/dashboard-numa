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
