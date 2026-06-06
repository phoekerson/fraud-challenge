"""
AEGIS API — service REST de détection de fraude + authentification forte (MFA).

Permet à une entreprise de paiement de :
  1. envoyer des transactions (JSON ou CSV) et récupérer les verdicts en JSON ;
  2. récupérer les transactions à vérifier (voie « MFA ») ;
  3. enrôler un client dans une app d'authentification (Google Authenticator /
     Microsoft Authenticator) et vérifier son code TOTP pour lever le doute.

Lancer :  uvicorn api:app --reload
Doc interactive (Swagger) :  http://localhost:8000/docs
"""

import json
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db
import mfa
from fraud_detection import detect_fraud, load_transactions

DATA_DIR = Path(__file__).parent / "data"
RESULTS_FILE = DATA_DIR / "last_results.json"
MFA_STATE_FILE = DATA_DIR / "mfa_state.json"
ISSUER = "AEGIS"

app = FastAPI(
    title="AEGIS — API de détection de fraude & MFA",
    description="Détection de fraude explicable + authentification TOTP "
                "(compatible Google Authenticator / Microsoft Authenticator).",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────
#  Modèles d'échange (JSON)
# ──────────────────────────────────────────────────────────────────────────
class Transaction(BaseModel):
    transaction_id: Optional[str] = None
    timestamp: Optional[str] = None
    user_id: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    merchant: Optional[str] = None
    country: Optional[str] = None
    card_present: Optional[bool] = None


class AnalyzeRequest(BaseModel):
    transactions: list[Transaction]


class Verdict(BaseModel):
    transaction_id: Optional[str]
    fraud_score: float
    is_suspicious: bool
    reason: str
    recommended_action: str
    mfa_required: bool


class AnalyzeResponse(BaseModel):
    summary: dict
    results: list[Verdict]


class EnrollRequest(BaseModel):
    user_id: str = Field(..., examples=["U1"])


class EnrollResponse(BaseModel):
    user_id: str
    secret: str
    otpauth_uri: str
    qr_data_uri: Optional[str] = None
    instructions: str


class VerifyRequest(BaseModel):
    user_id: str
    code: str = Field(..., examples=["123456"])
    transaction_id: Optional[str] = None


class VerifyResponse(BaseModel):
    verified: bool
    transaction_id: Optional[str] = None
    action_after: Optional[str] = None
    detail: str


class DatabaseRequest(BaseModel):
    database_url: Optional[str] = Field(
        None, description="URL SQLAlchemy de la base de la banque. "
                          "Vide = base de démonstration SQLite.",
        examples=["postgresql+psycopg://user:pwd@host/db"])
    table: str = "transactions"
    limit: Optional[int] = None


# ──────────────────────────────────────────────────────────────────────────
#  Persistance JSON (état MFA + derniers résultats)
# ──────────────────────────────────────────────────────────────────────────
def _load_state() -> dict:
    if MFA_STATE_FILE.exists():
        try:
            return json.loads(MFA_STATE_FILE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {"secrets": {}, "verified": []}


def _save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MFA_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                              encoding="utf-8")


def _save_results(results: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                            encoding="utf-8")


def _summary(results: list[dict]) -> dict:
    actions = [r.get("recommended_action", "approuver") for r in results]
    return {
        "total": len(results),
        "approuver": actions.count("approuver"),
        "verifier": actions.count("verifier"),
        "suspendre": actions.count("suspendre"),
        "alertes": sum(1 for r in results if r.get("is_suspicious")),
    }


# ──────────────────────────────────────────────────────────────────────────
#  Détection
# ──────────────────────────────────────────────────────────────────────────
@app.get("/", tags=["info"])
def root():
    return {
        "service": "AEGIS",
        "docs": "/docs",
        "endpoints": ["/analyze", "/analyze/csv", "/analyze/database",
                      "/bank/transactions", "/results", "/results/pending-mfa",
                      "/mfa/enroll", "/mfa/verify"],
    }


@app.get("/health", tags=["info"])
def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse, tags=["détection"])
def analyze(req: AnalyzeRequest):
    """Analyse une liste de transactions (JSON) et renvoie les verdicts."""
    txs = [t.model_dump() for t in req.transactions]
    results = detect_fraud(txs)
    _save_results(results)
    return {"summary": _summary(results), "results": results}


