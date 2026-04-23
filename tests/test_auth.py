from python_core.auth import parse_cookie_header


def test_parse_cookie_header():
    raw = "stratio-cookie=abc; JSESSIONID=xyz; other=v"
    out = parse_cookie_header(raw)
    assert out["stratio-cookie"] == "abc"
    assert out["JSESSIONID"] == "xyz"
