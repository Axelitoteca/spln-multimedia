from datetime import date
from pathlib import Path

import httpx
import pytest

from precios import downloader
from tests.fixtures.build_fixture import build_fixture


def _client_serving(zip_bytes: bytes) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        # primer pedido falla, segundo (fallback ayer) ok
        if (
            "lunes" in request.url.path
            or "martes" in request.url.path
            or "miercoles" in request.url.path
            or "jueves" in request.url.path
            or "viernes" in request.url.path
            or "sabado" in request.url.path
            or "domingo" in request.url.path
        ):
            return httpx.Response(200, content=zip_bytes)
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_descarga_cachea_y_valida(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fix.zip", big=True)
    zip_bytes = fixture.read_bytes()
    client = _client_serving(zip_bytes)
    fecha = date(2026, 5, 19)

    res1 = downloader.download(fecha, "minorista", tmp_path, client=client)
    assert res1.path.exists()
    assert res1.cached is False

    # segunda corrida: cache hit, sin red.
    res2 = downloader.download(fecha, "minorista", tmp_path, client=client)
    assert res2.cached is True
    assert res2.path == res1.path


def test_validacion_rechaza_zip_corrupto(tmp_path: Path) -> None:
    target = tmp_path / "raw" / "2026-05-19" / "sepa_minorista.zip"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"not a zip")
    ok, msg = downloader._validate_zip(target)
    assert ok is False
    assert "bad zip" in msg or "tamano" in msg


def test_fallback_a_dia_anterior(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fix.zip", big=True)
    zip_bytes = fixture.read_bytes()

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        # primer intento falla
        if calls["n"] == 1:
            return httpx.Response(500)
        return httpx.Response(200, content=zip_bytes)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    res = downloader.download(date(2026, 5, 19), "minorista", tmp_path, client=client)
    assert res.cached is False
    # se uso el fallback de ayer
    assert res.fecha == date(2026, 5, 18)


def test_tipo_invalido_levanta(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        downloader.download(date(2026, 5, 19), "raro", tmp_path)
