"""
Défi — Détection de fraude financière.

Moteur de détection explicable, basé sur des règles métier robustes
(velocity, voyage impossible, anomalie de montant vs historique client,
doublons, champs invalides). Chaque transaction reçoit un score de risque
0–1, un verdict et une justification lisible.

`load_transactions` est FOURNIE (lecture CSV) — ne pas la modifier.
Seule `detect_fraud` est notée par la CI.
"""

import csv
import math
from datetime import datetime, timezone


# ──────────────────────────────────────────────────────────────────────────
#  Lecture CSV (fourni — ne pas modifier)
# ──────────────────────────────────────────────────────────────────────────
def load_transactions(path):
    """Lit un fichier CSV de transactions et renvoie une liste de dicts."""
    transactions = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append(_clean_row(row))
    return transactions


def _clean_row(row):
    def get(key):
        v = row.get(key)
        return v.strip() if isinstance(v, str) and v.strip() != "" else None

    amount_raw = get("amount")
    try:
        amount = float(amount_raw) if amount_raw is not None else None
    except ValueError:
        amount = None

    card_raw = get("card_present")
    if card_raw is None:
        card_present = None
    else:
        card_present = card_raw.lower() in ("true", "1", "yes", "oui")

    return {
        "transaction_id": get("transaction_id"),
        "timestamp": get("timestamp"),
        "user_id": get("user_id"),
        "amount": amount,
        "currency": get("currency"),
        "merchant": get("merchant"),
        "country": get("country"),
        "card_present": card_present,
    }


# ──────────────────────────────────────────────────────────────────────────
#  Paramètres du moteur (seuils ajustables)
# ──────────────────────────────────────────────────────────────────────────
SUSPICION_THRESHOLD = 0.5          # score >= seuil  ->  is_suspicious = True
BLOCK_THRESHOLD = 0.8              # >= seuil -> blocage ; entre les deux -> MFA
REQUIRED_FIELDS = ("user_id", "currency", "country")

# Anomalie de montant vs historique du client
MIN_HISTORY = 3                    # nb mini d'historique pour juger un montant
AMOUNT_RATIO = 5.0                 # montant >= ratio x médiane du client
AMOUNT_MAX_FACTOR = 2.0            # ET >= facteur x plus gros montant connu
AMOUNT_ABS_GAP = 100.0             # ET écart absolu mini (évite le bruit)

# Voyage impossible : vitesse implicite max plausible (avion + escales)
MAX_PLAUSIBLE_KMH = 1000.0
FALLBACK_GEO_HOURS = 2.0           # pays inconnus : changement de pays < 2 h

# Velocity / rafale
BURST_COUNT = 5                    # nb de transactions...
BURST_WINDOW_MIN = 5              # ...dans cette fenêtre (minutes)
MERCHANT_FANOUT = 5                # nb de commerçants distincts...
MERCHANT_WINDOW_MIN = 60           # ...dans cette fenêtre (minutes) -> test carte

