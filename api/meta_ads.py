import os
import tempfile
import pandas as pd
from datetime import date
from pathlib import Path
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from utils.google_token import get_token_text, reauth

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
_TOKEN_FILE = Path(__file__).parent.parent / ".google_token.json"
_CLIENT_SECRETS_FILE = Path(__file__).parent.parent / "client_secret.json"

# Mapeamento do formato Coupler "Category: Field" para nosso padrão
_COL_MAP = {
    "report: date": "date",
    "campaign: campaign name": "campaign_name",
    "clicks: ctr": "ctr",
    "cost: amount spend": "spend",
    "cost: cpc": "cpc",
    "performance: clicks": "clicks",
    "performance: frequency": "frequency",
    "performance: impressions": "impressions",
    "performance: reach": "reach",
}


def _get_credentials() -> Credentials:
    if _TOKEN_FILE.exists():
        token_path = _TOKEN_FILE
    else:
        text = get_token_text()  # aceita JSON cru ou base64 via GOOGLE_TOKEN_JSON
        if text:
            tmp = Path(tempfile.mktemp(suffix=".json"))
            tmp.write_text(text)
            token_path = tmp
        else:
            token_path = _TOKEN_FILE

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                token_path.write_text(creds.to_json())
            except RefreshError:
                reauth()
                creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)
        else:
            reauth()
            creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)
    return creds


def _to_float(value) -> float:
    try:
        return float(str(value).replace(",", ".").replace(" ", ""))
    except Exception:
        return 0.0


def fetch_campaign_stats(start_date: date, end_date: date) -> pd.DataFrame:
    spreadsheet_id = os.environ["GOOGLE_ADS_SPREADSHEET_ID"]
    sheet_name = os.environ.get("META_SHEET_NAME", "Meta Ads")

    creds = _get_credentials()
    gc = gspread.authorize(creds)

    spreadsheet = gc.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(sheet_name)

    all_values = worksheet.get_all_values()
    if len(all_values) < 2:
        return pd.DataFrame()

    # Linha 0 = cabeçalhos do Coupler ("Report: Date", "Campaign: Campaign name", etc.)
    raw_headers = [h.strip().lower() for h in all_values[0]]
    data_rows = all_values[1:]

    rows = []
    for row in data_rows:
        if not any(row):
            continue
        record = {}
        for i, val in enumerate(row):
            if i < len(raw_headers):
                col = _COL_MAP.get(raw_headers[i], raw_headers[i])
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

    for col in ["spend", "impressions", "clicks", "cpc", "ctr", "reach", "frequency"]:
        if col in df.columns:
            df[col] = df[col].apply(_to_float)

    # CTR já vem em % do Coupler (ex: 7.63), não precisa multiplicar
    if "conversions" not in df.columns:
        df["conversions"] = 0.0
    if "cpa" not in df.columns:
        df["cpa"] = 0.0

    df["platform"] = "Meta Ads"
    df["campaign_id"] = ""

    return df
