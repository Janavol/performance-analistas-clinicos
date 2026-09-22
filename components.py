"""HTML/CSS compartilhado entre a página Streamlit (app.py) e o relatório em
PDF (pdf_report.py, via WeasyPrint). Fonte única de verdade: o PDF é uma
renderização real deste mesmo HTML/CSS, não uma reimplementação aproximada —
por isso os dois ficam pixel a pixel iguais."""

from __future__ import annotations

import base64

import charts
from insights import build_insight

FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700'
    '&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
)

# CSS puro (sem os seletores específicos do DOM do Streamlit — aqueles ficam
# só em app.py, adicionados por cima deste bloco comum).
BASE_CSS = """
body { background:#F6F4EE; color:#1E1B15; font-family: Helvetica, Arial, sans-serif; }
h1, h2, h3 { color:#1E1B15; font-family:'Fraunces', Georgia, serif; margin:0; }
.eyebrow { font-family:'IBM Plex Mono', monospace; font-size:12px; letter-spacing:.09em; text-transform:uppercase; color:#0B6E5C; font-weight:600; margin-bottom:2px; }
.lede { color:#726B58; font-size:15px; max-width:76ch; }
.pill { display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:700; font-family:'IBM Plex Mono', monospace; white-space:nowrap; }
.pill-Excelente { background:#E3F5EA; color:#0CA30C; }
.pill-Bom { background:#FBF0DE; color:#B4790A; }
.pill-Regular { background:#FBE6DC; color:#C1552C; }
.pill-Crítico { background:#FAE7E3; color:#D03B3B; }
.insight-box { background:#E3F1EC; border-left:3px solid #0B6E5C; border-radius:0 10px 10px 0; padding:12px 16px; margin-top:8px; width:100%; box-sizing:border-box; }
.insight-title { font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:#0B6E5C; font-weight:700; margin-bottom:4px; }
.insight-box p { margin:0; font-size:13px; line-height:1.55; color:#1E1B15; }
.radar-card { background:#F0ECE1; border:1px solid #DFD8C8; border-radius:12px; padding:10px 8px 12px; text-align:center; }
.radar-card-header { display:flex; align-items:baseline; justify-content:center; gap:6px; font-size:12.5px; font-weight:700; color:#1E1B15; margin-bottom:2px; }
.radar-card-score { font-family:'IBM Plex Mono', monospace; font-size:11.5px; font-weight:600; color:#726B58; }
.radar-card img { display:block; margin:0 auto; }
.tiles-row { display:flex; flex-wrap:wrap; gap:12px; margin:14px 0 22px; }
.tile {
    background:#FFFFFF; border:1px solid #DFD8C8; border-radius:12px; padding:16px;
    flex:1 1 150px; min-width:150px;
    box-shadow: 0 1px 2px rgba(30,27,21,0.06), 0 8px 24px -12px rgba(30,27,21,0.18);
}
.tile .t-label { font-size:11.5px; color:#726B58; text-transform:uppercase; letter-spacing:.06em; font-weight:600; margin-bottom:6px; }
.tile .t-value { font-family:'Fraunces', serif; font-size:28px; font-weight:600; color:#1E1B15; font-variant-numeric: tabular-nums; line-height:1.2; }
.tile .t-sub { margin-top:6px; }
.section-caption { color:#726B58; font-size:13px; margin:4px 0 10px; }
.analyst-card {
    background:#FFFFFF; border:1px solid #DFD8C8; border-radius:14px; padding:20px;
    box-shadow: 0 1px 2px rgba(30,27,21,0.06), 0 8px 24px -12px rgba(30,27,21,0.18);
}
.analyst-header { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:14px; }
.analyst-header h3 { font-family:'Fraunces', serif; font-size:19px; font-weight:600; margin:0; color:#1E1B15; }
.analyst-header .analyst-score { font-family:'IBM Plex Mono', monospace; font-size:15px; font-weight:600; color:#726B58; display:flex; align-items:center; gap:8px; }
.tiles-mini { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:18px; }
.tile-mini { background:#F0ECE1; border:1px solid #DFD8C8; border-radius:9px; padding:9px 11px; flex:1 1 120px; min-width:120px; box-sizing:border-box; }
.tile-mini .tm-label { font-size:10px; color:#726B58; text-transform:uppercase; letter-spacing:.05em; font-weight:600; margin-bottom:3px; }
.tile-mini .tm-value { font-family:'IBM Plex Mono', monospace; font-size:15px; font-weight:600; color:#1E1B15; }
/* display:table em vez de flex: dá largura definida e confiável às células
   (o WeasyPrint não resolve bem % / max-width dentro de flex-children sem
   largura explícita — imagens e texto transbordavam a coluna). */
.analyst-charts { display:table; width:100%; table-layout:fixed; border-spacing:16px 0; margin-bottom:18px; }
.analyst-chart-col {
    display:table-cell; width:50%;
    border:1px solid #DFD8C8; border-radius:10px; padding:14px; background:#F0ECE1;
    vertical-align:top; box-sizing:border-box;
}
.analyst-chart-col .chart-label { font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:#726B58; font-weight:600; margin-bottom:10px; }
.analyst-chart-col img { max-width:100%; height:auto; display:block; margin:0 auto; }
.radar-grid { display:flex; flex-wrap:wrap; gap:14px; }
.radar-grid > div { flex:1 1 170px; max-width:200px; box-sizing:border-box; }
.trend-grid { display:flex; flex-wrap:wrap; gap:14px; }
.trend-grid > div { flex:1 1 220px; max-width:250px; box-sizing:border-box; }
.trend-card { background:#F0ECE1; border:1px solid #DFD8C8; border-radius:12px; padding:10px 10px 12px; text-align:center; }
.trend-card-header { display:flex; align-items:baseline; justify-content:center; gap:6px; font-size:12.5px; font-weight:700; color:#1E1B15; margin-bottom:2px; }
.trend-card-score { font-family:'IBM Plex Mono', monospace; font-size:11.5px; font-weight:600; color:#726B58; }
.trend-delta { display:inline-block; font-family:'IBM Plex Mono', monospace; font-size:11px; font-weight:700; padding:2px 8px; border-radius:999px; margin-top:6px; }
.trend-delta-up { background:#E3F5EA; color:#0CA30C; }
.trend-delta-down { background:#FAE7E3; color:#D03B3B; }
.trend-delta-flat { background:#F0ECE1; color:#726B58; border:1px solid #DFD8C8; }
.trend-card img { display:block; margin:0 auto; }
"""

