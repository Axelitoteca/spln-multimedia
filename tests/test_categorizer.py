from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, text

from precios import categorizer, etl
from tests.fixtures.build_fixture import build_fixture


def test_keyword_categoriza_top_categorias() -> None:
    cases = [
        ("Leche entera La Serenisima 1L", "lacteos"),
        ("Yerba mate Taragui 1kg", "bebidas"),
        ("Detergente Magistral 750ml", "limpieza"),
        ("Pañales Pampers M x40", "bebes"),
        ("Pan lactal Bimbo", "panaderia"),
        ("Carne picada especial", "carniceria"),
        ("Shampoo Sedal 400ml", "perfumeria"),
        ("Fideos Matarazzo 500g", "almacen"),
    ]
    for desc, expected in cases:
        assert categorizer.categorize_keyword(desc) == expected, f"fallo en: {desc}"


def test_keyword_no_match_devuelve_none() -> None:
    assert categorizer.categorize_keyword("Producto raro inclasificable XYZ") is None
    assert categorizer.categorize_keyword(None) is None
    assert categorizer.categorize_keyword("") is None


def test_categorize_all_skip_llm_marca_sin_clasificar(tmp_path: Path, monkeypatch) -> None:
    zip_path = build_fixture(tmp_path / "sepa.zip", big=False)
    db = tmp_path / "precios.db"
    etl.ingest_zip(zip_path, db, date(2026, 5, 19))

    engine = create_engine(f"sqlite:///{db}")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    stats = categorizer.categorize_all(engine, use_llm=True)
    assert stats["keyword"] >= 4
    assert stats["sin_clasificar"] >= 1

    with engine.begin() as conn:
        n = conn.execute(
            text("SELECT COUNT(*) FROM categorias_cache WHERE categoria='sin_clasificar'")
        ).scalar_one()
        assert n >= 1


def test_capa2_llm_mockeado(tmp_path: Path, monkeypatch) -> None:
    zip_path = build_fixture(tmp_path / "sepa.zip", big=False)
    db = tmp_path / "precios.db"
    etl.ingest_zip(zip_path, db, date(2026, 5, 19))
    engine = create_engine(f"sqlite:///{db}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(type="text", text='[{"id":"9990000000099","cat":"almacen"}]')]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg

    with patch("anthropic.Anthropic", return_value=fake_client):
        stats = categorizer.categorize_all(engine, use_llm=True)

    assert stats["llm"] == 1
    with engine.begin() as conn:
        cat = conn.execute(
            text("SELECT categoria FROM categorias_cache WHERE id_producto='9990000000099'")
        ).scalar_one()
        assert cat == "almacen"


def test_cache_no_reclasifica(tmp_path: Path, monkeypatch) -> None:
    zip_path = build_fixture(tmp_path / "sepa.zip", big=False)
    db = tmp_path / "precios.db"
    etl.ingest_zip(zip_path, db, date(2026, 5, 19))
    engine = create_engine(f"sqlite:///{db}")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    s1 = categorizer.categorize_all(engine, use_llm=False)
    s2 = categorizer.categorize_all(engine, use_llm=False)

    # En la segunda corrida, todo viene de cache.
    assert s2["cache"] >= s1["keyword"] + s1["sin_clasificar"]
    assert s2["keyword"] == 0
    assert s2["sin_clasificar"] == 0
