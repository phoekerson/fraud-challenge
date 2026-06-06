from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=40).run()
print("exception:", at.exception)
assert not at.exception, at.exception
print("OK — app.py s'exécute sans erreur (MFA + 3 voies)")
