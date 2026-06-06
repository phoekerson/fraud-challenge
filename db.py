"""
Connecteur base de données — lit les transactions directement d'une banque.

- Par défaut : une base SQLite de démonstration (`data/bank_demo.db`), créée
  automatiquement à partir de `data/demo_transactions.csv` (aucune config requise).
- En production : pointez `DATABASE_URL` vers la base de la banque
  (PostgreSQL/MySQL/… via SQLAlchemy), ex. une instance Neon :
      export DATABASE_URL="postgresql+psycopg://user:pwd@host/db"

Les lignes sont normalisées au même format que `load_transactions`
(types propres, valeurs vides -> None) pour être analysées par `detect_fraud`.
"""

import csv
import os
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DEMO_DB = DATA_DIR / "bank_demo.db"
DEMO_CSV = DATA_DIR / "demo_transactions.csv"
SAMPLE_CSV = DATA_DIR / "sample_transactions.csv"

COLUMNS = ["transaction_id", "timestamp", "user_id", "amount",
           "currency", "merchant", "country", "card_present"]


def default_database_url() -> str:
    """URL par défaut : variable d'env DATABASE_URL, sinon la base démo SQLite."""
    return os.environ.get("DATABASE_URL") or f"sqlite:///{DEMO_DB.as_posix()}"


def _norm_str(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s != "" else None


def _norm_amount(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _norm_card(v):
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    return str(v).strip().lower() in ("true", "1", "yes", "oui", "t")


def _normalize(record: dict) -> dict:
    """Normalise un enregistrement (peu importe l'origine) au format transaction."""
    return {
        "transaction_id": _norm_str(record.get("transaction_id")),
        "timestamp": _norm_str(record.get("timestamp")),
        "user_id": _norm_str(record.get("user_id")),
        "amount": _norm_amount(record.get("amount")),
        "currency": _norm_str(record.get("currency")),
        "merchant": _norm_str(record.get("merchant")),
        "country": _norm_str(record.get("country")),
        "card_present": _norm_card(record.get("card_present")),
    }


def ensure_demo_db(table: str = "transactions") -> None:
    """Crée et alimente la base SQLite de démonstration si elle n'existe pas."""
    if DEMO_DB.exists():
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    source = DEMO_CSV if DEMO_CSV.exists() else SAMPLE_CSV
    conn = sqlite3.connect(DEMO_DB)
    try:
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {table} ("
            "transaction_id TEXT, timestamp TEXT, user_id TEXT, amount REAL, "
            "currency TEXT, merchant TEXT, country TEXT, card_present INTEGER)"
        )
        with open(source, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                tx = _normalize(row)
                conn.execute(
                    f"INSERT INTO {table} VALUES (?,?,?,?,?,?,?,?)",
                    (tx["transaction_id"], tx["timestamp"], tx["user_id"], tx["amount"],
                     tx["currency"], tx["merchant"], tx["country"],
                     None if tx["card_present"] is None else int(tx["card_present"])),
                )
        conn.commit()
    finally:
        conn.close()


def load_transactions_from_db(database_url: str | None = None,
                              table: str = "transactions",
                              limit: int | None = None) -> list[dict]:
    """Lit les transactions depuis la base et renvoie une liste de dicts normalisés."""
    url = database_url or default_database_url()
    sql = f"SELECT {', '.join(COLUMNS)} FROM {table}"
    if limit:
        sql += f" LIMIT {int(limit)}"

    if url.startswith("sqlite"):
        path = url.replace("sqlite:///", "").replace("sqlite://", "")
        if Path(path).resolve() == DEMO_DB.resolve():
            ensure_demo_db(table)
        conn = sqlite3.connect(path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql).fetchall()
            return [_normalize(dict(r)) for r in rows]
        finally:
            conn.close()

    # Autres moteurs (PostgreSQL, MySQL…) via SQLAlchemy
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).mappings().all()
    return [_normalize(dict(r)) for r in rows]