CLASS_CSS = {"Excelente": "pill-Excelente", "Bom": "pill-Bom", "Regular": "pill-Regular", "Crítico": "pill-Crítico"}


def img_b64(png_bytes: bytes) -> str:
    return base64.b64encode(png_bytes).decode("ascii")


def pill_html(classe: str | None) -> str:
    if not classe:
        return ""
    return f'<span class="pill {CLASS_CSS.get(classe, "")}">{classe}</span>'


def tile_html(label: str, value, sub: str = "") -> str:
    sub_html = f'<div class="t-sub">{sub}</div>' if sub else ""
    return f'<div class="tile"><div class="t-label">{label}</div><div class="t-value">{value}</div>{sub_html}</div>'


def tiles_row_html(tiles: list) -> str:
    return '<div class="tiles-row">' + "".join(tiles) + "</div>"


def radar_card_html(item: dict, img_max_w: str = "170px") -> str:
    png = charts.radar_chart_png(item["scores"], item["classe"], size=1.9)
    b64 = img_b64(png)
    score_txt = f"{item['score_final']:.1f}" if item.get("score_final") is not None else "—"
    pill = pill_html(item["classe"]) if item.get("classe") else '<span style="font-size:11px;color:#9a9282;">sem dados</span>'
    return (
        '<div class="radar-card">'
        f'<div class="radar-card-header"><span>{item["name"]}</span><span class="radar-card-score">{score_txt}</span></div>'
        f'<img src="data:image/png;base64,{b64}" style="width:100%;max-width:{img_max_w};height:auto;display:block;margin:0 auto;">'
        f'<div style="margin-top:6px;">{pill}</div>'
        "</div>"
    )


