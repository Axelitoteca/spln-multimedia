"""CLI: python -m precios.cli --fecha 2026-05-19 --tipo minorista"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from . import categorizer, downloader, etl, reporter
from .logging_setup import get_logger

log = get_logger(__name__)


def _parse_fecha(s: str) -> date:
    s = s.strip().lower()
    if s in ("hoy", "today"):
        return date.today()
    if s in ("ayer", "yesterday"):
        from datetime import timedelta

        return date.today() - timedelta(days=1)
    return datetime.strptime(s, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="precios", description="Comparador SEPA Olavarria")
    parser.add_argument("--fecha", default="hoy", help="YYYY-MM-DD | hoy | ayer")
    parser.add_argument("--tipo", choices=["minorista", "mayorista"], default="minorista")
    parser.add_argument("--data-dir", default="data", help="dir para cache de ZIPs y SQLite")
    parser.add_argument("--output-dir", default="output", help="dir para reportes md/csv")
    parser.add_argument("--skip-llm", action="store_true", help="no usar Claude API en capa 2")
    parser.add_argument("--db", default=None, help="path a sqlite (default: data/precios.db)")
    args = parser.parse_args(argv)

    fecha = _parse_fecha(args.fecha)
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    db_path = Path(args.db) if args.db else data_dir / "precios.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    log.info(f"== precios SEPA {args.tipo} fecha={fecha} ==")

    res = downloader.download(fecha, args.tipo, data_dir)
    log.info(f"ZIP listo: {res.path} (cached={res.cached}, fecha real={res.fecha})")

    stats = etl.ingest_zip(res.path, db_path, res.fecha)
    log.info(
        f"ingesta: sucursales_olv={stats.sucursales_olavarria}/{stats.sucursales_total}, "
        f"productos={stats.productos}, precios={stats.precios}"
    )
    if stats.sucursales_olavarria == 0:
        log.warning("no se encontraron sucursales en Olavarria. nada que reportar.")
        return 1

    engine = etl.open_db(db_path)
    cat_stats = categorizer.categorize_all(engine, use_llm=not args.skip_llm)
    log.info(f"categorizacion: {cat_stats}")

    md, csv_path = reporter.generar_reporte(engine, res.fecha, output_dir)
    log.info(f"OK: {md} | {csv_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
