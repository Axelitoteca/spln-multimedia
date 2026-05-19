"""Descarga idempotente del ZIP diario SEPA.

La estructura típica del dataset publicado en datos.produccion.gob.ar es un
ZIP por dia de la semana (sepa_lunes.zip, sepa_martes.zip, ...). El ZIP
maestro contiene a su vez sub-ZIPs por cadena. Como la URL exacta cambia
con cada release del portal CKAN, soportamos:

- override completo via --url o env var (SEPA_MINORISTA_URL / SEPA_MAYORISTA_URL)
- resolver por dia-de-la-semana usando un template con {slug}
"""

from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import httpx

from .logging_setup import get_logger

log = get_logger(__name__)

DIAS_ES = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

# Defaults: pueden sobreescribirse por env var o CLI. Si el portal CKAN cambia
# la URL, basta con setear SEPA_MINORISTA_URL / SEPA_MAYORISTA_URL.
DEFAULT_URLS = {
    "minorista": "https://datos.produccion.gob.ar/dataset/sepa-precios/resource/{slug}/download/sepa_{slug}.zip",
    "mayorista": "https://datos.produccion.gob.ar/dataset/precios-claros-sepa-mayoristas/resource/{slug}/download/sepa_mayorista_{slug}.zip",
}

MIN_ZIP_BYTES = 10 * 1024 * 1024  # 10 MB


@dataclass
class DownloadResult:
    path: Path
    fecha: date
    tipo: str
    cached: bool


def _slug_for(fecha: date) -> str:
    return DIAS_ES[fecha.weekday()]


def _url_for(tipo: str, fecha: date) -> str:
    env_key = f"SEPA_{tipo.upper()}_URL"
    template = os.getenv(env_key) or DEFAULT_URLS[tipo]
    return template.format(
        slug=_slug_for(fecha),
        fecha=fecha.isoformat(),
        yyyymmdd=fecha.strftime("%Y%m%d"),
    )


def _cache_path(data_dir: Path, fecha: date, tipo: str) -> Path:
    return data_dir / "raw" / fecha.isoformat() / f"sepa_{tipo}.zip"


def _validate_zip(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "no existe"
    size = path.stat().st_size
    if size < MIN_ZIP_BYTES:
        return False, f"tamano insuficiente ({size} bytes)"
    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            if bad is not None:
                return False, f"miembro corrupto: {bad}"
            if not zf.namelist():
                return False, "vacio"
    except zipfile.BadZipFile as e:
        return False, f"bad zip: {e}"
    return True, "ok"


def _download_to(url: str, dest: Path, client: httpx.Client) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log.info(f"GET {url}")
    with client.stream("GET", url, follow_redirects=True, timeout=120.0) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1 << 20):
                f.write(chunk)
    tmp.replace(dest)


def download(
    fecha: date,
    tipo: str,
    data_dir: Path,
    *,
    client: httpx.Client | None = None,
    fallback_days: int = 7,
) -> DownloadResult:
    """Descarga el ZIP para la fecha pedida; si falla, retrocede hasta `fallback_days` dias.

    Idempotente: si ya existe un ZIP valido cacheado, lo devuelve sin re-descargar.
    """
    if tipo not in DEFAULT_URLS:
        raise ValueError(f"tipo invalido: {tipo}; usa minorista|mayorista")

    target = _cache_path(data_dir, fecha, tipo)
    ok, _ = _validate_zip(target)
    if ok:
        log.info(f"cache hit: {target}")
        return DownloadResult(path=target, fecha=fecha, tipo=tipo, cached=True)

    own_client = client is None
    if own_client:
        client = httpx.Client(headers={"User-Agent": "precios-olavarria/0.1"})

    try:
        for delta in range(fallback_days + 1):
            attempt_date = fecha - timedelta(days=delta)
            attempt_path = _cache_path(data_dir, attempt_date, tipo)
            ok, _ = _validate_zip(attempt_path)
            if ok:
                log.info(f"cache hit (fallback {delta}d): {attempt_path}")
                return DownloadResult(path=attempt_path, fecha=attempt_date, tipo=tipo, cached=True)

            url = _url_for(tipo, attempt_date)
            try:
                _download_to(url, attempt_path, client)
            except (httpx.HTTPError, OSError) as e:
                log.warning(f"intento {attempt_date} fallo: {e}")
                if attempt_path.exists():
                    attempt_path.unlink()
                continue

            ok, msg = _validate_zip(attempt_path)
            if not ok:
                log.warning(f"validacion {attempt_date} fallo: {msg}")
                attempt_path.unlink(missing_ok=True)
                continue

            log.info(f"descarga ok: {attempt_path} ({attempt_path.stat().st_size:,} bytes)")
            return DownloadResult(path=attempt_path, fecha=attempt_date, tipo=tipo, cached=False)

        raise RuntimeError(
            f"no se pudo descargar SEPA {tipo} desde {fecha} retrocediendo {fallback_days} dias"
        )
    finally:
        if own_client:
            client.close()
