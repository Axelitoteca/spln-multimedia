"""Construye un ZIP SEPA sintético para tests. Reproduce la estructura tipica:
ZIP maestro -> 2 sub-ZIPs (uno por comercio) -> comercio.csv, sucursales.csv, productos.csv.
"""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path


def _csv(rows: list[list[str]]) -> bytes:
    out = io.StringIO()
    for r in rows:
        out.write(",".join(r))
        out.write("\n")
    return out.getvalue().encode("utf-8")


def _sub_zip(cuit: str, bandera: str, sucursales: list[dict], productos: list[dict]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "comercio.csv",
            _csv(
                [
                    [
                        "id_comercio",
                        "comercio_cuit",
                        "comercio_razon_social",
                        "comercio_bandera_nombre",
                    ],
                    [cuit, cuit, f"{bandera} SA", bandera],
                ]
            ),
        )
        suc_rows = [
            [
                "id_comercio",
                "id_sucursal",
                "sucursales_nombre",
                "sucursales_calle",
                "sucursales_numero",
                "sucursales_codigo_postal",
                "sucursales_localidad",
                "sucursales_provincia",
            ]
        ]
        for s in sucursales:
            suc_rows.append(
                [
                    cuit,
                    s["id"],
                    s["nombre"],
                    s["calle"],
                    s["numero"],
                    s["cp"],
                    s["localidad"],
                    s["provincia"],
                ]
            )
        zf.writestr("sucursales.csv", _csv(suc_rows))

        prod_rows = [
            [
                "id_comercio",
                "id_sucursal",
                "id_producto",
                "productos_descripcion",
                "productos_marca",
                "productos_cantidad_presentacion",
                "productos_unidad_medida_presentacion",
                "productos_precio_lista",
            ]
        ]
        for p in productos:
            prod_rows.append(
                [
                    cuit,
                    p["id_sucursal"],
                    p["ean"],
                    p["desc"],
                    p.get("marca", ""),
                    p.get("cant", "1"),
                    p.get("unid", "u"),
                    str(p["precio"]),
                ]
            )
        zf.writestr("productos.csv", _csv(prod_rows))
    return buf.getvalue()


def build_fixture(target: Path, *, big: bool = False) -> Path:
    """Build a synthetic master ZIP. If big=True, pad to >10MB for size validation."""
    # Comercio A: una sucursal en Olavarria (CP 7400), otra en CABA.
    a_suc = [
        {
            "id": "1",
            "nombre": "Olavarría Centro",
            "calle": "Av Pringles",
            "numero": "200",
            "cp": "7400",
            "localidad": "Olavarría",
            "provincia": "Buenos Aires",
        },
        {
            "id": "2",
            "nombre": "Caballito",
            "calle": "Rivadavia",
            "numero": "5000",
            "cp": "1424",
            "localidad": "CABA",
            "provincia": "Ciudad Autonoma de Buenos Aires",
        },
    ]
    a_prod = [
        # En sucursal Olavarria
        {
            "id_sucursal": "1",
            "ean": "7790070112233",
            "desc": "Leche entera La Serenisima",
            "marca": "La Serenisima",
            "cant": "1",
            "unid": "L",
            "precio": 1050.0,
        },
        {
            "id_sucursal": "1",
            "ean": "7790036000077",
            "desc": "Yerba mate Taragui",
            "marca": "Taragui",
            "cant": "1",
            "unid": "kg",
            "precio": 3200.0,
        },
        {
            "id_sucursal": "1",
            "ean": "7791234500011",
            "desc": "Detergente Magistral 750ml",
            "marca": "Magistral",
            "cant": "750",
            "unid": "ml",
            "precio": 2200.0,
        },
        {
            "id_sucursal": "1",
            "ean": "7790004003344",
            "desc": "Pañales Pampers M x40",
            "marca": "Pampers",
            "cant": "40",
            "unid": "u",
            "precio": 15800.0,
        },
        # Mismo EAN en CABA, no debe contar
        {
            "id_sucursal": "2",
            "ean": "7790070112233",
            "desc": "Leche entera La Serenisima",
            "marca": "La Serenisima",
            "cant": "1",
            "unid": "L",
            "precio": 990.0,
        },
    ]

    # Comercio B: tambien tiene sucursal en Olavarria (por nombre, sin CP exacto).
    b_suc = [
        {
            "id": "10",
            "nombre": "Olavarría Sur",
            "calle": "Belgrano",
            "numero": "1100",
            "cp": "B7400",
            "localidad": "OLAVARRIA",
            "provincia": "Buenos Aires",
        },
    ]
    b_prod = [
        {
            "id_sucursal": "10",
            "ean": "7790070112233",
            "desc": "Leche entera La Serenisima",
            "marca": "La Serenisima",
            "cant": "1",
            "unid": "L",
            "precio": 980.0,
        },
        {
            "id_sucursal": "10",
            "ean": "7790036000077",
            "desc": "Yerba mate Taragui",
            "marca": "Taragui",
            "cant": "1",
            "unid": "kg",
            "precio": 3450.0,
        },
        {
            "id_sucursal": "10",
            "ean": "7791234500011",
            "desc": "Detergente Magistral 750ml",
            "marca": "Magistral",
            "cant": "750",
            "unid": "ml",
            "precio": 2050.0,
        },
        {
            "id_sucursal": "10",
            "ean": "9990000000099",
            "desc": "Producto raro inclasificable XYZ",
            "marca": "Generic",
            "cant": "1",
            "unid": "u",
            "precio": 500.0,
        },
    ]

    a_bytes = _sub_zip("30111111119", "Carrefour", a_suc, a_prod)
    b_bytes = _sub_zip("30222222227", "DIA", b_suc, b_prod)

    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as outer:
        outer.writestr("sepa_30111111119.zip", a_bytes)
        outer.writestr("sepa_30222222227.zip", b_bytes)
        if big:
            # padding incompresible (urandom) para superar 10MB despues de deflate
            info = zipfile.ZipInfo("padding.bin")
            info.compress_type = zipfile.ZIP_STORED
            outer.writestr(info, os.urandom(11 * 1024 * 1024))
    return target


if __name__ == "__main__":  # pragma: no cover
    p = build_fixture(Path("/tmp/sepa_fixture.zip"), big=True)
    print(p, p.stat().st_size)
