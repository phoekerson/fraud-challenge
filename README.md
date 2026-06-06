# Hackathon IT — Détection de fraude financière par l'IA

**Organisation :** [CURSOR-INTELO2026](https://github.com/INTELO2026)  
**Dépôt officiel :** https://github.com/INTELO2026/fraud-challenge

> **Thème :** *L'Intelligence Artificielle au service de la sécurité financière : détecter, prévenir et combattre la fraude.*

Vous avez **4 heures**. Vous codez **en solo**, en **Python**.

Votre mission : compléter la fonction `detect_fraud` pour analyser des transactions financières et signaler celles qui sont suspectes — **sans accabler les clients honnêtes**.

---

## Démarrage rapide

```bash
# 1. Forkez https://github.com/INTELO2026/fraud-challenge puis clonez VOTRE fork
git clone https://github.com/VOTRE-PSEUDO/fraud-challenge.git
cd fraud-challenge

# 2. Installez les dépendances
pip install -r requirements.txt

# 3. Lancez les tests (ils échouent au début, c'est normal)
pytest tests/ -v

# 4. Implémentez detect_fraud dans fraud_detection.py

# 5. Créez VOTRE interface intuitive dans app.py (base fournie)
streamlit run app.py
```

À chaque **push** sur votre fork et à chaque **pull request** vers le dépôt officiel, la CI relance les tests et affiche votre score **X/Y tests publics réussis**.

---

## Soumission officielle

1. **Fork** ce dépôt sur votre compte GitHub.
2. Travaillez sur une branche : `git checkout -b votre-pseudo`.
3. Poussez régulièrement : `git push origin votre-pseudo`.
4. Ouvrez une **Pull Request** vers le dépôt officiel du hackathon.
5. Vérifiez que la CI est **verte** et notez votre score affiché.

> Les tests **cachés** (niveau 2 avancé et niveau 3) ne sont pas dans ce dépôt. Ils servent au **classement final**. Faites passer les tests publics, mais codez une logique qui **généralise**.

---

## Interface à créer (évaluée par le jury)

Un **squelette** `app.py` est fourni (Streamlit). **Vous devez le transformer** en interface **intuitive** pour que le jury et un public non technique comprennent votre solution.

```bash
streamlit run app.py
```

À faire dans `render_interface()` :
- expliquer clairement ce qui est suspect et pourquoi ;
- présenter les résultats de façon visuelle (tableaux, cartes, couleurs, filtres, graphiques…) ;
- guider l’utilisateur sans qu’il lise le code.

**Important :**
| Élément | Qui juge ? |
|---------|------------|
| `detect_fraud` + tests | **Automatique** (CI + classement X/21) |
| `app.py` (votre interface) | **Jury humain** (repêchage, démo, créativité) |

La CI **ne note pas** l’interface. Le jury l’utilisera pour **repêcher** des candidats intéressants au-delà du seul score technique.

## Ce que vous devez implémenter (moteur de détection)

Dans `fraud_detection.py`, complétez :

```python
def detect_fraud(transactions):
    ...
```

- **Entrée** : la liste complète des transactions (dictionnaires). Vous recevez tout le lot d'un coup pour comparer chaque transaction à l'historique du client.
- **Sortie** : une liste de résultats, **un par transaction**, dans le **même ordre** :

```python
{
    "transaction_id": "T-001",
    "fraud_score": 0.92,      # entre 0.0 et 1.0
    "is_suspicious": True,
    "reason": "Montant très supérieur à l'habitude du client",
}
```

La fonction `load_transactions` (lecture CSV) est **déjà fournie** — concentrez-vous sur la détection.

### Format d'une transaction

| Clé              | Type            | Remarque                          |
|------------------|-----------------|-----------------------------------|
| `transaction_id` | str             |                                   |
| `timestamp`      | str ISO 8601    | peut être `None`                  |
| `user_id`        | str             |                                   |
| `amount`         | float           | peut être `None`, négatif ou nul  |
| `currency`       | str             |                                   |
| `merchant`       | str             |                                   |
| `country`        | str (code ISO)  | peut être `None`                  |
| `card_present`   | bool            | peut être `None`                  |

Les données réelles sont imparfaites. Votre programme **ne doit jamais planter**.

---

## Les trois paliers

Votre progression = **nombre de tests réussis** (publics visibles en CI).

| Niveau | Contenu |
|--------|---------|
| **1 — Fondamentaux** | Format de sortie ; montant négatif/nul ; champs manquants sans crash |
| **2 — Logique métier** | Montant anormal vs historique ; fréquence ; incohérence géographique |
| **3 — Finesse** | Éviter les faux positifs ; cas limites (dates, doublons…) |

**Conseil :** bouclez le niveau 1 en entier avant d'attaquer le 2.

---

## Données d'exemple

- `data/sample_transactions.csv`
- `data/sample_expected.json`

```python
from fraud_detection import load_transactions, detect_fraud
resultats = detect_fraud(load_transactions("data/sample_transactions.csv"))
```

---

## Bonus — API REST + authentification forte (MFA)

En plus de l'interface, une **API** (`api.py`, FastAPI) permet à une entreprise de
paiement de récupérer les verdicts en **JSON** et d'appliquer une **authentification
multi-facteurs** sur les transactions douteuses, plutôt que de les bloquer
(réduction des faux positifs).

```bash
uvicorn api:app --reload      # doc interactive : http://localhost:8000/docs
```

| Endpoint | Rôle |
|----------|------|
| `POST /analyze` | analyse des transactions (JSON) → verdicts JSON |
| `POST /analyze/csv` | idem à partir d'un fichier CSV |
| `GET /results` · `GET /results/pending-mfa` | derniers résultats / transactions à vérifier |
| `POST /mfa/enroll` | enrôle un client → secret + URI `otpauth://` (QR) |
| `POST /mfa/verify` | vérifie un code TOTP → valide la transaction |

Le MFA est un **TOTP RFC 6238** (HMAC-SHA1, 6 chiffres, 30 s) **compatible
Google Authenticator et Microsoft Authenticator** — implémenté en bibliothèque
standard (`mfa.py`), sans dépendance externe.

Bon courage !
