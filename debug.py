import os
from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
import gspread
from google.oauth2.credentials import Credentials

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
_TOKEN_FILE = Path(".google_token.json")

creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)
gc = gspread.authorize(creds)
spreadsheet_id = os.environ["GOOGLE_ADS_SPREADSHEET_ID"]
ss = gc.open_by_key(spreadsheet_id)

print("=== ABAS DISPONÍVEIS ===")
for ws in ss.worksheets():
    print(f"  '{ws.title}'")

print("\n=== GOOGLE ADS — primeiras 5 linhas brutas ===")
try:
    ws = ss.get_worksheet(0)
    rows = ws.get_all_values()
    for i, row in enumerate(rows[:5]):
        print(f"  Linha {i+1}: {row}")
except Exception as e:
    print(f"ERRO: {e}")

print("\n=== META ADS — primeiras 5 linhas brutas ===")
try:
    ws2 = ss.worksheet("Meta Ads")
    rows2 = ws2.get_all_values()
    for i, row in enumerate(rows2[:5]):
        print(f"  Linha {i+1}: {row}")
except Exception as e:
    print(f"ERRO: {e}")
