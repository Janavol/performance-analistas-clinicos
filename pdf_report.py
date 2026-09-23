"""Geração do relatório em PDF — via WeasyPrint, renderizando o MESMO HTML/CSS
de `components.py` que a página Streamlit usa. Não é uma reimplementação
aproximada: é o navegador de PDF (WeasyPrint) desenhando o mesmo markup, com as
mesmas fontes (Fraunces/IBM Plex Mono) e os mesmos cartões — por isso o PDF é,
de fato, uma "fotografia" de cada seção da página, uma por página, em paisagem.
"""

from __future__ import annotations

from datetime import datetime

from weasyprint import HTML

import charts
import components

PAGE_CSS = """
@page { size: A4 landscape; margin: 0; }
html, body { margin:0; padding:0; background:#F6F4EE; }
.pdf-page { page-break-after: always; padding: 14mm; box-sizing: border-box; }
.pdf-page:last-child { page-break-after: auto; }
/* No PDF a sombra do CSS da web fica pesada (renderização diferente do
   navegador) — cartões se distinguem só pela borda, sem sombra. */
.tile, .analyst-card, .radar-card, .trend-card { box-shadow: none; }
.pdf-meta { color:#726B58; font-size:12px; margin:2px 0 10px; }
.pdf-table { width:100%; table-layout:fixed; border-collapse:collapse; font-size:6.6px; }
.pdf-table th {
    background:#0B6E5C; color:#FFFFFF; text-align:right; font-size:6.2px; text-transform:uppercase;
    letter-spacing:.02em; padding:4px 3px; border:0.5px solid #DFD8C8; word-wrap:break-word;
}
.pdf-table th:first-child, .pdf-table td.name-cell { text-align:left; width:9%; }
.pdf-table td { padding:3.5px 3px; border:0.5px solid #DFD8C8; text-align:right; font-family:'IBM Plex Mono', monospace; word-wrap:break-word; }
.pdf-table td.name-cell { font-family: Helvetica, Arial, sans-serif; font-weight:700; }
.pdf-table tr.team-row td { background:#E3F1EC; font-weight:700; }
.pdf-table td.class-cell { text-align:left; font-family: Helvetica, Arial, sans-serif; }
"""


def _fmt_pct(v):
    return "—" if v is None else f"{v*100:.1f}%"


def _fmt_score(v):
    return "—" if v is None else f"{v:.1f}"


