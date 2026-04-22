"""
Pruebas unitarias para la regla canónica de derivación de partner.

La regla (§6.2 f_usuarios y §14 Glosario):
  - Si email o username contienen 'stratio' (case-insensitive) → 'stratio'
  - En caso contrario → último token del username tras el último '-'
    Ejemplo: 'juan.garcia-acme' → 'acme'
             'admin-foo-corp'   → 'corp'
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def derive_partner(username: str, email: str) -> str:
    """
    Implementación Python de la regla canónica de partner.
    Debe mantenerse en sincronía con:
      - src/transform/semantic/f_usuarios.sql  (Spark SQL)
      - src/agent/sanity.py                    (DuckDB)
    """
    if "stratio" in username.lower() or "stratio" in email.lower():
        return "stratio"
    parts = username.split("-")
    return parts[-1] if parts else username


# ─── Casos nominales ──────────────────────────────────────────────────────────

def test_partner_simple():
    assert derive_partner("juan-acme", "juan@acme.com") == "acme"

def test_partner_multiple_hyphens():
    assert derive_partner("admin-foo-corp", "admin@corp.com") == "corp"

def test_partner_no_hyphen():
    # Sin guión: el username completo es el partner
    assert derive_partner("juangarcia", "juan@acme.com") == "juangarcia"

def test_partner_stratio_username():
    assert derive_partner("admin-stratio", "admin@stratio.com") == "stratio"

def test_partner_stratio_email():
    assert derive_partner("jsmith-partner", "jsmith@stratio.com") == "stratio"

def test_partner_stratio_case_insensitive_email():
    assert derive_partner("jsmith-partner", "jsmith@STRATIO.COM") == "stratio"

def test_partner_stratio_case_insensitive_username():
    assert derive_partner("admin-STRATIO", "admin@other.com") == "stratio"

def test_partner_stratio_substring_email():
    # 'stratio' como substring del dominio
    assert derive_partner("user-partner", "user@beta.stratio.io") == "stratio"

def test_partner_trailing_hyphen():
    # Edge case: username termina en '-'
    username = "user-"
    result = derive_partner(username, "user@other.com")
    assert result == ""   # split deja cadena vacía como último elemento

def test_partner_unicode_not_stratio():
    assert derive_partner("maría-acme", "maria@acme.es") == "acme"


# ─── Batch: regla aplicada a varios usuarios ──────────────────────────────────

def test_partner_derivation_batch():
    cases = [
        ("pepe-iberdrola",   "pepe@iberdrola.com",   "iberdrola"),
        ("admin",            "admin@stratio.com",     "stratio"),
        ("bob-a-b-mycorp",   "bob@mycorp.net",        "mycorp"),
        ("stratio.admin",    "sa@internal.com",       "stratio"),  # 'stratio' en username
    ]
    for username, email, expected in cases:
        result = derive_partner(username, email)
        assert result == expected, (
            f"derive_partner({username!r}, {email!r}) = {result!r}, expected {expected!r}"
        )
