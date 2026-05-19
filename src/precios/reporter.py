"""Genera reporte markdown + CSV con el comercio mas barato por producto en Olavarria."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import polars as pl
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .logging_setup import get_logger

log = get_logger(__name__)


def _load_dataframe(engine: Engine, fecha_dump: date) -> pl.DataFrame:
    sql = """
    SELECT
        p.id_producto,
        pr.descripcion,
        pr.marca,
        pr.presentacion,
        p.id_comercio,
        c.bandera AS comercio,
        c.razon_social,
        p.id_sucursal,
        s.nombre AS sucursal_nombre,
        s.calle, s.numero, s.codigo_postal, s.localidad,
        p.precio,
        COALESCE(cat.categoria, 'sin_clasificar') AS categoria
    FROM precios p
    JOIN sucursales s ON s.id_comercio = p.id_comercio AND s.id_sucursal = p.id_sucursal
    JOIN productos pr ON pr.id_producto = p.id_producto
    LEFT JOIN comercios c ON c.id_comercio = p.id_comercio
    LEFT JOIN categorias_cache cat ON cat.id_producto = p.id_producto
    WHERE p.fecha_dump = :f
    """
    with engine.begin() as conn:
        rows = conn.execute(text(sql), {"f": fecha_dump.isoformat()}).fetchall()
        cols = [
            "id_producto",
            "descripcion",
            "marca",
            "presentacion",
            "id_comercio",
            "comercio",
            "razon_social",
            "id_sucursal",
            "sucursal_nombre",
            "calle",
            "numero",
            "codigo_postal",
            "localidad",
            "precio",
            "categoria",
        ]
    return pl.DataFrame(rows, schema=cols, orient="row")


def _comercio_label(row: dict) -> str:
    return row.get("comercio") or row.get("razon_social") or row.get("id_comercio") or "?"


def _sucursal_label(row: dict) -> str:
    parts = [row.get("sucursal_nombre"), row.get("calle"), row.get("numero")]
    return " ".join(str(p) for p in parts if p) or row.get("id_sucursal", "?")


def generar_reporte(engine: Engine, fecha_dump: date, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    df = _load_dataframe(engine, fecha_dump)
    if df.is_empty():
        raise RuntimeError(f"no hay precios para {fecha_dump}; corrió la ingesta?")

    # Para cada producto: min / max sobre las sucursales de Olavarria.
    agg = (
        df.group_by("id_producto")
        .agg(
            pl.col("precio").min().alias("precio_min"),
            pl.col("precio").max().alias("precio_max"),
            pl.col("precio").count().alias("n_sucursales"),
        )
        .with_columns(
            (pl.col("precio_max") - pl.col("precio_min")).alias("ahorro_abs"),
            (
                (pl.col("precio_max") - pl.col("precio_min"))
                / pl.when(pl.col("precio_max") == 0).then(1).otherwise(pl.col("precio_max"))
                * 100
            ).alias("dif_pct"),
        )
    )

    # join con la fila de minimo (para conocer dónde está el más barato).
    min_rows = df.sort("precio").group_by("id_producto", maintain_order=True).agg(pl.all().first())
    reporte = min_rows.join(agg, on="id_producto").sort(
        "categoria", "ahorro_abs", descending=[False, True]
    )

    md_path = output_dir / f"reporte_{fecha_dump.isoformat()}.md"
    csv_path = output_dir / f"reporte_{fecha_dump.isoformat()}.csv"

    _write_csv(reporte, csv_path)
    _write_markdown(reporte, df, fecha_dump, md_path)
    log.info(f"reporte generado: {md_path}, {csv_path}")
    return md_path, csv_path


def _write_csv(reporte: pl.DataFrame, csv_path: Path) -> None:
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "categoria",
                "id_producto",
                "descripcion",
                "marca",
                "presentacion",
                "precio_min",
                "precio_max",
                "ahorro_abs",
                "dif_pct",
                "n_sucursales",
                "comercio_min",
                "sucursal_min",
            ]
        )
        for r in reporte.iter_rows(named=True):
            w.writerow(
                [
                    r["categoria"],
                    r["id_producto"],
                    r["descripcion"],
                    r.get("marca"),
                    r.get("presentacion"),
                    f"{r['precio_min']:.2f}",
                    f"{r['precio_max']:.2f}",
                    f"{r['ahorro_abs']:.2f}",
                    f"{r['dif_pct']:.1f}",
                    r["n_sucursales"],
                    _comercio_label(r),
                    _sucursal_label(r),
                ]
            )


def _write_markdown(
    reporte: pl.DataFrame, df_full: pl.DataFrame, fecha_dump: date, md_path: Path
) -> None:
    lines: list[str] = []
    lines.append(f"# Reporte de precios - Olavarria - {fecha_dump.isoformat()}\n")
    lines.append(
        f"Total productos comparados: **{reporte.height}** | "
        f"sucursales: **{df_full.select('id_sucursal').n_unique()}** | "
        f"comercios: **{df_full.select('id_comercio').n_unique()}**\n"
    )

    resumen_ganadores: list[tuple[str, str, str, int, int]] = []

    for cat in sorted(reporte["categoria"].unique().to_list()):
        sub = reporte.filter(pl.col("categoria") == cat).sort("ahorro_abs", descending=True)
        if sub.is_empty():
            continue

        # Top 20 por ahorro absoluto
        top = sub.head(20)
        lines.append(f"\n## {cat} ({sub.height} productos)\n")
        lines.append(
            "| Producto | Marca | Presentación | Precio min | Precio max | Δ% | Ahorro $ | Más barato en |"
        )
        lines.append("|---|---|---|---:|---:|---:|---:|---|")
        for r in top.iter_rows(named=True):
            lines.append(
                f"| {(r['descripcion'] or '')[:60]} | {r.get('marca') or ''} | "
                f"{r.get('presentacion') or ''} | ${r['precio_min']:.2f} | ${r['precio_max']:.2f} | "
                f"{r['dif_pct']:.1f}% | ${r['ahorro_abs']:.2f} | "
                f"{_comercio_label(r)} - {_sucursal_label(r)} |"
            )

        # Para esta categoria: que comercio gana mas veces?
        cat_full = df_full.filter(pl.col("categoria") == cat)
        ganador = (
            cat_full.sort("precio")
            .group_by("id_producto", maintain_order=True)
            .agg(pl.all().first())
            .group_by("id_comercio")
            .agg(pl.len().alias("wins"), pl.col("sucursal_nombre").first())
            .sort("wins", descending=True)
            .head(1)
        )
        if ganador.height:
            g = ganador.row(0, named=True)
            comercio_rows = df_full.filter(pl.col("id_comercio") == g["id_comercio"])
            label_comercio = (
                _comercio_label(comercio_rows.row(0, named=True))
                if comercio_rows.height
                else g["id_comercio"]
            )
            label_sucursal = g.get("sucursal_nombre") or "?"
            total = sub.height
            resumen_ganadores.append((cat, label_comercio, label_sucursal, g["wins"], total))

    lines.append("\n## Resumen por categoria\n")
    if resumen_ganadores:
        lines.append("| Categoría | Comercio | Sucursal | Gana en |")
        lines.append("|---|---|---|---:|")
        for cat, com, suc, wins, total in resumen_ganadores:
            lines.append(f"| {cat} | {com} | {suc} | {wins} de {total} |")
    else:
        lines.append("_(sin datos suficientes)_")

    md_path.write_text("\n".join(lines), encoding="utf-8")
