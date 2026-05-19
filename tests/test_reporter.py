from datetime import date
from pathlib import Path

from precios import categorizer, etl, reporter
from tests.fixtures.build_fixture import build_fixture


def test_reporte_end_to_end(tmp_path: Path, monkeypatch) -> None:
    zip_path = build_fixture(tmp_path / "sepa.zip", big=False)
    db = tmp_path / "precios.db"
    out = tmp_path / "output"
    fecha = date(2026, 5, 19)

    etl.ingest_zip(zip_path, db, fecha)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    engine = etl.open_db(db)
    categorizer.categorize_all(engine, use_llm=False)

    md, csv_path = reporter.generar_reporte(engine, fecha, out)

    assert md.exists() and csv_path.exists()
    contenido = md.read_text(encoding="utf-8")
    assert "Olavarria" in contenido
    assert "## lacteos" in contenido or "## limpieza" in contenido
    # Producto comun a las 2 sucursales: leche; mas barato es comercio B ($980 vs $1050)
    assert "$980" in contenido or "980.0" in contenido

    csv_text = csv_path.read_text(encoding="utf-8")
    assert "7790070112233" in csv_text