# Centroïdes (lat, lon) des pays courants — pour estimer une distance plausible.
COUNTRY_CENTROIDS = {
    "FR": (46.6, 2.2), "DE": (51.2, 10.4), "ES": (40.0, -4.0), "IT": (42.8, 12.6),
    "GB": (54.0, -2.0), "UK": (54.0, -2.0), "BE": (50.6, 4.6), "NL": (52.2, 5.3),
    "CH": (46.8, 8.2), "PT": (39.6, -8.0), "IE": (53.2, -8.0), "AT": (47.6, 14.1),
    "SE": (62.0, 15.0), "NO": (61.0, 8.5), "FI": (64.0, 26.0), "DK": (56.0, 9.5),
    "PL": (52.0, 19.0), "RU": (61.5, 105.0), "TR": (39.0, 35.0), "GR": (39.0, 22.0),
    "US": (39.8, -98.6), "CA": (56.1, -106.3), "MX": (23.6, -102.5),
    "BR": (-14.2, -51.9), "AR": (-38.4, -63.6), "CL": (-35.7, -71.5),
    "CN": (35.9, 104.2), "JP": (36.2, 138.3), "KR": (36.5, 127.8),
    "IN": (20.6, 78.9), "ID": (-0.8, 113.9), "TH": (15.9, 101.0),
    "SG": (1.35, 103.8), "MY": (4.2, 101.9), "PH": (12.9, 121.8),
    "AE": (23.4, 53.8), "SA": (23.9, 45.1), "QA": (25.3, 51.2), "IL": (31.0, 34.9),
    "ZA": (-30.6, 22.9), "EG": (26.8, 30.8), "NG": (9.1, 8.7), "KE": (-0.0, 37.9),
    "MA": (31.8, -7.1), "DZ": (28.0, 1.7), "TN": (33.9, 9.6), "CI": (7.5, -5.5),
    "SN": (14.5, -14.5), "ML": (17.6, -4.0), "BF": (12.2, -1.6), "BJ": (9.3, 2.3),
    "TG": (8.6, 0.8), "CM": (3.8, 11.5), "GH": (7.9, -1.0),
    "AU": (-25.3, 133.8), "NZ": (-40.9, 174.9),
}


# ──────────────────────────────────────────────────────────────────────────
#  Utilitaires robustes (ne plantent jamais)
# ──────────────────────────────────────────────────────────────────────────
def _parse_timestamp(value):
    """ISO 8601 -> datetime aware (UTC). Renvoie None si absent/illisible."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except (ValueError, TypeError):
        # Derniers recours : quelques formats fréquents
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text.replace("+00:00", ""), fmt)
                break
            except ValueError:
                dt = None
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _haversine_km(a, b):
    """Distance en km entre deux (lat, lon)."""
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def _median(values):
    s = sorted(values)
    n = len(s)
    if n == 0:
        return None
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _is_impossible_hop(country_a, country_b, hours):
    """True si passer de country_a à country_b en `hours` est physiquement irréaliste."""
    if country_a == country_b:
        return False
    if hours <= 0:
        return True  # deux pays différents au même instant -> impossible
    ca = COUNTRY_CENTROIDS.get((country_a or "").upper())
    cb = COUNTRY_CENTROIDS.get((country_b or "").upper())
    if ca and cb:
        dist = _haversine_km(ca, cb)
        if dist < 100:          # pays voisins/proches : on ne juge pas par la vitesse
            return False
        return (dist / hours) > MAX_PLAUSIBLE_KMH
    # Pays inconnu(s) : repli prudent sur le temps écoulé
    return hours < FALLBACK_GEO_HOURS


# ──────────────────────────────────────────────────────────────────────────
#  Cœur : analyse et scoring
# ──────────────────────────────────────────────────────────────────────────
def detect_fraud(transactions):
    """Analyse une liste de transactions et renvoie un verdict pour chacune.

    Retour : list[dict] avec transaction_id, fraud_score (0-1),
    is_suspicious (bool), reason (str) — un résultat par transaction, même ordre.
    """
    if not isinstance(transactions, list):
        transactions = list(transactions or [])

    # 1) Pré-calculs par client (historique, chronologie, doublons)
    profiles = _build_profiles(transactions)
    geo_flagged = _flag_impossible_travel(profiles)
    burst_flagged, fanout_flagged = _flag_velocity(profiles)
    duplicate_flagged = _flag_duplicates(transactions)

    # 2) Verdict transaction par transaction
    results = []
    for idx, tx in enumerate(transactions):
        try:
            results.append(
                _score_transaction(
                    tx, idx, profiles,
                    geo_flagged, burst_flagged, fanout_flagged, duplicate_flagged,
                )
            )
        except Exception:  # robustesse absolue : jamais de crash
            results.append({
                "transaction_id": (tx or {}).get("transaction_id"),
                "fraud_score": 0.0,
                "is_suspicious": False,
                "reason": "Analyse impossible — transaction conservée par défaut",
                "recommended_action": "approuver",
                "mfa_required": False,
            })
    return results


def _build_profiles(transactions):
    """Regroupe par client : montants valides + chronologie (idx, time, country, ...)."""
    profiles = {}
    for idx, tx in enumerate(transactions):
        if not isinstance(tx, dict):
            continue
        user = tx.get("user_id")
        prof = profiles.setdefault(user, {"amounts": [], "timeline": []})
        amount = tx.get("amount")
        if isinstance(amount, (int, float)) and amount > 0:
            prof["amounts"].append(float(amount))
        prof["timeline"].append({
            "idx": idx,
            "time": _parse_timestamp(tx.get("timestamp")),
            "country": tx.get("country"),
            "merchant": tx.get("merchant"),
            "amount": amount,
        })
    return profiles


def _flag_impossible_travel(profiles):
    """Renvoie l'ensemble des index de transactions en incohérence géographique."""
    flagged = set()
    for prof in profiles.values():
        events = [e for e in prof["timeline"] if e["time"] and e["country"]]
        events.sort(key=lambda e: e["time"])
        for prev, cur in zip(events, events[1:]):
            hours = (cur["time"] - prev["time"]).total_seconds() / 3600.0
            if _is_impossible_hop(prev["country"], cur["country"], hours):
                flagged.add(prev["idx"])
                flagged.add(cur["idx"])
    return flagged


