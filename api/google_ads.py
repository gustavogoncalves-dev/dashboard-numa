import os
import pandas as pd
from datetime import date
from pathlib import Path
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
_TOKEN_FILE = Path(__file__).parent.parent / ".google_token.json"
_CLIENT_SECRETS_FILE = Path(__file__).parent.parent / "client_secret.json"

# Colunas exportadas pelo Google Ads → padrão interno
_COL_MAP = {
    "dia": "date",
    "day": "date",
    "campanha": "campaign_name",
    "campaign": "campaign_name",
    "custo": "spend",
    "cost": "spend",
    "impr.": "impressions",
    "impressões": "impressions",
    "impressions": "impressions",
    "cliques": "clicks",
    "clicks": "clicks",
    "cpc méd.": "cpc",
    "cpc med.": "cpc",
    "avg. cpc": "cpc",
    "cpc": "cpc",
    "ctr": "ctr",
    "custo por mil impressões (cpm)": "cpm",
    "cpm": "cpm",
    "código da moeda": None,   # ignorar
    "currency code": None,
}


def _get_credentials() -> Credentials:
    creds = None
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(_CLIENT_SECRETS_FILE), _SCOPES
            )
            creds = flow.run_local_server(port=0)
        _TOKEN_FILE.write_text(creds.to_json())
    return creds


def _to_float(value) -> float:
    try:
        s = str(value).strip()
        s = s.replace("R$", "").replace("%", "").replace(" ", "")
        s = s.replace(".", "").replace(",", ".")
        return float(s)
    except Exception:
        return 0.0


def fetch_campaign_stats(start_date: date, end_date: date) -> pd.DataFrame:
    spreadsheet_id = os.environ["GOOGLE_ADS_SPREADSHEET_ID"]

    creds = _get_credentials()
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(spreadsheet_id)

    # Usa a primeira aba (Página1) por padrão, ou o nome definido no .env
    sheet_name = os.environ.get("GOOGLE_ADS_SHEET_NAME", "")
    if sheet_name:
        worksheet = spreadsheet.worksheet(sheet_name)
    else:
        worksheet = spreadsheet.get_worksheet(0)

    all_values = worksheet.get_all_values()
    if len(all_values) < 2:
        return pd.DataFrame()

    raw_headers = [h.strip().lower() for h in all_values[0]]
    data_rows = all_values[1:]

    rows = []
    for row in data_rows:
        if not any(row):
            continue
        record = {}
        for i, val in enumerate(row):
            if i >= len(raw_headers):
                continue
            col = _COL_MAP.get(raw_headers[i], raw_headers[i])
            if col is None:
                continue
            record[col] = val
        rows.append(record)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    df["date"] = pd.to_datetime(df.get("date", pd.NaT), errors="coerce")
    df = df.dropna(subset=["date"])

    mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
    df = df[mask].copy()

    if df.empty:
        return pd.DataFrame()

    for col in ["spend", "impressions", "clicks", "cpc", "ctr", "cpm"]:
        if col in df.columns:
            df[col] = df[col].apply(_to_float)

    if "conversions" not in df.columns:
        df["conversions"] = 0.0
    if "cpa" not in df.columns:
        df["cpa"] = 0.0

    df["platform"] = "Google Ads"
    df["campaign_id"] = ""
    df["reach"] = None
    df["frequency"] = None

    return df
