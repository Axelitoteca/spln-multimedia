"""Categorizador hibrido: capa 1 keywords, capa 2 Claude Haiku (opcional, cacheado)."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .logging_setup import get_logger

log = get_logger(__name__)


CATEGORIAS = [
    "lacteos",
    "almacen",
    "limpieza",
    "bebidas",
    "panaderia",
    "carniceria",
    "perfumeria",
    "bebes",
    "sin_clasificar",
]

# Keywords -> categoria. Orden importa (primer match gana). Cubre top volumen.
KEYWORDS: list[tuple[str, str]] = [
    # bebes (antes que lacteos para que "leche bebe" caiga aca)
    (r"\bpanal(es)?\b|\bbebe(s)?\b|\bmaternal\b|\bformula infantil\b|\bnan\b|\bnestum\b", "bebes"),
    # perfumeria / higiene personal
    (
        r"\bshampoo\b|\bacondicionador\b|\bjabon (de )?tocador\b|\bjabon liquido para manos\b|"
        r"\bcrema (corporal|facial|de manos)\b|\bdesodorante\b|\bantitranspirante\b|\bpasta dental\b|"
        r"\bcepillo dental\b|\benjuague bucal\b|\bafeitar\b|\btoallitas?\b|\btoalla femenina\b|"
        r"\btampones?\b|\bprotectores diarios\b|\bpapel higienico\b",
        "perfumeria",
    ),
    # limpieza
    (
        r"\bdetergente\b|\blavandina\b|\blimpiador\b|\bdesengrasante\b|\bdesinfectante\b|"
        r"\bjabon en polvo\b|\bjabon liquido\b|\bsuavizante\b|\bquitamanchas\b|\besponja\b|"
        r"\btrapo\b|\brejilla\b|\bbolsas (de )?residuos?\b|\binsecticida\b|\baromatizante\b|"
        r"\blustramuebles\b|\bcera\b",
        "limpieza",
    ),
    # bebidas
    (
        r"\bgaseosa\b|\bcoca cola\b|\bsprite\b|\bfanta\b|\bpepsi\b|\bseven up\b|\bschweppes\b|"
        r"\bagua mineral\b|\bagua saborizada\b|\bsoda\b|\bjugo\b|\bcerveza\b|\bvino\b|"
        r"\bwhisky\b|\bvodka\b|\bfernet\b|\bgin\b|\bron\b|\bsidra\b|\bisotonica\b|\bgatorade\b|"
        r"\bpowerade\b|\bcafe\b|\bte\b|\byerba\b|\bmate cocido\b",
        "bebidas",
    ),
    # panaderia
    (
        r"\bpan\b|\bpan lactal\b|\bgalletit(a|as)\b|\bgalleta\b|\bbiz?cochuelo\b|\bfact(ura|uras)\b|"
        r"\bmedialun(a|as)\b|\bcriollos\b|\btapas? de (empanada|tarta|pascualina)\b|\bharina\b|"
        r"\blevadura\b|\bpremezcla\b|\btostadas\b",
        "panaderia",
    ),
    # carniceria / fiambres
    (
        r"\bcarne\b|\bnalga\b|\bpeceto\b|\bbife\b|\basado\b|\bvacio\b|\bmatambre\b|\bmilanesas?\b|"
        r"\bpollo\b|\bsupreme?a\b|\bmuslo\b|\bpata muslo\b|\bcerdo\b|\bchori(zo|zos)\b|\bsalchich(a|as)\b|"
        r"\bhamburgues(a|as)\b|\bjamon\b|\bsalame\b|\bsalami\b|\bmortadela\b|\bpaleta cocida\b|\bbondiola\b|"
        r"\bpancet(a|as)\b",
        "carniceria",
    ),
    # lacteos
    (
        r"\bleche\b|\byogur(t)?\b|\bqueso\b|\bdulce de leche\b|\bcrema (de leche)?\b|\bmanteca\b|"
        r"\bmargarina\b|\bricota\b|\bcrema chantilly\b|\bpostre lacteo\b|\bflan\b|"
        r"\bla serenisima\b|\bsancor\b|\bmilkaut\b|\bilolay\b",
        "lacteos",
    ),
    # almacen (catch-all amplio: aceites, fideos, arroz, conservas, snacks, condimentos, azucar)
    (
        r"\bfideos?\b|\btallarines?\b|\bspaghetti\b|\bmostachol(es)?\b|\bravioles?\b|\bsorrentinos?\b|"
        r"\bnoquis?\b|\barroz\b|\baceite\b|\bvinagre\b|\bsal\b|\bazucar\b|\bedulcorante\b|\bharina\b|"
        r"\bpolent(a|as)\b|\bpure de tomate\b|\bsalsa\b|\bextracto de tomate\b|\btomate triturado\b|"
        r"\barvejas?\b|\bchoclo\b|\batun\b|\bsardin(a|as)\b|\bcaballa\b|\bpicadillo\b|\bmermelada\b|"
        r"\bdulce\b|\bcacao\b|\bchocolate\b|\bgolosin(a|as)\b|\balfajor(es)?\b|\bturron(es)?\b|"
        r"\bsnack\b|\bpapas fritas\b|\bpalitos\b|\bmani\b|\bpororo\b|\bgelatina\b|\bmayonesa\b|"
        r"\bketchup\b|\bmostaza\b|\baderezo\b|\bcondiment(o|os)\b|\boregano\b|\bpimienta\b",
        "almacen",
    ),
]


def _normalize(s: str) -> str:
    s = s.lower()
    # quitar tildes y reemplazar ñ -> n para matchear con patrones ASCII
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("ñ", "n")
    s = re.sub(r"\s+", " ", s)
    return s


# Capa 1
def categorize_keyword(descripcion: str | None) -> str | None:
    if not descripcion:
        return None
    text_low = _normalize(descripcion)
    for pattern, cat in KEYWORDS:
        if re.search(pattern, text_low):
            return cat
    return None


def _load_cache(engine: Engine) -> dict[str, str]:
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id_producto, categoria FROM categorias_cache")).fetchall()
    return {r[0]: r[1] for r in rows}


def _save_cache(engine: Engine, items: Iterable[tuple[str, str, str]]) -> None:
    now = datetime.utcnow().isoformat(timespec="seconds")
    with engine.begin() as conn:
        for id_p, cat, fuente in items:
            conn.execute(
                text(
                    "INSERT INTO categorias_cache(id_producto, categoria, fuente, actualizado_en) "
                    "VALUES (:i,:c,:f,:t) "
                    "ON CONFLICT(id_producto) DO UPDATE SET categoria=excluded.categoria, "
                    "fuente=excluded.fuente, actualizado_en=excluded.actualizado_en"
                ),
                {"i": id_p, "c": cat, "f": fuente, "t": now},
            )


def categorize_all(engine: Engine, *, use_llm: bool = True, batch_size: int = 50) -> dict[str, int]:
    """Categoriza todos los productos sin categoria. Devuelve conteo por fuente."""
    cache = _load_cache(engine)
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id_producto, descripcion FROM productos")).fetchall()

    stats = {"cache": 0, "keyword": 0, "llm": 0, "sin_clasificar": 0}
    nuevos: list[tuple[str, str, str]] = []
    pendientes: list[tuple[str, str]] = []

    for id_p, desc in rows:
        if id_p in cache:
            stats["cache"] += 1
            continue
        cat = categorize_keyword(desc)
        if cat is not None:
            nuevos.append((id_p, cat, "keyword"))
            stats["keyword"] += 1
        else:
            pendientes.append((id_p, desc or ""))

    if nuevos:
        _save_cache(engine, nuevos)

    if not pendientes:
        return stats

    if use_llm and os.getenv("ANTHROPIC_API_KEY"):
        try:
            llm_results = _llm_categorize(pendientes, batch_size=batch_size)
            _save_cache(engine, [(i, c, "llm") for i, c in llm_results.items()])
            stats["llm"] = len(llm_results)
            faltan = [p for p, _ in pendientes if p not in llm_results]
            if faltan:
                _save_cache(engine, [(i, "sin_clasificar", "fallback") for i in faltan])
                stats["sin_clasificar"] = len(faltan)
        except Exception as e:
            log.warning(f"capa 2 LLM fallo: {e}; marco sin_clasificar")
            _save_cache(engine, [(i, "sin_clasificar", "fallback") for i, _ in pendientes])
            stats["sin_clasificar"] = len(pendientes)
    else:
        if use_llm:
            log.info("ANTHROPIC_API_KEY no seteada; capa 2 saltada")
        _save_cache(engine, [(i, "sin_clasificar", "fallback") for i, _ in pendientes])
        stats["sin_clasificar"] = len(pendientes)

    return stats


def _llm_categorize(pendientes: list[tuple[str, str]], *, batch_size: int = 50) -> dict[str, str]:
    """Llama a Claude Haiku para categorizar productos en lote. Cacheable por EAN."""
    import anthropic

    client = anthropic.Anthropic()
    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    cats_csv = ", ".join(c for c in CATEGORIAS if c != "sin_clasificar")
    out: dict[str, str] = {}

    for i in range(0, len(pendientes), batch_size):
        chunk = pendientes[i : i + batch_size]
        items = [{"id": p, "desc": d} for p, d in chunk]
        prompt = (
            "Clasifica cada producto de supermercado argentino en UNA de estas categorias: "
            f"{cats_csv}. "
            "Si ninguna calza, devolve 'sin_clasificar'. "
            'Respondé SOLO con JSON array: [{"id":"...","cat":"..."}].\n\n'
            f"Productos:\n{json.dumps(items, ensure_ascii=False)}"
        )
        msg = client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        text_resp = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        try:
            start = text_resp.find("[")
            end = text_resp.rfind("]")
            parsed = json.loads(text_resp[start : end + 1])
            for row in parsed:
                cat = row.get("cat", "sin_clasificar")
                if cat not in CATEGORIAS:
                    cat = "sin_clasificar"
                out[row["id"]] = cat
        except Exception as e:
            log.warning(f"LLM batch {i} no parseable: {e}")
            continue

    return out
