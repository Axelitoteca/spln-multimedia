"""ETL del ZIP SEPA hacia SQLite, filtrando por sucursales en Olavarria.

El ZIP maestro puede contener:
- CSVs directamente (comercio.csv, sucursales.csv, productos.csv), o
- Sub-ZIPs por cadena (uno por comercio), cada uno con esos CSVs.

Soportamos ambas estructuras y derivamos el esquema real del header del CSV
en vez de hardcodearlo. La normalizacion lower-snake-case mas alias cubre
los nombres tipicos definidos en Res. 678/2020 (Anexo II).
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .logging_setup import get_logger

log = get_logger(__name__)


# Aliases canonicos -> lista de nombres alternativos vistos en la wild.
COL_ALIASES = {
    "id_comercio": ["id_comercio", "comercio_id", "comerciocodigo"],
    "comercio_cuit": ["comercio_cuit", "cuit", "cuit_comercio"],
    "comercio_razon_social": ["comercio_razon_social", "razon_social"],
    "comercio_bandera_nombre": ["comercio_bandera_nombre", "bandera_nombre", "bandera"],
    "id_sucursal": ["id_sucursal", "sucursal_id"],
    "sucursales_nombre": ["sucursales_nombre", "sucursal_nombre", "nombre_sucursal"],
    "sucursales_calle": ["sucursales_calle", "sucursal_calle", "calle"],
    "sucursales_numero": ["sucursales_numero", "sucursal_numero", "numero"],
    "sucursales_codigo_postal": [
        "sucursales_codigo_postal",
        "codigo_postal",
        "sucursal_codigo_postal",
        "cp",
    ],
    "sucursales_localidad": ["sucursales_localidad", "localidad", "sucursal_localidad"],
    "sucursales_provincia": ["sucursales_provincia", "provincia", "sucursal_provincia"],
    "id_producto": ["id_producto", "producto_id", "ean", "productos_ean"],
    "productos_descripcion": [
        "productos_descripcion",
        "producto_descripcion",
        "descripcion",
    ],
    "productos_marca": ["productos_marca", "producto_marca", "marca"],
    "productos_cantidad_presentacion": [
        "productos_cantidad_presentacion",
        "cantidad_presentacion",
    ],
    "productos_unidad_medida_presentacion": [
        "productos_unidad_medida_presentacion",
        "unidad_medida_presentacion",
    ],
    "productos_precio_lista": [
        "productos_precio_lista",
        "precio_lista",
        "precio",
    ],
}

PROVINCIAS_BSAS = {"buenos aires", "bs as", "bs. as.", "bs as.", "ba"}


@dataclass
class IngestStats:
    sucursales_total: int
    sucursales_olavarria: int
    productos: int
    precios: int


def _norm_col(c: str) -> str:
    c = c.strip().lower()
    c = re.sub(r"[^a-z0-9]+", "_", c)
    return c.strip("_")


def _rename_canonical(df: pl.DataFrame) -> pl.DataFrame:
    cols = {c: _norm_col(c) for c in df.columns}
    df = df.rename(cols)
    rename = {}
    for canonical, aliases in COL_ALIASES.items():
        for alias in aliases:
            if alias in df.columns and alias != canonical:
                rename[alias] = canonical
                break
    if rename:
        df = df.rename(rename)
    return df


def _read_csv_bytes(data: bytes, *, fname_hint: str = "") -> pl.DataFrame:
    # SEPA usa pipe o coma segun el publicador. Detectamos.
    head = data[:4096].decode("utf-8", errors="replace")
    sep = "|" if head.count("|") > head.count(",") else ","
    try:
        return pl.read_csv(
            io.BytesIO(data),
            separator=sep,
            infer_schema_length=2000,
            ignore_errors=True,
            truncate_ragged_lines=True,
            try_parse_dates=False,
        )
    except Exception as e:  # pragma: no cover
        log.warning(f"fallo lectura CSV {fname_hint}: {e}")
        return pl.DataFrame()


def _iter_inner_csvs(zip_path: Path) -> Iterable[tuple[str, bytes]]:
    """Yield (logical_name, bytes) para cada CSV, manejando sub-ZIPs anidados."""
    with zipfile.ZipFile(zip_path) as outer:
        for info in outer.infolist():
            if info.is_dir():
                continue
            name = info.filename
            lower = name.lower()
            if lower.endswith(".csv"):
                yield name, outer.read(info)
            elif lower.endswith(".zip"):
                inner_bytes = outer.read(info)
                try:
                    with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
                        for sub in inner.infolist():
                            if sub.is_dir() or not sub.filename.lower().endswith(".csv"):
                                continue
                            yield f"{name}::{sub.filename}", inner.read(sub)
                except zipfile.BadZipFile:
                    log.warning(f"sub-zip corrupto: {name}")


def _classify(fname: str) -> str | None:
    f = fname.lower()
    if "comercio" in f and "sucursal" not in f:
        return "comercio"
    if "sucursal" in f:
        return "sucursal"
    if "producto" in f:
        return "producto"
    return None


def _is_olavarria(df: pl.DataFrame) -> pl.Expr:
    cp_col = pl.col("sucursales_codigo_postal").cast(pl.Utf8, strict=False).str.strip_chars()
    loc_col = (
        pl.col("sucursales_localidad").cast(pl.Utf8, strict=False).str.to_lowercase().fill_null("")
    )
    prov_col = (
        pl.col("sucursales_provincia")
        .cast(pl.Utf8, strict=False)
        .str.to_lowercase()
        .str.strip_chars()
        .fill_null("")
    )
    es_bsas = prov_col.is_in(list(PROVINCIAS_BSAS))
    cp_ok = cp_col == "7400"
    loc_ok = loc_col.str.contains("olavarr")
    _ = df  # silence linter
    return es_bsas & (cp_ok | loc_ok)


def create_schema(engine: Engine) -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS comercios (
        id_comercio TEXT PRIMARY KEY,
        cuit TEXT,
        razon_social TEXT,
        bandera TEXT
    );
    CREATE TABLE IF NOT EXISTS sucursales (
        id_comercio TEXT NOT NULL,
        id_sucursal TEXT NOT NULL,
        nombre TEXT,
        calle TEXT,
        numero TEXT,
        codigo_postal TEXT,
        localidad TEXT,
        provincia TEXT,
        PRIMARY KEY (id_comercio, id_sucursal)
    );
    CREATE INDEX IF NOT EXISTS ix_sucursales_cp ON sucursales(codigo_postal);
    CREATE TABLE IF NOT EXISTS productos (
        id_producto TEXT PRIMARY KEY,
        descripcion TEXT,
        marca TEXT,
        presentacion TEXT
    );
    CREATE INDEX IF NOT EXISTS ix_productos_id ON productos(id_producto);
    CREATE TABLE IF NOT EXISTS precios (
        id_comercio TEXT NOT NULL,
        id_sucursal TEXT NOT NULL,
        id_producto TEXT NOT NULL,
        precio REAL NOT NULL,
        fecha_dump DATE NOT NULL,
        PRIMARY KEY (id_comercio, id_sucursal, id_producto, fecha_dump)
    );
    CREATE INDEX IF NOT EXISTS ix_precios_fecha ON precios(fecha_dump);
    CREATE INDEX IF NOT EXISTS ix_precios_producto ON precios(id_producto);
    CREATE TABLE IF NOT EXISTS categorias_cache (
        id_producto TEXT PRIMARY KEY,
        categoria TEXT NOT NULL,
        fuente TEXT NOT NULL,
        actualizado_en TEXT NOT NULL
    );
    """
    with engine.begin() as conn:
        for stmt in filter(None, (s.strip() for s in ddl.split(";"))):
            conn.execute(text(stmt))


