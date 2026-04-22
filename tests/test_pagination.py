"""
Pruebas unitarias para la lógica de paginación de la API de Moodle.

La API estándar (core_user_get_users, core_course_get_courses) puede
devolver listas grandes. El cliente debe paginar usando limitfrom/limitnum
y concatenar hasta recibir una página vacía (o menor que limitnum).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Implementación mínima de paginación (espejo de moodle_api.py) ────────────

def paginate(fetch_page, page_size: int = 500) -> list[dict]:
    """
    Consume páginas llamando a fetch_page(offset) hasta vaciar el cursor.
    fetch_page(offset) debe devolver lista[dict] de longitud <= page_size.
    """
    result = []
    offset = 0
    while True:
        page = fetch_page(offset)
        result.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return result


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_source(total: int):
    """Genera una fuente de datos ficticia de `total` ítems."""
    return [{"id": i} for i in range(total)]


def _page_fetcher(source: list[dict], page_size: int):
    """Devuelve un closure que simula la paginación de Moodle."""
    def fetch(offset: int) -> list[dict]:
        return source[offset: offset + page_size]
    return fetch


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_pagination_exact_multiple():
    """1000 ítems con page_size=500 → exactamente 2 páginas."""
    source = _make_source(1000)
    calls = []

    def fetch(offset):
        calls.append(offset)
        return source[offset: offset + 500]

    result = paginate(fetch, page_size=500)
    assert len(result) == 1000
    # La tercera llamada devuelve vacío y para el bucle
    assert calls == [0, 500, 1000]

def test_pagination_partial_last_page():
    """750 ítems → primera página llena (500) + segunda parcial (250) → para."""
    source = _make_source(750)
    calls = []

    def fetch(offset):
        calls.append(offset)
        return source[offset: offset + 500]

    result = paginate(fetch, page_size=500)
    assert len(result) == 750
    assert calls == [0, 500]

def test_pagination_empty_source():
    """Fuente vacía → primera página vacía → ningún ítem."""
    source: list = []
    calls = []

    def fetch(offset):
        calls.append(offset)
        return source[offset: offset + 500]

    result = paginate(fetch, page_size=500)
    assert result == []
    assert calls == [0]

def test_pagination_less_than_one_page():
    """37 ítems → una sola llamada."""
    source = _make_source(37)
    calls = []

    def fetch(offset):
        calls.append(offset)
        return source[offset: offset + 500]

    result = paginate(fetch, page_size=500)
    assert len(result) == 37
    assert calls == [0]

def test_pagination_single_item():
    source = _make_source(1)
    result = paginate(_page_fetcher(source, 500), page_size=500)
    assert result == [{"id": 0}]

def test_pagination_preserves_order():
    """Los ítems llegan en el orden correcto tras concatenar páginas."""
    source = _make_source(1200)
    result = paginate(_page_fetcher(source, 500), page_size=500)
    assert [r["id"] for r in result] == list(range(1200))

def test_pagination_small_page_size():
    """Funciona con page_size=1 (caso extremo)."""
    source = _make_source(5)
    result = paginate(_page_fetcher(source, 1), page_size=1)
    assert len(result) == 5
    assert [r["id"] for r in result] == [0, 1, 2, 3, 4]