def _flag_velocity(profiles):
    """Détecte les rafales (burst) et l'éclatement sur de nombreux commerçants."""
    burst, fanout = set(), set()
    for prof in profiles.values():
        events = [e for e in prof["timeline"] if e["time"]]
        events.sort(key=lambda e: e["time"])
        n = len(events)
        for i in range(n):
            # Rafale : >= BURST_COUNT transactions dans une fenêtre glissante
            window = [e for e in events
                      if 0 <= (events[i]["time"] - e["time"]).total_seconds() <= BURST_WINDOW_MIN * 60]
            if len(window) >= BURST_COUNT:
                for e in window:
                    burst.add(e["idx"])
            # Test de carte : beaucoup de commerçants distincts en peu de temps
            near = [e for e in events
                    if abs((events[i]["time"] - e["time"]).total_seconds()) <= MERCHANT_WINDOW_MIN * 60]
            merchants = {e["merchant"] for e in near if e["merchant"]}
            if len(merchants) >= MERCHANT_FANOUT:
                for e in near:
                    fanout.add(e["idx"])
    return burst, fanout


def _flag_duplicates(transactions):
    """Doublons exacts (même client, montant, commerçant, horodatage) : extras signalés."""
    seen = {}
    flagged = set()
    for idx, tx in enumerate(transactions):
        if not isinstance(tx, dict):
            continue
        amount = tx.get("amount")
        if amount is None:
            continue
        key = (tx.get("user_id"), amount, tx.get("merchant"), tx.get("timestamp"))
        if key in seen:
            flagged.add(idx)
        else:
            seen[key] = idx
    return flagged


