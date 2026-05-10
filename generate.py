"""
Generador de Designaciones Multimedia SPLN

Lee data.json y produce index.html.

Uso:
    python generate.py

Para usar el mes que viene:
    1. Editar data.json (mes, año, días, notas, turnos)
    2. Correr `python generate.py`
    3. `git add . && git commit -m "Junio 2026" && git push`
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent
DATA = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))

ROLE_LABELS = [
    ("obs", "OBS", "obs"),
    ("cam1", "Cám 1", ""),
    ("cam2", "Cám 2", ""),
    ("proy1", "Proy 1", ""),
    ("proy2", "Proy 2", ""),
]


def render_dia(dia: dict, horarios: dict) -> str:
    es_domingo = dia["tipo"] == "domingo"
    nombre = "Domingo" if es_domingo else "Jueves"
    hora = horarios["horario_domingo" if es_domingo else "horario_jueves"]
    klass = "day-card sunday" if es_domingo else "day-card"

    roles_html = []
    for key, label, css in ROLE_LABELS:
        nombre_persona = dia["asignados"].get(key, "—")
        roles_html.append(
            f'<div class="role {css}"><div class="role-label">{label}</div>'
            f'<div class="role-name">{nombre_persona}</div></div>'
        )

    chips_html = "".join(
        f'<span class="chip">{n}</span>' for n in dia.get("disponibles", [])
    )

    return f"""    <div class="{klass}">
      <div class="day-header">
        <div><div class="day-name">{nombre}</div><span class="day-time">{hora}</span></div>
        <div class="day-date">{dia["fecha"]}</div>
      </div>
      <div class="roles">
        {''.join(roles_html)}
      </div>
      <div class="available">
        <div class="available-label">Disponibles para reemplazo</div>
        <div class="chips">{chips_html}</div>
      </div>
    </div>"""


def render_nota(nota: dict) -> str:
    return f"""      <div class="note">
        <span class="note-label">{nota["label"]}</span>
        <p class="note-text">{nota["texto"]}</p>
      </div>"""


def render_roster_row(p: dict) -> str:
    css = f" {p['estilo']}" if p.get("estilo") else ""
    return (
        f'        <div class="roster-row"><span class="roster-name">{p["nombre"]}</span>'
        f'<span class="roster-count{css}">{p["turnos"]}</span></div>'
    )


def build_html(data: dict) -> str:
    meta = data["meta"]
    titulo_mes = f'{meta["mes"]} {meta["anio"]}'
    horarios = {
        "horario_domingo": meta["horario_domingo"],
        "horario_jueves": meta["horario_jueves"],
    }

    dias_html = "\n\n".join(render_dia(d, horarios) for d in data["dias"])
    notas_html = "\n".join(render_nota(n) for n in data["notas"])
    roster_html = "\n".join(render_roster_row(p) for p in data["turnos_por_persona"])
    stats = meta["stats"]

    return TEMPLATE.format(
        titulo_mes=titulo_mes,
        mes=meta["mes"],
        anio=meta["anio"],
        verso=meta["verso"],
        ubicacion=meta["ubicacion"],
        cultos=stats["cultos"],
        servidores=stats["servidores"],
        roles=stats["roles"],
        turnos=stats["turnos"],
        dias_html=dias_html,
        notas_html=notas_html,
        roster_html=roster_html,
    )


TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5">
<meta name="theme-color" content="#1A2540">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="description" content="Designaciones del equipo Multimedia · Iglesia Sanidad Para Las Naciones · {titulo_mes}">
<meta property="og:title" content="Multimedia SPLN · {titulo_mes}">
<meta property="og:description" content="Designaciones del equipo Multimedia · Iglesia Sanidad Para Las Naciones">
<meta property="og:image" content="spln_logo.png">
<meta property="og:type" content="website">
<meta property="og:locale" content="es_AR">
<link rel="icon" type="image/png" href="spln_logo.png">
<link rel="apple-touch-icon" href="spln_logo.png">
<title>Multimedia SPLN · {titulo_mes}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Cormorant+Garamond:wght@400;500;600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --azul-logo: #101F92;
    --granate-logo: #9A2034;
    --marino: #1A2540;
    --marino-light: #2A3754;
    --celeste: #B8DCE6;
    --celeste-light: #D9EDF2;
    --aqua: #7FBFB0;
    --aqua-light: #B5D9CF;
    --crema: #FAF7F0;
    --gris-suave: #E0E6E8;
    --gris-card: #EFF3F4;
    --texto: #1A2540;
    --texto-tenue: #7A8794;
    --verde: #2D6E4E;
    --verde-light: #DCE9DF;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }}
  html, body {{ min-height: 100vh; overflow-x: hidden; }}
  body {{ font-family: 'Inter', -apple-system, sans-serif; color: var(--texto); line-height: 1.5; background: var(--crema); -webkit-font-smoothing: antialiased; }}
  .header {{ background: radial-gradient(ellipse at top right, var(--aqua-light) 0%, transparent 50%), radial-gradient(ellipse at bottom left, var(--celeste) 0%, transparent 50%), linear-gradient(160deg, var(--marino) 0%, var(--marino-light) 100%); color: white; padding: 36px 24px 32px; position: relative; overflow: hidden; text-align: center; }}
  .header::before {{ content: ""; position: absolute; top: -100px; right: -60px; width: 220px; height: 220px; background: radial-gradient(circle, rgba(127,191,176,0.4) 0%, transparent 60%); pointer-events: none; }}
  .header::after {{ content: ""; position: absolute; bottom: -80px; left: -40px; width: 180px; height: 180px; background: radial-gradient(circle, rgba(184,220,230,0.3) 0%, transparent 65%); pointer-events: none; }}
  .logo-circle {{ width: 140px; height: 140px; margin: 0 auto 18px; position: relative; z-index: 2; background: white; border-radius: 50%; padding: 12px; display: flex; align-items: center; justify-content: center; box-shadow: 0 14px 36px rgba(0,0,0,0.32), 0 0 0 4px rgba(255,255,255,0.18); }}
  .logo-circle img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
  .header-eyebrow {{ position: relative; z-index: 2; font-size: 9.5px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: var(--aqua-light); opacity: 0.95; margin-bottom: 10px; }}
  .header-title {{ position: relative; z-index: 2; font-family: 'Cinzel', serif; font-size: 28px; font-weight: 900; letter-spacing: 2px; line-height: 1; margin-bottom: 8px; color: white; }}
  .header-subtitle {{ position: relative; z-index: 2; font-family: 'Cormorant Garamond', serif; font-size: 18px; font-weight: 500; font-style: italic; color: var(--celeste-light); margin-bottom: 6px; }}
  .header-verse {{ position: relative; z-index: 2; font-family: 'Cormorant Garamond', serif; font-size: 13px; font-weight: 500; font-style: italic; color: rgba(255,255,255,0.75); margin-top: 10px; padding: 0 8px; }}
  .header-stats {{ position: relative; z-index: 2; display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; margin: 22px -8px 0; background: rgba(255,255,255,0.08); padding: 6px; border-radius: 14px; border: 1px solid rgba(184,220,230,0.20); backdrop-filter: blur(10px); }}
  .stat {{ padding: 12px 4px; text-align: center; }}
  .stat-num {{ font-family: 'Cinzel', serif; font-size: 22px; font-weight: 700; line-height: 1; margin-bottom: 3px; color: var(--celeste-light); }}
  .stat-label {{ font-size: 8px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: rgba(255,255,255,0.70); }}
  .body-wrap {{ padding: 22px 16px 32px; max-width: 480px; margin: 0 auto; }}
  .rule-box {{ background: linear-gradient(135deg, var(--celeste-light) 0%, white 100%); border-left: 4px solid var(--aqua); padding: 14px 18px; margin-bottom: 26px; border-radius: 10px; box-shadow: 0 2px 12px rgba(127,191,176,0.15); }}
  .rule-box strong {{ font-size: 9.5px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--aqua); display: block; margin-bottom: 5px; }}
  .rule-box p {{ font-family: 'Cormorant Garamond', serif; font-size: 15px; color: var(--marino); line-height: 1.45; }}
  .section-divider {{ display: flex; align-items: center; gap: 10px; margin: 6px 0 16px; }}
  .section-divider .line {{ flex: 1; height: 1px; background: linear-gradient(to right, transparent, var(--aqua), transparent); }}
  .section-divider .label {{ font-family: 'Cinzel', serif; font-size: 10px; font-weight: 700; letter-spacing: 2.5px; text-transform: uppercase; color: var(--marino); }}
  .day-card {{ background: white; border: 1.5px solid var(--gris-suave); border-radius: 14px; margin-bottom: 14px; overflow: hidden; position: relative; box-shadow: 0 2px 8px rgba(26,37,64,0.05); }}
  .day-card::before {{ content: ""; position: absolute; top: 0; left: 0; right: 0; height: 4px; background: linear-gradient(to right, var(--aqua), var(--celeste)); }}
  .day-card.sunday::before {{ background: linear-gradient(to right, var(--granate-logo), #c4374e); }}
  .day-header {{ display: flex; justify-content: space-between; align-items: baseline; padding: 16px 18px 12px; border-bottom: 1px solid var(--gris-suave); }}
  .day-name {{ font-family: 'Cinzel', serif; font-size: 17px; font-weight: 700; color: var(--aqua); line-height: 1; letter-spacing: 0.5px; }}
  .day-card.sunday .day-name {{ color: var(--granate-logo); }}
  .day-date {{ font-family: 'Cormorant Garamond', serif; font-size: 30px; font-weight: 700; color: var(--marino); line-height: 1; }}
  .day-time {{ display: block; font-size: 9px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--texto-tenue); margin-top: 4px; }}
  .roles {{ padding: 12px 14px 4px; display: grid; grid-template-columns: 1fr; gap: 6px; }}
  .role {{ display: grid; grid-template-columns: 70px 1fr; gap: 12px; align-items: center; padding: 10px 13px; background: var(--gris-card); border-radius: 7px; }}
  .role-label {{ font-size: 9.5px; font-weight: 800; letter-spacing: 1.3px; text-transform: uppercase; color: var(--texto-tenue); }}
  .role-name {{ font-family: 'Cormorant Garamond', serif; font-size: 17px; font-weight: 600; color: var(--marino); }}
  .role.obs {{ background: linear-gradient(135deg, var(--marino) 0%, var(--azul-logo) 100%); box-shadow: 0 3px 10px rgba(16, 31, 146, 0.30); }}
  .role.obs .role-label {{ color: var(--celeste-light); }}
  .role.obs .role-name {{ color: white; font-weight: 700; }}
  .available {{ padding: 12px 16px 14px; background: var(--verde-light); border-top: 1px dashed #b5cebd; }}
  .available-label {{ font-size: 9px; font-weight: 800; letter-spacing: 1.3px; text-transform: uppercase; color: var(--verde); display: flex; align-items: center; gap: 5px; margin-bottom: 8px; }}
  .available-label::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--verde); }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 5px; }}
  .chip {{ font-family: 'Cormorant Garamond', serif; font-size: 13.5px; font-weight: 600; padding: 3px 11px; background: white; color: var(--verde); border: 1px solid #b5cebd; border-radius: 12px; line-height: 1.3; }}
  .panel {{ background: white; border: 1.5px solid var(--gris-suave); border-radius: 14px; padding: 20px 22px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(26,37,64,0.04); }}
  .panel-title {{ font-family: 'Cinzel', serif; font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--marino); padding-bottom: 10px; margin-bottom: 14px; border-bottom: 1.5px solid var(--gris-suave); }}
  .note {{ margin-bottom: 14px; }} .note:last-child {{ margin-bottom: 0; }}
  .note-label {{ font-size: 10px; font-weight: 700; letter-spacing: 1.3px; text-transform: uppercase; color: var(--granate-logo); display: block; margin-bottom: 4px; }}
  .note-text {{ font-family: 'Cormorant Garamond', serif; font-size: 15px; color: var(--marino); line-height: 1.45; }}
  .roster-list {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px 18px; }}
  .roster-row {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px; padding: 5px 0; border-bottom: 1px dashed var(--gris-suave); }}
  .roster-name {{ font-family: 'Cormorant Garamond', serif; font-size: 15px; font-weight: 600; color: var(--marino); }}
  .roster-count {{ font-size: 11px; font-weight: 700; color: var(--marino); background: var(--celeste-light); padding: 2px 9px; border-radius: 10px; min-width: 26px; text-align: center; }}
  .roster-count.high {{ background: var(--marino); color: white; }}
  .roster-count.low {{ color: var(--texto-tenue); background: var(--gris-card); }}
  .footer {{ background: linear-gradient(135deg, var(--marino), var(--marino-light)); color: white; padding: 24px 24px; text-align: center; position: relative; overflow: hidden; }}
  .footer::before {{ content: ""; position: absolute; top: -50px; right: -30px; width: 120px; height: 120px; background: radial-gradient(circle, rgba(127,191,176,0.20) 0%, transparent 60%); }}
  .footer-divider {{ width: 50px; height: 2px; background: var(--aqua); margin: 0 auto 14px; position: relative; z-index: 2; }}
  .footer-text {{ position: relative; z-index: 2; font-family: 'Cinzel', serif; font-size: 10px; letter-spacing: 2.5px; text-transform: uppercase; color: var(--celeste-light); }}
  .footer-verse {{ position: relative; z-index: 2; display: block; margin-top: 12px; font-family: 'Cormorant Garamond', serif; font-size: 14px; font-style: italic; letter-spacing: 0.5px; color: white; }}
  @media (min-width: 768px) {{ .body-wrap {{ max-width: 560px; padding: 28px 24px 40px; }} .logo-circle {{ width: 160px; height: 160px; }} .header-title {{ font-size: 34px; }} .header-subtitle {{ font-size: 21px; }} .header {{ padding: 48px 32px 40px; }} }}
  @media (min-width: 1024px) {{ body {{ background: radial-gradient(ellipse at top left, var(--celeste-light) 0%, transparent 40%), radial-gradient(ellipse at bottom right, var(--aqua-light) 0%, transparent 40%), var(--crema); padding: 24px; }} .container {{ max-width: 620px; margin: 0 auto; background: white; border-radius: 24px; overflow: hidden; box-shadow: 0 24px 64px rgba(26,37,64,0.18); }} }}
</style>
</head>
<body>
<div class="container">
  <header class="header">
    <div class="logo-circle"><img src="spln_logo.png" alt="Iglesia Sanidad Para Las Naciones"></div>
    <div class="header-eyebrow">Sanidad Para Las Naciones</div>
    <h1 class="header-title">Multimedia</h1>
    <p class="header-subtitle">Designaciones · {titulo_mes}</p>
    <p class="header-verse">"{verso}"</p>
    <div class="header-stats">
      <div class="stat"><div class="stat-num">{cultos}</div><div class="stat-label">Cultos</div></div>
      <div class="stat"><div class="stat-num">{servidores}</div><div class="stat-label">Servidores</div></div>
      <div class="stat"><div class="stat-num">{roles}</div><div class="stat-label">Roles</div></div>
      <div class="stat"><div class="stat-num">{turnos}</div><div class="stat-label">Turnos</div></div>
    </div>
  </header>
  <div class="body-wrap">
    <div class="rule-box">
      <strong>Regla operativa</strong>
      <p>Si no podés estar en tu día, sos responsable de buscarte un reemplazo y avisar al líder. Los nombres en verde son quienes están disponibles para cubrir.</p>
    </div>
    <div class="section-divider"><div class="line"></div><div class="label">Calendario</div><div class="line"></div></div>
{dias_html}

    <div class="section-divider"><div class="line"></div><div class="label">Notas del mes</div><div class="line"></div></div>
    <div class="panel">
{notas_html}
    </div>
    <div class="section-divider"><div class="line"></div><div class="label">Turnos por persona</div><div class="line"></div></div>
    <div class="panel">
      <div class="roster-list">
{roster_html}
      </div>
    </div>
  </div>
  <footer class="footer">
    <div class="footer-divider"></div>
    <div class="footer-text">Equipo Multimedia · SPLN · {titulo_mes}</div>
    <span class="footer-verse">{ubicacion}</span>
  </footer>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    html = build_html(DATA)
    out = ROOT / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"OK · {out.name} generado · {len(html):,} chars · mes: {DATA['meta']['mes']} {DATA['meta']['anio']}")