def build_pdf(result: dict, config: dict, is_example: bool) -> bytes:
    t = result["team"]

    def pct(v):
        return _fmt_pct(v)

    def sc(v):
        return _fmt_score(v)

    pages = []

    # ---- página 1: cabeçalho + cartões (igual ao topo da página) ----
    now = datetime.now().strftime("%d/%m/%Y às %H:%M")
    gerado = f"Gerado em {now}" + ("  •  dados de exemplo" if is_example else "")
    main_tiles = [
        components.tile_html("Score final da equipe", sc(t["score_final"]), components.pill_html(t["classe"])),
        components.tile_html("Resultados críticos", t["rc_total"]),
        components.tile_html("Críticos notificados", pct(t["rc_notif_pct"])),
        components.tile_html("Notificados no prazo", pct(t["rc_prazo_pct"])),
        components.tile_html("PA no prazo", pct(t["pa"]["pct"])),
        components.tile_html("UI no prazo", pct(t["ui"]["pct"])),
        components.tile_html("UTI no prazo", pct(t["uti"]["pct"])),
    ]
    block_tiles = [
        components.tile_html("Score Críticos", sc(t["score_criticos"])),
        components.tile_html("Score Protocolos", sc(t["score_protocolos"])),
        components.tile_html("Score PA", sc(t["score_pa"])),
        components.tile_html("Score UI", sc(t["score_ui"])),
        components.tile_html("Score UTI Adulto", sc(t["score_uca"])),
    ]
    pages.append(
        '<div class="eyebrow">Análise automática de performance</div>'
        "<h1>Performance Analistas Clínicos</h1>"
        f'<div class="pdf-meta">{gerado}</div>'
        '<p class="lede">Calcula <b>notificação de resultados críticos</b>, <b>cumprimento de TAT</b> por protocolo '
        "(PA, UI, UTI, Sepse, Dor Torácica, AVE) e o <b>score final ponderado</b> de cada analista.</p>"
        f"{components.tiles_row_html(main_tiles)}"
        '<div class="section-caption">Score por bloco (equipe)</div>'
        f"{components.tiles_row_html(block_tiles)}"
    )

    # ---- página 2: gráfico de barras (largura total) ----
    rankable = [a for a in result["per_analyst"] if a["score_final"] is not None]
    bar_entries = [{"label": "Equipe", "value": t["score_final"], "classe": t["classe"]}] + [
        {"label": a["analista"], "value": a["score_final"], "classe": a["classe"]} for a in rankable
    ]
    if len(bar_entries) > 1:
        bar_png = charts.bar_chart_png(bar_entries, width=15, height=None)
        pages.append(
            "<h2>Score final por analista</h2>"
            f'<img src="data:image/png;base64,{components.img_b64(bar_png)}" style="width:100%;height:auto;margin-top:10px;">'
        )

    # ---- página(s) 3: radar — cartões individuais, igual à página ----
    radar_items = [{"name": "Equipe", "scores": t, "classe": t["classe"], "score_final": t["score_final"]}] + [
        {"name": a["analista"], "scores": a, "classe": a["classe"], "score_final": a["score_final"]}
        for a in result["per_analyst"]
    ]
    chunk_size = 15  # 3 linhas de 5 cartões — cartão um pouco menor que na tela para caber numa página só
    radar_chunks = [radar_items[i : i + chunk_size] for i in range(0, len(radar_items), chunk_size)]
    for idx, chunk in enumerate(radar_chunks):
        title = "Perfil por bloco — radar"
        if len(radar_chunks) > 1:
            title += f" ({idx+1}/{len(radar_chunks)})"
        pages.append(
            f"<h2>{title}</h2>"
            '<p class="section-caption">Cada eixo mostra o score (0–100, equivalente a % de cumprimento): '
            "Resultados críticos, Protocolos, Pronto atendimento, Unidades de Internação e UTI Adulto.</p>"
            f"{components.radar_grid_html(chunk, img_max_w='140px', chart_size=1.4)}"
        )

    # ---- páginas por analista — o mesmo cartão da tela ----
    for a in result["per_analyst"]:
        pages.append(components.analyst_card_html(a, t))

    # ---- tabela de detalhamento ----
    head_cols = [
        "Analista", "RC Total", "RC Notif.", "RC no Prazo", "PA no Prazo", "UI no Prazo", "UTI no Prazo",
        "Sepse no Prazo", "DT no Prazo", "AVE no Prazo", "Sc. Críticos", "Sc. Protocolos", "Sc. PA", "Sc. UI",
        "Sc. UCA", "Score Final", "Classificação",
    ]

    def row_html(a, team_row=False):
        cells = [
            a["analista"], a["rc_total"], pct(a["rc_notif_pct"]), pct(a["rc_prazo_pct"]),
            pct(a["pa"]["pct"]), pct(a["ui"]["pct"]), pct(a["uti"]["pct"]),
            pct(a["sepse"]["pct"]), pct(a["dt"]["pct"]), pct(a["ave"]["pct"]),
            sc(a["score_criticos"]), sc(a["score_protocolos"]), sc(a["score_pa"]),
            sc(a["score_ui"]), sc(a["score_uca"]), sc(a["score_final"]),
        ]
        classe = a["classe"] or "—"
        tds = f'<td class="name-cell">{cells[0]}</td>' + "".join(f"<td>{c}</td>" for c in cells[1:])
        tds += f'<td class="class-cell">{classe}</td>'
        row_class = ' class="team-row"' if team_row else ""
        return f"<tr{row_class}>{tds}</tr>"

    rows_html = row_html(t, team_row=True) + "".join(row_html(a) for a in result["per_analyst"])
    table_html = (
        "<h2>Detalhamento por analista</h2>"
        '<table class="pdf-table" style="margin-top:10px;"><thead><tr>'
        + "".join(f"<th>{c}</th>" for c in head_cols)
        + f"</tr></thead><tbody>{rows_html}</tbody></table>"
    )
    pages.append(table_html)

    body = "".join(f'<section class="pdf-page">{p}</section>' for p in pages)
    full_html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"{components.FONT_LINKS}"
        f"<style>{components.BASE_CSS}{PAGE_CSS}</style>"
        f"</head><body>{body}</body></html>"
    )

    return HTML(string=full_html).write_pdf()
