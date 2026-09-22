"""PDF da análise por temporalidade — mesmo método do pdf_report.py: monta um
HTML usando os componentes de components.py e renderiza via WeasyPrint, uma
seção por página, em paisagem."""

from __future__ import annotations

from datetime import datetime

from weasyprint import HTML

import charts
import components
import temporal_engine as te

PAGE_CSS = """
@page { size: A4 landscape; margin: 0; }
html, body { margin:0; padding:0; background:#F6F4EE; }
.pdf-page { page-break-after: always; padding: 14mm; box-sizing: border-box; }
.pdf-page:last-child { page-break-after: auto; }
/* No PDF a sombra do CSS da web fica pesada (renderização diferente do
   navegador) — cartões se distinguem só pela borda, sem sombra. */
.tile, .analyst-card, .radar-card, .trend-card { box-shadow: none; }
.pdf-meta { color:#726B58; font-size:12px; margin:2px 0 10px; }
.pdf-table { width:100%; table-layout:fixed; border-collapse:collapse; font-size:9px; }
.pdf-table th {
    background:#0B6E5C; color:#FFFFFF; text-align:right; font-size:8.5px; text-transform:uppercase;
    letter-spacing:.02em; padding:5px 4px; border:0.5px solid #DFD8C8; word-wrap:break-word;
}
.pdf-table th:first-child, .pdf-table td.name-cell { text-align:left; width:16%; }
.pdf-table td { padding:4.5px 4px; border:0.5px solid #DFD8C8; text-align:right; font-family:'IBM Plex Mono', monospace; word-wrap:break-word; }
.pdf-table td.name-cell { font-family: Helvetica, Arial, sans-serif; font-weight:700; }
"""

BLOCK_COLS = [
    ("Score Res. Críticos", "Críticos"),
    ("Score Protocolos", "Protocolos"),
    ("Score PA", "PA"),
    ("Score UI", "UI"),
    ("Score UCA", "UTI Adulto"),
]


def build_pdf(result: dict) -> bytes:
    periods = result["periods"]
    team_df = result["team_df"]
    last_row = team_df.dropna(subset=["Score Final"])
    team_classe = last_row["Classificação"].iloc[-1] if len(last_row) else None

    def sc(v):
        return f"{v:.1f}" if v is not None else "—"

    def delta_txt(v):
        return f"{v:+.1f}" if v is not None else "—"

    pages = []

    # ---- página 1: cabeçalho + cartões ----
    now = datetime.now().strftime("%d/%m/%Y às %H:%M")
    tiles = [
        components.tile_html("Períodos analisados", len(periods)),
        components.tile_html("Score inicial da equipe", sc(result["team_first"])),
        components.tile_html("Score atual da equipe", sc(result["team_last"]), components.pill_html(team_classe)),
        components.tile_html("Variação da equipe", delta_txt(result["team_delta"])),
        components.tile_html("Analistas comparados", len(result["analysts"])),
    ]
    team_png = charts.trend_line_png(
        periods, [{"label": "Equipe", "values": team_df["Score Final"].tolist(), "color": charts.COLORS["accent"]}],
        width=11, height=3.0, show_legend=False,
    )
    pages.append(
        '<div class="eyebrow">Comparativo entre períodos</div>'
        "<h1>Análise por Temporalidade</h1>"
        f'<div class="pdf-meta">Gerado em {now}  •  Períodos: {", ".join(periods)}</div>'
        '<p class="lede">Evolução do score final da equipe e de cada analista entre os períodos enviados.</p>'
        f"{components.tiles_row_html(tiles)}"
        f'<div class="insight-box" style="margin-top:14px;"><div class="insight-title">Insight</div>'
        f"<p>{te.build_temporal_insight(result)}</p></div>"
        '<h2 style="margin-top:16px;">Evolução do score da equipe</h2>'
        f'<img src="data:image/png;base64,{components.img_b64(team_png)}" style="width:100%;height:auto;margin-top:6px;">'
    )

    # ---- página 3: evolução por bloco ----
    block_series = [{"label": label, "values": team_df[col].tolist()} for col, label in BLOCK_COLS]
    block_png = charts.trend_line_png(periods, block_series, width=11, height=3.6)
    pages.append(
        "<h2>Evolução por bloco (equipe)</h2>"
        f'<img src="data:image/png;base64,{components.img_b64(block_png)}" style="width:100%;height:auto;margin-top:10px;">'
    )

    # ---- página(s) 4: evolução individual — cartões pequenos ----
    analysts = result["analysts"]
    chunk_size = 12
    chunks = [analysts[i : i + chunk_size] for i in range(0, len(analysts), chunk_size)]
    for idx, chunk in enumerate(chunks):
        title = "Evolução individual por analista"
        if len(chunks) > 1:
            title += f" ({idx+1}/{len(chunks)})"
        pages.append(f"<h2>{title}</h2>" + components.trend_grid_html(chunk, periods))

    # ---- tabela comparativa ----
    head = ["Analista"] + periods
    rows_html = ""
    for a in analysts:
        s = a["series"].set_index(te.PERIOD_COL)["Score Final"]
        cells = "".join(f"<td>{sc(s.get(p))}</td>" for p in periods)
        rows_html += f'<tr><td class="name-cell">{a["analista"]}</td>{cells}</tr>'
    table_html = (
        "<h2>Tabela comparativa — Score Final por período</h2>"
        '<table class="pdf-table" style="margin-top:10px;"><thead><tr>'
        + "".join(f"<th>{c}</th>" for c in head)
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
