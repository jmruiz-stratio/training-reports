from python_core.domain.rules import derive_partner


def test_derive_partner_stratio():
    assert derive_partner("john-acme", "john@stratio.com") == "stratio"


def test_derive_partner_last_token():
    assert derive_partner("ana-bigcorp", "ana@bigcorp.com") == "bigcorp"