def ingest_zip(zip_path: Path, db_path: Path, fecha_dump: date) -> IngestStats:
    """Ingesta el ZIP a SQLite filtrando por Olavarria. Idempotente por (claves + fecha)."""
    engine = create_engine(f"sqlite:///{db_path}")
    create_schema(engine)

    comercios_frames: list[pl.DataFrame] = []
    sucursales_frames: list[pl.DataFrame] = []
    productos_frames: list[pl.DataFrame] = []

    for fname, data in _iter_inner_csvs(zip_path):
        kind = _classify(fname)
        if kind is None:
            continue
        df = _read_csv_bytes(data, fname_hint=fname)
        if df.is_empty():
            continue
        df = _rename_canonical(df)
        if kind == "comercio":
            comercios_frames.append(df)
        elif kind == "sucursal":
            sucursales_frames.append(df)
        elif kind == "producto":
            productos_frames.append(df)

    if not sucursales_frames or not productos_frames:
        raise RuntimeError("ZIP no contiene sucursales/productos reconocibles")

    sucursales = pl.concat(sucursales_frames, how="diagonal_relaxed")
    productos = pl.concat(productos_frames, how="diagonal_relaxed")
    comercios = (
        pl.concat(comercios_frames, how="diagonal_relaxed") if comercios_frames else pl.DataFrame()
    )

    sucursales_total = sucursales.height
    sucursales_olv = sucursales.filter(_is_olavarria(sucursales))
    log.info(f"sucursales total={sucursales_total} -> Olavarria={sucursales_olv.height}")
    if sucursales_olv.is_empty():
        return IngestStats(sucursales_total, 0, 0, 0)

    keys = sucursales_olv.select(["id_comercio", "id_sucursal"]).unique()
    productos_olv = productos.join(keys, on=["id_comercio", "id_sucursal"], how="inner")
    log.info(f"productos en sucursales Olavarria={productos_olv.height}")

    # comercios catalog
    if not comercios.is_empty():
        com_rows = comercios.select(
            pl.col("id_comercio").cast(pl.Utf8),
            pl.col("comercio_cuit").cast(pl.Utf8, strict=False).alias("cuit")
            if "comercio_cuit" in comercios.columns
            else pl.lit(None).alias("cuit"),
            pl.col("comercio_razon_social").cast(pl.Utf8, strict=False).alias("razon_social")
            if "comercio_razon_social" in comercios.columns
            else pl.lit(None).alias("razon_social"),
            pl.col("comercio_bandera_nombre").cast(pl.Utf8, strict=False).alias("bandera")
            if "comercio_bandera_nombre" in comercios.columns
            else pl.lit(None).alias("bandera"),
        ).unique(subset=["id_comercio"])
    else:
        com_rows = pl.DataFrame({"id_comercio": [], "cuit": [], "razon_social": [], "bandera": []})

    suc_rows = sucursales_olv.select(
        pl.col("id_comercio").cast(pl.Utf8),
        pl.col("id_sucursal").cast(pl.Utf8),
        pl.col("sucursales_nombre").cast(pl.Utf8, strict=False).alias("nombre")
        if "sucursales_nombre" in sucursales_olv.columns
        else pl.lit(None).alias("nombre"),
        pl.col("sucursales_calle").cast(pl.Utf8, strict=False).alias("calle")
        if "sucursales_calle" in sucursales_olv.columns
        else pl.lit(None).alias("calle"),
        pl.col("sucursales_numero").cast(pl.Utf8, strict=False).alias("numero")
        if "sucursales_numero" in sucursales_olv.columns
        else pl.lit(None).alias("numero"),
        pl.col("sucursales_codigo_postal").cast(pl.Utf8, strict=False).alias("codigo_postal"),
        pl.col("sucursales_localidad").cast(pl.Utf8, strict=False).alias("localidad")
        if "sucursales_localidad" in sucursales_olv.columns
        else pl.lit(None).alias("localidad"),
        pl.col("sucursales_provincia").cast(pl.Utf8, strict=False).alias("provincia")
        if "sucursales_provincia" in sucursales_olv.columns
        else pl.lit(None).alias("provincia"),
    )

    prod_catalog = (
        productos_olv.select(
            pl.col("id_producto").cast(pl.Utf8),
            pl.col("productos_descripcion").cast(pl.Utf8, strict=False).alias("descripcion"),
            pl.col("productos_marca").cast(pl.Utf8, strict=False).alias("marca")
            if "productos_marca" in productos_olv.columns
            else pl.lit(None).alias("marca"),
            (
                pl.col("productos_cantidad_presentacion").cast(pl.Utf8, strict=False)
                + pl.lit(" ")
                + pl.col("productos_unidad_medida_presentacion").cast(pl.Utf8, strict=False)
            ).alias("presentacion")
            if {"productos_cantidad_presentacion", "productos_unidad_medida_presentacion"}.issubset(
                set(productos_olv.columns)
            )
            else pl.lit(None).alias("presentacion"),
        )
        .filter(pl.col("id_producto").is_not_null())
        .unique(subset=["id_producto"])
    )

    precios_rows = (
        productos_olv.select(
            pl.col("id_comercio").cast(pl.Utf8),
            pl.col("id_sucursal").cast(pl.Utf8),
            pl.col("id_producto").cast(pl.Utf8),
            pl.col("productos_precio_lista").cast(pl.Float64, strict=False).alias("precio"),
        )
        .filter(pl.col("precio").is_not_null() & (pl.col("precio") > 0))
        .with_columns(pl.lit(fecha_dump.isoformat()).alias("fecha_dump"))
    )

    with engine.begin() as conn:
        _upsert(conn, "comercios", com_rows, ["id_comercio"])
        _upsert(conn, "sucursales", suc_rows, ["id_comercio", "id_sucursal"])
        _upsert(conn, "productos", prod_catalog, ["id_producto"])
        # precios: borrar la fecha_dump primero (idempotencia), luego insert
        conn.execute(
            text("DELETE FROM precios WHERE fecha_dump = :f"), {"f": fecha_dump.isoformat()}
        )
        if precios_rows.height:
            conn.exec_driver_sql(
                "INSERT INTO precios (id_comercio, id_sucursal, id_producto, precio, fecha_dump) VALUES (?,?,?,?,?)",
                list(precios_rows.iter_rows()),
            )

    return IngestStats(
        sucursales_total=sucursales_total,
        sucursales_olavarria=sucursales_olv.height,
        productos=prod_catalog.height,
        precios=precios_rows.height,
    )


def _upsert(conn, table: str, df: pl.DataFrame, pk_cols: list[str]) -> None:
    if df.is_empty():
        return
    cols = df.columns
    placeholders = ",".join(["?"] * len(cols))
    col_list = ",".join(cols)
    update_set = ",".join(f"{c}=excluded.{c}" for c in cols if c not in pk_cols)
    conflict = ",".join(pk_cols)
    if update_set:
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT({conflict}) DO UPDATE SET {update_set}"
        )
    else:
        sql = f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})"
    conn.exec_driver_sql(sql, list(df.iter_rows()))


def open_db(db_path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{db_path}")
    create_schema(engine)
    return engine
