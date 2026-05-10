# Multimedia SPLN — Designaciones

Sitio web público con las designaciones del equipo de Multimedia de la Iglesia Sanidad Para Las Naciones (Olavarría).

🌐 **https://axelitoteca.github.io/spln-multimedia/**

---

## Cómo actualizar para el próximo mes (3 pasos)

### 1. Editar `data.json`

Abrir `data.json` y cambiar lo que corresponda al nuevo mes:

- `meta.mes` y `meta.anio`
- `meta.stats` (número de cultos, turnos, etc.)
- `dias[]` — lista de los cultos del mes con sus asignados y disponibles
- `notas[]` — notas del mes (Aramis, Jere, DEN, etc.)
- `turnos_por_persona[]` — conteo final por persona

### 2. Ejecutar `actualizar.bat`

Doble click en `actualizar.bat`. El script:

1. Regenera `index.html` con los datos nuevos
2. Pide un mensaje de commit (ej: "Junio 2026")
3. Hace `git commit` + `git push`

En 1-2 minutos el sitio público se actualiza solo.

### Alternativa manual

```bash
python generate.py
git add data.json index.html
git commit -m "Junio 2026"
git push
```

---

## Estructura del proyecto

| Archivo | Para qué |
|---|---|
| `data.json` | **Lo único que se edita mes a mes**. Estructura completa del mes. |
| `generate.py` | Lee `data.json` y genera `index.html`. **No editar a mano** salvo que cambie el diseño. |
| `index.html` | **Generado automáticamente**. No editar — se sobreescribe. |
| `spln_logo.png` | Logo histórico SPLN. Permanente. |
| `actualizar.bat` | One-click: regenera + commit + push. |

---

## Estructura de `data.json`

```json
{
  "meta": {
    "mes": "Junio",
    "anio": 2026,
    "horario_domingo": "10:00 hs",
    "horario_jueves": "20:00 hs",
    "verso": "La fe en el nombre de Jesús opera milagros",
    "ubicacion": "Olavarría · Buenos Aires · Argentina",
    "stats": { "cultos": 9, "servidores": 14, "roles": 5, "turnos": 45 }
  },
  "dias": [
    {
      "tipo": "domingo",
      "fecha": "07",
      "asignados": {
        "obs": "Nombre",
        "cam1": "Nombre",
        "cam2": "Nombre",
        "proy1": "Nombre",
        "proy2": "Nombre"
      },
      "disponibles": ["Persona1", "Persona2"]
    }
  ],
  "notas": [
    { "label": "Título corto", "texto": "Explicación..." }
  ],
  "turnos_por_persona": [
    { "nombre": "David", "turnos": 5, "estilo": "high" },
    { "nombre": "Juli",  "turnos": 4, "estilo": "" },
    { "nombre": "Ara",   "turnos": 2, "estilo": "low" }
  ]
}
```

**Campos clave:**

- `tipo`: `"domingo"` (header granate) o `"jueves"` (header aqua)
- `estilo` en turnos: `"high"` (azul fuerte, persona con más turnos) · `""` (normal) · `"low"` (gris, sub-utilizada)

---

## Reglas que ya están aplicadas

1. **OBS no se asigna a**: Rocío F., Luna, David Martínez (en formación). Cuando aprendan, se les puede dar OBS.
2. **Solapes con D.E.N.** (Departamento Escuela Niños): si alguien está designado en niños, no se le pone en multimedia ese día.
3. **Disponibilidad**: viene de la encuesta del Google Sheet del equipo.
4. **Aramis**: confirmar contra designaciones de música antes de oficializar.
5. **Regla operativa**: si alguien no puede ir, se busca su propio reemplazo (de la lista verde de cada día) y avisa al líder.

---

## Diseño

- **Logo histórico SPLN** (manos + paloma + lema circular + 9 rayos)
- **Paleta**: marino oscuro `#1A2540`, aqua menta `#7FBFB0`, celeste pastel `#B8DCE6`, cobalto `#101F92`, granate `#9A2034`
- **Tipografía**: Cinzel (display), Cormorant Garamond (body), Inter (UI)
- **Mobile-first** + responsive desktop
- **PWA-ready** (Add to Home Screen funciona bien en celu)
