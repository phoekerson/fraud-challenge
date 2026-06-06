from fraud_detection import load_transactions, detect_fraud

res = detect_fraud(load_transactions("data/sample_transactions.csv"))
for r in res:
    print(f"{r['transaction_id']:6} susp={str(r['is_suspicious']):5} "
          f"score={r['fraud_score']:.2f} action={r['recommended_action']:9} "
          f"mfa={r['mfa_required']!s:5} | {r['reason']}")
