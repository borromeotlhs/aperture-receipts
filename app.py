import os
from flask import Flask, redirect, request, url_for, session
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

# IMPORTANT:
# Set this in Railway as a long random value (e.g., 32+ chars)
# Railway variable name I'd use: FLASK_SECRET_KEY
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.environ.get("FLASK_SECRET", "dev"))

# Ensure Flask knows the real scheme/host behind Railway's proxy
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

def redirect_uri():
    """
    Use an explicit env var if provided, otherwise derive from the request host.
    IMPORTANT: This must EXACTLY match what you entered in Google Cloud Console
    under Authorized redirect URIs.
    """
    return os.environ.get("GOOGLE_REDIRECT_URI") or url_for("oauth2callback", _external=True)

@app.get("/")
def home():
    return "Aperture Receipts: OK. Go to /auth to connect Google."

@app.get("/auth")
def auth():
    # Clear any stale session state from previous attempts
    session.pop("state", None)
    session.pop("code_verifier", None)

    flow = Flow.from_client_config(
        client_config(),
        scopes=SCOPES,
        redirect_uri=redirect_uri(),
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    # Persist state + PKCE verifier so callback can fetch token without "Missing code verifier"
    session["state"] = state
    session["code_verifier"] = getattr(flow, "code_verifier", None)

    return redirect(auth_url)

@app.get("/oauth2callback")
def oauth2callback():
    # Recreate flow with same redirect + state
    flow = Flow.from_client_config(
        client_config(),
        scopes=SCOPES,
        state=session.get("state"),
        redirect_uri=redirect_uri(),
    )

    # Restore PKCE verifier (if this library version uses it)
    cv = session.get("code_verifier")
    if cv:
        setattr(flow, "code_verifier", cv)

    # Exchange code for tokens
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    # For now we just prove Drive access by listing a few files
    service = build("drive", "v3", credentials=creds)
    results = service.files().list(pageSize=5, fields="files(id,name)").execute()
    items = results.get("files", [])

    return {
        "status": "authorized",
        "authed_as_hint": "This lists files for the Google account you used during consent.",
        "sample_files": items,
        "note": "Next step: store refresh token securely + process receipts folder + write to Spent sheet."
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=True)
