from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text

from precios import etl
from tests.fixtures.build_fixture import build_fixture


def test_ingesta_filtra_olavarria(tmp_path: Path) -> None:
    zip_path = build_fixture(tmp_path / "sepa.zip", big=False)
    db = tmp_path / "precios.db"
    fecha = date(2026, 5, 19)

    stats = etl.ingest_zip(zip_path, db, fecha)

    # Comercio A: 1 sucursal Olavarria + 1 CABA -> solo se guarda Olavarria.
    # Comercio B: 1 sucursal Olavarria.
    assert stats.sucursales_olavarria == 2
    assert stats.sucursales_total == 3
    # 4 productos Olavarria del A (sucursal 1) + 4 del B (sucursal 10) = 8 precios
    assert stats.precios == 8

    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        # SQL del criterio 3
        rows = conn.execute(
            text(
                "SELECT s.codigo_postal, p.precio FROM precios p "
                "JOIN sucursales s ON s.id_comercio=p.id_comercio AND s.id_sucursal=p.id_sucursal "
                "WHERE s.codigo_postal LIKE '%7400%'"
            )
        ).fetchall()
        assert len(rows) >= 1

        # productos catalog deduplicado por EAN
        n_prod = conn.execute(text("SELECT COUNT(*) FROM productos")).scalar_one()
        # 4 EAN unicos en el fixture A + 1 nuevo en B = 5
        assert n_prod == 5


def test_re_ingesta_misma_fecha_idempotente(tmp_path: Path) -> None:
    zip_path = build_fixture(tmp_path / "sepa.zip", big=False)
    db = tmp_path / "precios.db"
    fecha = date(2026, 5, 19)

    etl.ingest_zip(zip_path, db, fecha)
    etl.ingest_zip(zip_path, db, fecha)

    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        n = conn.execute(
            text("SELECT COUNT(*) FROM precios WHERE fecha_dump = :f"), {"f": fecha.isoformat()}
        ).scalar_one()
        assert n == 8


def test_norm_col_y_aliases() -> None:
    import polars as pl

    df = pl.DataFrame(
        {"Comercio CUIT": ["x"], "CODIGO_POSTAL": ["7400"], "Producto Descripcion": ["leche"]}
    )
    df2 = etl._rename_canonical(df)
    assert "comercio_cuit" in df2.columns
    assert "sucursales_codigo_postal" in df2.columns
    assert "productos_descripcion" in df2.columns