@app.post("/analyze/csv", response_model=AnalyzeResponse, tags=["détection"])
async def analyze_csv(file: UploadFile = File(...)):
    """Analyse un fichier CSV (mêmes colonnes que le format officiel)."""
    content = await file.read()
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        txs = load_transactions(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    results = detect_fraud(txs)
    _save_results(results)
    return {"summary": _summary(results), "results": results}


@app.get("/bank/transactions", tags=["banque"])
def bank_transactions(table: str = "transactions", limit: Optional[int] = None,
                      database_url: Optional[str] = None):
    """Lit les transactions directement dans la base de la banque (sans analyse)."""
    try:
        txs = db.load_transactions_from_db(database_url, table=table, limit=limit)
    except Exception as exc:
        raise HTTPException(502, f"Connexion base impossible : {exc}")
    return {"count": len(txs), "source": database_url or db.default_database_url(),
            "transactions": txs}


@app.post("/analyze/database", response_model=AnalyzeResponse, tags=["banque"])
def analyze_database(req: DatabaseRequest = DatabaseRequest()):
    """Lit la base de la banque puis analyse toutes les transactions."""
    try:
        txs = db.load_transactions_from_db(req.database_url, table=req.table, limit=req.limit)
    except Exception as exc:
        raise HTTPException(502, f"Connexion base impossible : {exc}")
    results = detect_fraud(txs)
    _save_results(results)
    return {"summary": _summary(results), "results": results}


@app.get("/results", tags=["détection"])
def get_results():
    """Renvoie les derniers résultats analysés (fichier JSON)."""
    if not RESULTS_FILE.exists():
        raise HTTPException(404, "Aucun résultat. Appelez d'abord /analyze.")
    return json.loads(RESULTS_FILE.read_text(encoding="utf-8"))


@app.get("/results/pending-mfa", tags=["détection"])
def pending_mfa():
    """Transactions en attente de confirmation MFA (voies « vérifier » et « suspendre »)."""
    if not RESULTS_FILE.exists():
        raise HTTPException(404, "Aucun résultat. Appelez d'abord /analyze.")
    results = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    state = _load_state()
    verified = set(state.get("verified", []))
    pending = [r for r in results
               if r.get("mfa_required")
               and r.get("transaction_id") not in verified]
    return {"count": len(pending), "transactions": pending}


# ──────────────────────────────────────────────────────────────────────────
#  MFA — Google Authenticator / Microsoft Authenticator (TOTP)
# ──────────────────────────────────────────────────────────────────────────
@app.post("/mfa/enroll", response_model=EnrollResponse, tags=["MFA"])
def enroll(req: EnrollRequest):
    """Enrôle un client : génère un secret TOTP et l'URI à scanner dans l'app."""
    state = _load_state()
    secret = state["secrets"].get(req.user_id) or mfa.generate_secret()
    state["secrets"][req.user_id] = secret
    _save_state(state)

    uri = mfa.provisioning_uri(secret, account=req.user_id, issuer=ISSUER)
    return EnrollResponse(
        user_id=req.user_id,
        secret=secret,
        otpauth_uri=uri,
        qr_data_uri=mfa.qr_data_uri(uri),
        instructions="Ouvrez Google Authenticator ou Microsoft Authenticator, "
                     "« Ajouter un compte » → scannez le QR (otpauth_uri) ou "
                     "saisissez le secret manuellement.",
    )


@app.post("/mfa/verify", response_model=VerifyResponse, tags=["MFA"])
def verify(req: VerifyRequest):
    """Vérifie le code TOTP du client ; si valide, lève l'alerte MFA de la transaction."""
    state = _load_state()
    secret = state["secrets"].get(req.user_id)
    if not secret:
        raise HTTPException(404, f"Client {req.user_id} non enrôlé. Appelez /mfa/enroll.")

    if not mfa.verify(secret, req.code):
        return VerifyResponse(verified=False, transaction_id=req.transaction_id,
                              detail="Code invalide ou expiré.")

    action_after = None
    if req.transaction_id:
        if req.transaction_id not in state["verified"]:
            state["verified"].append(req.transaction_id)
            _save_state(state)
        action_after = "approuver"  # MFA réussie -> transaction validée

    return VerifyResponse(
        verified=True,
        transaction_id=req.transaction_id,
        action_after=action_after,
        detail="Identité confirmée — transaction validée (faux positif évité)."
        if req.transaction_id else "Identité confirmée.",
    )
