"""
AEGIS — Bouclier anti-fraude.  Interface de démonstration (Streamlit).

Le jury lance :  streamlit run app.py

Contrat technique respecté :
  - les appels à `detect_fraud` / `load_transactions` ne sont pas modifiés ;
  - toute la valeur visuelle vit dans `render_interface()`.

Objectif UX : rendre la détection compréhensible par un public NON technique —
on explique en français clair *quoi* est suspect et *pourquoi*.
"""

from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

from fraud_detection import detect_fraud, load_transactions

SAMPLE_CSV = Path(__file__).parent / "data" / "sample_transactions.csv"


# ──────────────────────────────────────────────────────────────────────────
#  Thème visuel (inspiration « Aligno » : noir profond + orange chaud)
# ──────────────────────────────────────────────────────────────────────────
ORANGE = "#F97316"
ORANGE_SOFT = "#FB923C"
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root { --orange:#F97316; --orange2:#FB923C; --ink:#0B0B0F; --panel:#141318; }

html, body, [class*="css"], .stApp { font-family:'Plus Jakarta Sans', sans-serif; }
.stApp {
  background:
    radial-gradient(900px 500px at 80% -10%, rgba(249,115,22,.18), transparent 60%),
    radial-gradient(700px 500px at -10% 110%, rgba(249,115,22,.10), transparent 55%),
    #08080B;
  color:#E9E9EC;
}
#MainMenu, footer, header { visibility:hidden; }
.block-container { padding-top:2.2rem; max-width:1200px; }

/* Hero */
.hero { text-align:center; padding:14px 0 6px; }
.hero .pill {
  display:inline-flex; gap:8px; align-items:center; font-size:.78rem; font-weight:600;
  color:#FFD9BE; background:rgba(249,115,22,.12); border:1px solid rgba(249,115,22,.35);
  padding:6px 14px; border-radius:999px; letter-spacing:.3px;
}
.hero h1 {
  font-size:3.4rem; font-weight:800; margin:.35em 0 .1em; line-height:1.04;
  background:linear-gradient(180deg,#FFF 8%, #F97316 120%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}
.hero p { color:#A6A6AE; font-size:1.02rem; max-width:620px; margin:0 auto; }

/* KPI cards */
.kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:26px 0 8px; }
.kpi {
  background:linear-gradient(180deg, rgba(255,255,255,.045), rgba(255,255,255,.015));
  border:1px solid rgba(255,255,255,.08); border-radius:18px; padding:18px 20px;
  backdrop-filter:blur(6px);
}
.kpi .label { color:#8E8E97; font-size:.8rem; font-weight:600; text-transform:uppercase; letter-spacing:.5px; }
.kpi .value { font-size:2rem; font-weight:800; margin-top:6px; color:#F5F5F7; }
.kpi .sub { font-size:.8rem; color:#7C7C85; margin-top:2px; }
.kpi.alert { border-color:rgba(249,115,22,.45); box-shadow:0 0 0 1px rgba(249,115,22,.15), 0 18px 40px -22px rgba(249,115,22,.7); }
.kpi.alert .value { color:var(--orange2); }

/* Section title */
.sect { font-size:1.25rem; font-weight:700; margin:30px 0 6px; color:#F2F2F4; }
.sect span { color:var(--orange2); }
.sub-muted { color:#8A8A93; font-size:.9rem; margin-bottom:6px; }

/* Alert cards */
.alertcard {
  background:linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.015));
  border:1px solid rgba(255,255,255,.08); border-left:4px solid var(--orange);
  border-radius:16px; padding:16px 18px; margin-bottom:12px;
}
.alertcard.high { border-left-color:#EF4444; }
.alertcard.mid  { border-left-color:#F59E0B; }
.alertcard .top { display:flex; justify-content:space-between; align-items:center; }
.alertcard .tid { font-weight:700; color:#F4F4F6; font-size:1rem; }
.alertcard .reason { color:#D8D8DC; margin:8px 0 10px; font-size:.95rem; }
.alertcard .meta { color:#8A8A93; font-size:.82rem; }
.alertcard .meta b { color:#C9C9CF; font-weight:600; }
.badge { font-size:.72rem; font-weight:700; padding:5px 12px; border-radius:999px; letter-spacing:.3px; }
.badge.high { background:rgba(239,68,68,.16); color:#FCA5A5; border:1px solid rgba(239,68,68,.4); }
.badge.mid  { background:rgba(245,158,11,.16); color:#FCD34D; border:1px solid rgba(245,158,11,.4); }
.badge.safe { background:rgba(16,185,129,.14); color:#6EE7B7; border:1px solid rgba(16,185,129,.35); }

/* Risk meter */
.meter { height:8px; border-radius:999px; background:rgba(255,255,255,.08); overflow:hidden; margin-top:4px; }
.meter > div { height:100%; border-radius:999px; background:linear-gradient(90deg,#F59E0B,#EF4444); }

/* explain rules */
.rule { background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.07);
        border-radius:14px; padding:14px 16px; margin-bottom:10px; }
.rule b { color:var(--orange2); }
.rule span { color:#A6A6AE; font-size:.9rem; }

.empty { text-align:center; color:#6EE7B7; background:rgba(16,185,129,.08);
         border:1px solid rgba(16,185,129,.25); border-radius:16px; padding:26px; }
</style>
"""


def _risk_level(score: float, suspicious: bool):
    if not suspicious:
        return "safe", "Sain", "#10B981"
    if score >= 0.8:
        return "high", "Risque élevé", "#EF4444"
    return "mid", "À vérifier", "#F59E0B"


def _fmt_amount(tx: dict) -> str:
    amt = tx.get("amount")
    cur = tx.get("currency") or ""
    if amt is None:
        return "—"
    return f"{amt:,.2f} {cur}".replace(",", " ").strip()


# ──────────────────────────────────────────────────────────────────────────
#  Interface principale (vue jury / public)
# ──────────────────────────────────────────────────────────────────────────
def render_interface(transactions: list[dict], results: list[dict]) -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)

    by_id = {t.get("transaction_id"): t for t in transactions}
    n = len(results)
    alerts = [r for r in results if r.get("is_suspicious")]
    n_alert = len(alerts)
    rate = (n_alert / n * 100) if n else 0
    clients = {t.get("user_id") for t in transactions if t.get("user_id")}

    amount_at_risk = 0.0
    for r in alerts:
        amt = by_id.get(r["transaction_id"], {}).get("amount")
        if isinstance(amt, (int, float)) and amt > 0:
            amount_at_risk += amt

    # — Hero —
    st.markdown(
        """
        <div class="hero">
          <span class="pill">🛡️ Détection de fraude pilotée par l'IA</span>
          <h1>AEGIS</h1>
          <p>Chaque transaction est analysée puis expliquée en langage clair :
          nous signalons l'anormal sans gêner les clients honnêtes.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # — KPI —
    st.markdown(
        f"""
        <div class="kpis">
          <div class="kpi"><div class="label">Transactions</div>
            <div class="value">{n}</div><div class="sub">analysées</div></div>
          <div class="kpi alert"><div class="label">Alertes</div>
            <div class="value">{n_alert}</div><div class="sub">à examiner</div></div>
          <div class="kpi"><div class="label">Taux d'alerte</div>
            <div class="value">{rate:.0f}%</div><div class="sub">des transactions</div></div>
          <div class="kpi"><div class="label">Montant à risque</div>
            <div class="value">{amount_at_risk:,.0f}</div><div class="sub">{len(clients)} client(s) suivis</div></div>
        </div>
        """.replace(",", " "),
        unsafe_allow_html=True,
    )

    # — Graphiques : répartition + motifs —
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.markdown('<div class="sect">Répartition du <span>risque</span></div>', unsafe_allow_html=True)
        high = sum(1 for r in alerts if r["fraud_score"] >= 0.8)
        mid = n_alert - high
        safe = n - n_alert
        dist = pd.DataFrame(
            {"Niveau": ["Risque élevé", "À vérifier", "Sain"], "Nombre": [high, mid, safe]}
        ).set_index("Niveau")
        st.bar_chart(dist, color=ORANGE, height=240)

    with c2:
        st.markdown('<div class="sect">Principaux <span>motifs</span> d\'alerte</div>', unsafe_allow_html=True)
        motifs = Counter(r["reason"].split(" · ")[0] for r in alerts)
        if motifs:
            mdf = (pd.DataFrame(motifs.most_common(), columns=["Motif", "Alertes"])
                   .set_index("Motif"))
            st.bar_chart(mdf, color=ORANGE_SOFT, height=240, horizontal=True)
        else:
            st.markdown('<div class="empty">Aucune alerte — flux conforme ✅</div>', unsafe_allow_html=True)

    # — Filtres —
    st.markdown('<div class="sect">Journal des <span>alertes</span></div>', unsafe_allow_html=True)
    f1, f2, f3 = st.columns([1.2, 1, 1])
    with f1:
        only_alerts = st.toggle("Afficher uniquement les transactions suspectes", value=True)
    with f2:
        countries = sorted({t.get("country") or "—" for t in transactions})
        country_sel = st.selectbox("Pays", ["Tous"] + countries)
    with f3:
        client_sel = st.selectbox("Client", ["Tous"] + sorted(clients))

    # — Cartes d'alerte explicables —
    shown = 0
    for r in results:
        tx = by_id.get(r["transaction_id"], {})
        if only_alerts and not r["is_suspicious"]:
            continue
        if country_sel != "Tous" and (tx.get("country") or "—") != country_sel:
            continue
        if client_sel != "Tous" and tx.get("user_id") != client_sel:
            continue
        shown += 1
        lvl, label, _ = _risk_level(r["fraud_score"], r["is_suspicious"])
        pct = int(round(r["fraud_score"] * 100))
        st.markdown(
            f"""
            <div class="alertcard {lvl}">
              <div class="top">
                <span class="tid">#{r['transaction_id']}</span>
                <span class="badge {lvl}">{label} · {pct}%</span>
              </div>
              <div class="reason">{r['reason']}</div>
              <div class="meta">
                <b>Client</b> {tx.get('user_id') or '—'} &nbsp;·&nbsp;
                <b>Montant</b> {_fmt_amount(tx)} &nbsp;·&nbsp;
                <b>Commerçant</b> {tx.get('merchant') or '—'} &nbsp;·&nbsp;
                <b>Pays</b> {tx.get('country') or '—'} &nbsp;·&nbsp;
                <b>Date</b> {tx.get('timestamp') or '—'}
              </div>
              <div class="meter"><div style="width:{pct}%"></div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if shown == 0:
        st.markdown(
            '<div class="empty">Aucune transaction suspecte selon ces filtres — '
            'tout est conforme ✅</div>', unsafe_allow_html=True)

    # — Pédagogie : comment AEGIS décide —
    st.markdown('<div class="sect">Comment AEGIS <span>décide</span> ?</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-muted">Des règles métier explicables, pas une boîte noire.</div>',
                unsafe_allow_html=True)
    rules = [
        ("Montant aberrant", "montant nul, négatif ou bien plus élevé que l'habitude du client."),
        ("Voyage impossible", "deux pays trop distants en trop peu de temps (calcul de distance / vitesse)."),
        ("Rafale de transactions", "trop d'opérations en quelques minutes — typique du test de carte volée."),
        ("Champs manquants", "informations obligatoires absentes (pays, devise, client)."),
        ("Doublon", "même paiement répété à l'identique (possible double débit)."),
        ("Faux positif évité", "un achat inhabituel mais cohérent avec le profil n'est PAS signalé."),
    ]
    rc1, rc2 = st.columns(2)
    for i, (title, desc) in enumerate(rules):
        with (rc1 if i % 2 == 0 else rc2):
            st.markdown(f'<div class="rule"><b>{title}</b><br><span>{desc}</span></div>',
                        unsafe_allow_html=True)

    # — Tableau complet (export / inspection) —
    with st.expander("Voir le détail complet (tableau)"):
        rows = []
        for r in results:
            tx = by_id.get(r["transaction_id"], {})
            rows.append({
                "ID": r["transaction_id"],
                "Suspecte": "🔴" if r["is_suspicious"] else "🟢",
                "Score": r["fraud_score"],
                "Client": tx.get("user_id"),
                "Montant": tx.get("amount"),
                "Devise": tx.get("currency"),
                "Pays": tx.get("country"),
                "Motif": r["reason"],
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, width="stretch", hide_index=True)
        st.download_button(
            "⬇️ Exporter les résultats (CSV)",
            df.to_csv(index=False).encode("utf-8"),
            file_name="resultats_fraude.csv", mime="text/csv",
        )


# ──────────────────────────────────────────────────────────────────────────
#  Bootstrap Streamlit
# ──────────────────────────────────────────────────────────────────────────
def main() -> None:
    st.set_page_config(
        page_title="AEGIS — Détection de fraude · INTELO2026",
        page_icon="🛡️",
        layout="wide",
    )
    st.markdown(THEME_CSS, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### 🛡️ AEGIS")
        st.caption("Hackathon INTELO2026 — détection de fraude financière")
        st.divider()
        st.markdown("**Source des données**")
        use_sample = st.toggle("Jeu d'exemple fourni", value=True)
        transactions: list[dict] = []

        if use_sample:
            transactions = load_transactions(str(SAMPLE_CSV))
            st.success(f"{len(transactions)} transactions chargées")
        else:
            uploaded = st.file_uploader("Importer un CSV", type=["csv"])
            if uploaded:
                tmp = Path(".streamlit_upload.csv")
                tmp.write_bytes(uploaded.getvalue())
                transactions = load_transactions(str(tmp))
                tmp.unlink(missing_ok=True)
                st.success(f"{len(transactions)} transactions importées")

        st.divider()
        st.caption("Format attendu : transaction_id, timestamp, user_id, amount, "
                   "currency, merchant, country, card_present.")

    if not transactions:
        st.markdown(THEME_CSS, unsafe_allow_html=True)
        st.markdown(
            """
            <div class="hero"><h1>AEGIS</h1>
            <p>Importez un fichier CSV ou activez le jeu d'exemple dans la barre
            latérale, puis lancez l'analyse.</p></div>
            """, unsafe_allow_html=True)
        return

    # ── Contrat technique : ne pas modifier cet appel ──
    try:
        results = detect_fraud(transactions)
    except NotImplementedError:
        st.error("Implémentez d'abord `detect_fraud` dans `fraud_detection.py`.")
        return
    except Exception as exc:
        st.error(f"Erreur pendant l'analyse : {exc}")
        return

    render_interface(transactions, results)


if __name__ == "__main__":
    main()
