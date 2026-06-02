# Media Dashboard — Guia de Configuração

## 1. Pré-requisitos

- Python 3.11+
- Contas de anunciante ativas no Google Ads e Meta Ads
- Propriedade GA4 com dados de e-commerce / eventos configurados

---

## 2. Instalação local

```bash
cd media-dashboard
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Copie o arquivo de variáveis:
```bash
copy .env.example .env
```

Edite o `.env` com suas credenciais (veja seções abaixo).

Rode o app:
```bash
streamlit run app.py
```

---

## 3. Credenciais Google Ads

1. Acesse https://developers.google.com/google-ads/api/docs/get-started/introduction
2. Crie um projeto no Google Cloud Console e ative a **Google Ads API**
3. Crie credenciais OAuth 2.0 (Desktop app)
4. Solicite um **Developer Token** em https://ads.google.com → Ferramentas → Centro de API
5. Gere o `refresh_token` com o script de autenticação OAuth do Google Ads Python Client
6. Preencha no `.env`:
   - `GOOGLE_ADS_DEVELOPER_TOKEN`
   - `GOOGLE_ADS_CLIENT_ID`
   - `GOOGLE_ADS_CLIENT_SECRET`
   - `GOOGLE_ADS_REFRESH_TOKEN`
   - `GOOGLE_ADS_CUSTOMER_ID` (ID da conta sem traços, ex: `1234567890`)

---

## 4. Credenciais Meta Ads

1. Acesse https://developers.facebook.com e crie um App (tipo Business)
2. Adicione o produto **Marketing API**
3. Gere um **User Access Token** de longa duração (60 dias) via Graph API Explorer:
   - Escopo necessário: `ads_read`, `read_insights`
4. Encontre o ID da sua conta de anúncios em https://business.facebook.com → Contas de anúncio
5. Preencha no `.env`:
   - `META_ACCESS_TOKEN`
   - `META_AD_ACCOUNT_ID` (formato `act_123456789`)
   - `META_APP_ID`
   - `META_APP_SECRET`

---

## 5. Credenciais GA4 (Service Account)

1. No Google Cloud Console, crie uma **Service Account**
2. Baixe o JSON da chave
3. No GA4, adicione o e-mail da service account como **Leitor** da propriedade
4. Cole o conteúdo do JSON (em uma linha) na variável `GA4_SERVICE_ACCOUNT_JSON`
5. Configure `GA4_PROPERTY_ID` (número da propriedade, sem "properties/")

### Importante: UTM tracking
Para o cruzamento funcionar, os anúncios devem usar UTM parameters com o **mesmo nome de campanha** que aparece no Google Ads / Meta. Configure os templates de URL:

- Google Ads: `{lpurl}?utm_source=google&utm_medium=cpc&utm_campaign={campaign.name}`
- Meta Ads: use os parâmetros de URL nas campanhas com `{{campaign.name}}`

---

## 6. Deploy no Streamlit Community Cloud (gratuito)

1. Crie um repositório privado no GitHub e faça push do projeto
2. Acesse https://share.streamlit.io e conecte o repositório
3. Configure as variáveis de ambiente em **Settings → Secrets** (mesmo formato do `.env`)
4. O app ficará disponível em `https://seu-app.streamlit.app`

---

## 7. Estrutura do projeto

```
media-dashboard/
├── app.py                  # App principal Streamlit
├── requirements.txt
├── .env.example
├── api/
│   ├── google_ads.py       # Busca dados do Google Ads API
│   ├── meta_ads.py         # Busca dados da Meta Marketing API
│   └── google_analytics.py # Busca dados da GA4 Data API
├── components/
│   ├── pre_click.py        # KPIs e gráficos de pré-clique
│   ├── post_click.py       # KPIs e gráficos de pós-clique
│   └── cross_data.py       # Análise cruzada pré vs. pós
└── utils/
    └── data.py             # Merge, agregações e formatação
```
