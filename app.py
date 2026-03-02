import os
import json
from flask import Flask, redirect, request, url_for, session
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

TOKEN_PATH = os.environ.get("TOKEN_PATH", "token.json")


def client_config():
    return {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def save_creds(creds: Credentials) -> None:
    os.makedirs(os.path.dirname(TOKEN_PATH) or ".", exist_ok=True)
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def load_creds() -> Credentials | None:
    if not os.path.exists(TOKEN_PATH):
        return None
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Credentials.from_authorized_user_info(data, scopes=SCOPES)


def get_creds() -> Credentials | None:
    creds = load_creds()
    if not creds:
        return None
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_creds(creds)
    return creds


@app.get("/")
def home():
    creds = get_creds()
    if creds:
        return "Aperture Receipts: authorized ✅ (token stored). Next: /files"
    return "Aperture Receipts: not authorized yet. Go to /auth"


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
    session["oauth_state"] = state
    return redirect(auth_url)


@app.get("/oauth2callback")
def oauth2callback():
    flow = Flow.from_client_config(
        client_config(),
        scopes=SCOPES,
        redirect_uri=url_for("oauth2callback", _external=True),
        state=session.get("oauth_state"),
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    save_creds(creds)

    # quick proof it works
    service = build("drive", "v3", credentials=creds)
    results = service.files().list(pageSize=3, fields="files(id,name)").execute()
    items = results.get("files", [])

    return {
        "status": "authorized",
        "token_saved_to": TOKEN_PATH,
        "sample_files": items,
        "next": "Go to / to confirm it stays authorized after redeploy.",
    }


# Placeholder for next steps (B)
@app.get("/files")
def files():
    creds = get_creds()
    if not creds:
        return {"error": "Not authorized. Visit /auth first."}, 401
    return {"ok": True, "note": "B will list files in your receipts folder."}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=True)