def _amount_anomaly(tx, profile):
    """Montant anormalement élevé vs l'historique du client. -> (score, reason) | None."""
    amount = tx.get("amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        return None
    others = list(profile["amounts"])
    others.remove(float(amount)) if float(amount) in others else None
    if len(others) < MIN_HISTORY:
        return None
    med = _median(others)
    mx = max(others)
    if med and med > 0 and amount >= AMOUNT_RATIO * med \
            and amount >= AMOUNT_MAX_FACTOR * mx and (amount - med) >= AMOUNT_ABS_GAP:
        ratio = amount / med
        score = max(0.55, min(0.95, 0.55 + 0.04 * (ratio - AMOUNT_RATIO)))
        return score, "Montant très supérieur à l'habitude du client"
    return None


def _score_transaction(tx, idx, profiles, geo, burst, fanout, duplicates):
    if not isinstance(tx, dict):
        return {"transaction_id": None, "fraud_score": 0.0,
                "is_suspicious": False, "reason": "Transaction illisible",
                "recommended_action": "approuver", "mfa_required": False}

    tid = tx.get("user_id")
    profile = profiles.get(tid, {"amounts": [], "timeline": []})
    amount = tx.get("amount")
    signals = []  # (score, reason)

    # — Niveau 1 : anomalies évidentes —
    if amount is None:
        signals.append((0.85, "Montant manquant"))
    elif amount <= 0:
        signals.append((0.9, "Montant nul ou négatif"))

    missing = [f for f in REQUIRED_FIELDS if not tx.get(f)]
    if missing:
        signals.append((0.85, "Champs obligatoires manquants: " + ", ".join(missing)))

    # — Niveau 2 : logique métier —
    anomaly = _amount_anomaly(tx, profile)
    if anomaly:
        signals.append(anomaly)

    if idx in geo:
        signals.append((0.88, "Deux pays différents en trop peu de temps"))

    if idx in burst:
        signals.append((0.75, "Rafale de transactions en très peu de temps"))

    if idx in fanout:
        signals.append((0.7, "Nombreux commerçants en peu de temps (test de carte)"))

    if idx in duplicates:
        signals.append((0.6, "Transaction en double (possible double débit)"))

    # — Niveau 3 : signal contextuel faible (n'alerte jamais seul) —
    ctx = _context_signal(tx, profile)
    if ctx:
        signals.append(ctx)

    return _combine(tx, signals)


def _context_signal(tx, profile):
    """Indice secondaire : achat nocturne, sans carte, nettement au-dessus de la normale."""
    amount = tx.get("amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        return None
    dt = _parse_timestamp(tx.get("timestamp"))
    if dt is None:
        return None
    others = [a for a in profile["amounts"] if a != float(amount)]
    med = _median(others)
    night = dt.hour <= 5
    elevated = med and med > 0 and amount >= 2.5 * med
    if night and tx.get("card_present") is False and elevated:
        return 0.35, "Achat nocturne sans carte, supérieur à l'habitude"
    return None


def _decide_action(score, suspicious):
    """Voie de décision (friction dynamique / step-up auth).

    - approuver : risque faible, on laisse passer.
    - verifier  : risque modéré -> authentification (MFA) pour lever le doute
                  sans gêner un client honnête.
    - suspendre : risque élevé -> transaction suspendue, libérée seulement après
                  confirmation forte du client (Google / Microsoft Authenticator).
    Les deux voies à risque exigent une confirmation MFA.
    """
    if not suspicious:
        return "approuver", False
    if score >= BLOCK_THRESHOLD:
        return "suspendre", True
    return "verifier", True


def _combine(tx, signals):
    """Fusionne les signaux : base = plus fort, léger renfort si plusieurs concordent."""
    tid = tx.get("transaction_id")
    if not signals:
        action, mfa = _decide_action(0.0, False)
        return {"transaction_id": tid, "fraud_score": 0.0, "is_suspicious": False,
                "reason": "Transaction conforme au profil du client",
                "recommended_action": action, "mfa_required": mfa}

    signals.sort(key=lambda s: s[0], reverse=True)
    base, reason = signals[0]
    corroborating = [s for s in signals[1:] if s[0] >= 0.4]
    score = min(1.0, base + min(0.09, 0.03 * len(corroborating)))

    if corroborating and corroborating[0][1] != reason:
        reason = f"{reason} · {corroborating[0][1]}"

    suspicious = bool(score >= SUSPICION_THRESHOLD)
    action, mfa = _decide_action(score, suspicious)

    return {
        "transaction_id": tid,
        "fraud_score": round(float(score), 2),
        "is_suspicious": suspicious,
        "reason": reason,
        "recommended_action": action,
        "mfa_required": mfa,
    }
