"""
Interface Streamlit — À CRÉER PAR VOUS pour le jury.

Le jury lancera :  streamlit run app.py

Règles :
  - Ne modifiez pas l'appel à detect_fraud / load_transactions (contrat technique).
  - Personnalisez render_interface() : clarté, intuitivité, compréhension pour un public non technique.
  - L'interface n'est PAS notée par la CI ; elle sert au jury pour repêcher et comparer les candidats.
"""

from pathlib import Path

import streamlit as st

from fraud_detection import detect_fraud, load_transactions

SAMPLE_CSV = Path(__file__).parent / "data" / "sample_transactions.csv"


def render_interface(transactions: list[dict], results: list[dict]) -> None:
    """
    ══════════════════════════════════════════════════════════════════
    À COMPLÉTER — votre interface intuitive pour le jury / le public.
    ══════════════════════════════════════════════════════════════════

    Idées (libres) :
      - titres et textes en langage simple (« transaction suspecte », « client à risque ») ;
      - cartes / indicateurs visuels (nombre d'alertes, niveau de risque) ;
      - tableau ou liste filtrable (uniquement les suspectes, par client, par pays…) ;
      - codes couleur, icônes, graphiques ;
      - zone « comment l'IA / vos règles décident » pour expliquer une alerte.

    Le jury évalue : clarté, utilité, intuitivité — pas le code en lui-même.
    """
    st.warning(
        "Interface à compléter : remplacez ce message par votre propre écran "
        "dans la fonction `render_interface()`."
    )

    # Fallback minimal — à remplacer par votre design
    st.subheader("Aperçu brut (temporaire)")
    st.caption(f"{len(transactions)} transactions · {sum(1 for r in results if r.get('is_suspicious'))} alerte(s)")
    st.dataframe(results, use_container_width=True)


def main() -> None:
    st.set_page_config(
        page_title="Détection de fraude — Hackathon INTELO2026",
        page_icon="🛡️",
        layout="wide",
    )

    st.title("Détection de fraude financière")
    st.caption("Hackathon INTELO2026 — interface participant · évaluée par le jury")

    with st.sidebar:
        st.header("Charger des données")
        use_sample = st.toggle("Utiliser le fichier d'exemple", value=True)
        transactions: list[dict] = []

        if use_sample:
            transactions = load_transactions(str(SAMPLE_CSV))
            st.success(f"{len(transactions)} transactions (exemple)")
        else:
            uploaded = st.file_uploader("Importer un CSV", type=["csv"])
            if uploaded:
                tmp = Path(".streamlit_upload.csv")
                tmp.write_bytes(uploaded.getvalue())
                transactions = load_transactions(str(tmp))
                tmp.unlink(missing_ok=True)
                st.success(f"{len(transactions)} transactions importées")

        st.divider()
        st.markdown(
            "**Jury :** évaluez l'ergonomie et la clarté de l'écran principal, "
            "pas seulement le score des tests."
        )

    if not transactions:
        st.info("Chargez des transactions (barre latérale) puis lancez l'analyse.")
        return

    if st.button("Analyser", type="primary"):
        try:
            results = detect_fraud(transactions)
        except NotImplementedError:
            st.error("Implémentez d'abord `detect_fraud` dans `fraud_detection.py`.")
            return
        except Exception as exc:
            st.error(f"Erreur : {exc}")
            return

        render_interface(transactions, results)


if __name__ == "__main__":
    main()
