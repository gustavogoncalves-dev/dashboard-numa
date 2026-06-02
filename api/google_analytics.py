import os
import json
import tempfile
import pandas as pd
from pathlib import Path
from datetime import date
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

TOKEN_FILE = Path(__file__).parent.parent / ".google_token.json"


def _build_client() -> BetaAnalyticsDataClient:
    if TOKEN_FILE.exists():
        token_path = TOKEN_FILE
    else:
        token_json = os.environ.get("GOOGLE_TOKEN_JSON", "")
        if not token_json:
            raise RuntimeError("GOOGLE_TOKEN_JSON não configurado e .google_token.json não encontrado")
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text(token_json)
        token_path = tmp

    raw = json.loads(token_path.read_text())

    # from_authorized_user_info parseia expiry corretamente — evita usar token expirado
    creds = Credentials.from_authorized_user_info(raw)

    # Refresh sempre que inválido OU expirado
    if not creds.valid or creds.expired:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())

    return BetaAnalyticsDataClient(credentials=creds)


def fetch_session_stats(start_date: date, end_date: date) -> pd.DataFrame:
    client = _build_client()
    property_id = os.environ["GA4_PROPERTY_ID"]

    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=str(start_date), end_date=str(end_date))],
        dimensions=[
            Dimension(name="date"),
            Dimension(name="sessionCampaignName"),
            Dimension(name="sessionSource"),
            Dimension(name="sessionMedium"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="engagementRate"),
            Metric(name="bounceRate"),
            Metric(name="averageSessionDuration"),
            Metric(name="screenPageViewsPerSession"),
            Metric(name="conversions"),
            Metric(name="totalRevenue"),
        ],
    )

    response = client.run_report(request)

    rows = []
    for row in response.rows:
        dims = [d.value for d in row.dimension_values]
        vals = [v.value for v in row.metric_values]
        rows.append({
            "date":                 dims[0],
            "campaign_name":        dims[1],
            "source":               dims[2],
            "medium":               dims[3],
            "sessions":             int(vals[0]),
            "engagement_rate":      float(vals[1]) * 100,
            "bounce_rate":          float(vals[2]) * 100,
            "avg_session_duration": float(vals[3]),
            "pages_per_session":    float(vals[4]),
            "ga4_conversions":      float(vals[5]),
            "revenue":              float(vals[6]),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    return df
