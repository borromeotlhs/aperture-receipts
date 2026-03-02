import os
import json
from flask import Flask, redirect, request, url_for
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

def client_config():
    # Put your OAuth "Web application" client_id/secret into Railway env vars
    return {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

@app.get("/")
def home():
    return "Aperture Receipts: OK. Go to /auth to connect Google."

@app.get("/auth")
def auth():
    flow = Flow.from_client_config(
        client_config(),
        scopes=SCOPES,
        redirect_uri=url_for("oauth2callback", _external=True),
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return redirect(auth_url)

@app.get("/oauth2callback")
def oauth2callback():
    flow = Flow.from_client_config(
        client_config(),
        scopes=SCOPES,
        redirect_uri=url_for("oauth2callback", _external=True),
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    # For now we just prove Drive access by listing a few files
    service = build("drive", "v3", credentials=creds)
    results = service.files().list(pageSize=5, fields="files(id,name)").execute()
    items = results.get("files", [])

    return {
        "status": "authorized",
        "sample_files": items,
        "note": "Next step: store refresh token securely + process receipts folder + write to Spent sheet."
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=True)
