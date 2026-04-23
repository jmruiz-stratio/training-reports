from mcp_server.tools import get_partner_kpis


def test_get_partner_kpis_empty(tmp_path):
    result = get_partner_kpis(str(tmp_path), "acme")
    assert result["partner"] == "acme"
    assert result["users"] == 0