def radar_grid_html(items: list) -> str:
    return '<div class="radar-grid">' + "".join(radar_card_html(item) for item in items) + "</div>"


def delta_badge_html(delta) -> str:
    if delta is None:
        return ""
    if delta > 0.5:
        cls, sign = "trend-delta-up", "+"
    elif delta < -0.5:
        cls, sign = "trend-delta-down", ""
    else:
        cls, sign = "trend-delta-flat", "±"
    return f'<span class="trend-delta {cls}">{sign}{delta:.1f} pts</span>'


def trend_card_html(a: dict, x_labels: list, img_max_w: str = "220px") -> str:
    """a: item de temporal_engine.compute()["analysts"] — {analista, series, first, last, delta, classe_atual}."""
    values = a["series"]["Score Final"].tolist()
    png = charts.mini_trend_png(x_labels, values, classe=a.get("classe_atual"), width=2.6, height=1.7)
    b64 = img_b64(png)
    last_txt = f"{a['last']:.1f}" if a.get("last") is not None else "—"
    return (
        '<div class="trend-card">'
        f'<div class="trend-card-header"><span>{a["analista"]}</span><span class="trend-card-score">{last_txt}</span></div>'
        f'<img src="data:image/png;base64,{b64}" style="width:100%;max-width:{img_max_w};height:auto;">'
        f"{delta_badge_html(a.get('delta'))}"
        "</div>"
    )


def trend_grid_html(analysts: list, x_labels: list) -> str:
    return '<div class="trend-grid">' + "".join(trend_card_html(a, x_labels) for a in analysts) + "</div>"


def analyst_card_html(a: dict, t: dict) -> str:
    def pct(v):
        return f"{v*100:.1f}%" if v is not None else "—"

    def sc(v):
        return f"{v:.1f}" if v is not None else "—"

    stats = [
        ("RC Total", str(a["rc_total"])),
        ("RC Notificados", pct(a["rc_notif_pct"])),
        ("RC no Prazo", pct(a["rc_prazo_pct"])),
        ("PA no Prazo", pct(a["pa"]["pct"])),
        ("UI no Prazo", pct(a["ui"]["pct"])),
        ("UTI no Prazo", pct(a["uti"]["pct"])),
        ("Sc. Protocolos", sc(a["score_protocolos"])),
        ("Score Final", sc(a["score_final"])),
    ]
    mini_tiles = "".join(
        f'<div class="tile-mini"><div class="tm-label">{label}</div><div class="tm-value">{value}</div></div>'
        for label, value in stats
    )

    bar_png = charts.bar_chart_png(
        [
            {"label": "Equipe", "value": t["score_final"], "classe": t["classe"]},
            {"label": a["analista"], "value": a["score_final"], "classe": a["classe"]},
        ],
        width=4.6, height=1.7,
    )
    radar_png = charts.radar_compare_png(a, a["classe"], t, size=2.7)
    score_txt = sc(a["score_final"])
    pill = pill_html(a["classe"])
    insight = build_insight(a, t)

    return (
        '<div class="analyst-card">'
        f'<div class="analyst-header"><h3>{a["analista"]}</h3>'
        f'<span class="analyst-score">{score_txt} {pill}</span></div>'
        f'<div class="tiles-mini">{mini_tiles}</div>'
        '<div class="analyst-charts">'
        f'<div class="analyst-chart-col"><div class="chart-label">Score final vs. Equipe</div>'
        f'<img src="data:image/png;base64,{img_b64(bar_png)}" style="width:100%;max-width:420px;height:auto;display:block;margin:0 auto;">'
        f'<div class="insight-box"><div class="insight-title">Insight</div><p>{insight}</p></div>'
        "</div>"
        f'<div class="analyst-chart-col"><div class="chart-label">Perfil por bloco vs. Equipe</div>'
        f'<img src="data:image/png;base64,{img_b64(radar_png)}" style="width:100%;max-width:340px;height:auto;display:block;margin:0 auto;"></div>'
        "</div>"
        "</div>"
    )
