# Comparador de precios SEPA — Olavarría (MVP)

Pipeline Python que descarga la base SEPA del gobierno argentino, filtra por
sucursales en Olavarría (CP 7400, Buenos Aires) y genera un reporte por
categoría con el comercio más barato para cada producto.

> Este sub-proyecto convive en el mismo repo que el sitio de Multimedia SPLN
> (ver `README.md`). Vive bajo `src/precios/`.

## Instalación

```bash
pip install -e ".[dev]"
cp .env.example .env       # opcional: completar ANTHROPIC_API_KEY
```

Requiere Python 3.11+.

## Uso

```bash
# minorista, día de hoy
python -m precios.cli --fecha hoy --tipo minorista

# mayorista, sin LLM (capa 2 desactivada)
python -m precios.cli --fecha hoy --tipo mayorista --skip-llm

# fecha específica
python -m precios.cli --fecha 2026-05-19 --tipo minorista
```

Salidas:
- `data/raw/YYYY-MM-DD/sepa_<tipo>.zip` — cache local del ZIP (no se versiona).
- `data/precios.db` — SQLite con `comercios`, `sucursales`, `productos`, `precios`, `categorias_cache`.
- `output/reporte_YYYY-MM-DD.md` — reporte legible, agrupado por categoría.
- `output/reporte_YYYY-MM-DD.csv` — mismos datos en CSV.

## Cómo funciona

1. **Downloader** (`downloader.py`): pide el ZIP por día-de-la-semana al portal
   CKAN de Producción. Si falla, retrocede hasta 7 días. Valida tamaño > 10MB
   e integridad ZIP. Cachea bajo `data/raw/YYYY-MM-DD/` — re-correr el mismo
   día no re-descarga.
2. **ETL** (`etl.py`): abre el ZIP maestro y los sub-ZIPs por cadena, deriva
   el esquema del header de cada CSV (con aliases tolerantes a variantes),
   filtra sucursales con provincia `Buenos Aires` y (`codigo_postal == '7400'`
   o `localidad ILIKE '%olavarr%'`), e ingesta a SQLite. Idempotente por
   `(claves, fecha_dump)`.
3. **Categorizer** (`categorizer.py`):
   - Capa 1: diccionario de regex sobre la descripción del producto.
   - Capa 2: Claude Haiku en batches de 50 (cacheado por EAN para no
     re-clasificar nunca el mismo producto).
   - Sin `ANTHROPIC_API_KEY`, la capa 2 se saltea y los huérfanos quedan
     `sin_clasificar`.
4. **Reporter** (`reporter.py`): por cada producto calcula min/max sobre las
   sucursales de Olavarría, % de diferencia y ahorro absoluto. Muestra top
   20 por categoría y un resumen "compra en X (gana en N de M productos)".

## Esquema SQLite (consultable)

```sql
-- Productos en Olavarría con precio del día
SELECT * FROM precios p
JOIN sucursales s USING (id_comercio, id_sucursal)
WHERE s.codigo_postal LIKE '%7400%';
```

## Tests

```bash
pytest -x
```

Cubre downloader (con `httpx.MockTransport`), ETL (fixture ZIP sintético con
estructura sub-zip anidada), categorizador capa 1 determinístico y capa 2
con `anthropic` mockeado.

## Despliegue (Railway)

`Procfile` y `railway.toml` listos. Configurar el cron en Railway:
`Settings → Cron Schedule: 0 12 * * *` (12:00 UTC ≈ 09:00 ART).

## Limitaciones conocidas

- **Cobertura**: la obligación SEPA aplica solo a grandes superficies
  (Res. 12/2016 y normas asociadas). Cadenas mayoristas como **Maxiconsumo,
  Diarco, Yaguar** y locales chicos **probablemente no reporten** a SEPA, así
  que no aparecerán en el reporte aunque tengan sucursal en Olavarría.
- **Schema variable**: el portal CKAN renombra columnas ocasionalmente. El
  ETL deriva el header en runtime y mapea por alias; si una columna nueva
  aparece, agregar el alias en `etl.py:COL_ALIASES`.
- **URL del recurso**: el endpoint exacto puede cambiar cuando re-publican el
  dataset. Para forzar una URL específica, exportá `SEPA_MINORISTA_URL` o
  `SEPA_MAYORISTA_URL` apuntando al ZIP correcto.
- **Sin LLM, categorización parcial**: la capa 1 (keywords) cubre el grueso
  pero deja `sin_clasificar` a productos con descripciones atípicas. Activar
  `ANTHROPIC_API_KEY` para cobertura completa.
- **SQLite, no Postgres**: aceptable para el MVP en Railway con un disco
  persistente; para volumen nacional convendrá migrar a Postgres.
- **Solo CLI**: no hay frontend web; los reportes se consumen en `output/`.

## Estructura

```
src/precios/
  downloader.py    # descarga + cache
  etl.py           # SEPA -> SQLite (filtro Olavarría)
  categorizer.py   # keywords + Claude (opcional)
  reporter.py      # markdown + CSV
  cli.py           # entrypoint
  run.py           # alias `python -m precios.run`
tests/
  fixtures/build_fixture.py
  test_downloader.py / test_etl.py / test_categorizer.py / test_reporter.py
```
