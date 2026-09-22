"""Geração do relatório em PDF (reportlab) — réplica fiel da página Streamlit:
mesmo cabeçalho, mesmos cards de indicadores, mesmos gráficos e mesma
disposição da análise por analista (insight abaixo do gráfico de barras,
ao lado do radar)."""

from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors as rl
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import charts
from insights import build_insight

PAGE_SIZE = landscape(A4)
PAGE_W, PAGE_H = PAGE_SIZE
MARGIN = 0.55 * inch
CONTENT_W = PAGE_W - 2 * MARGIN

# Paleta — mesmos tokens do app.py / charts.py
BG = rl.HexColor("#F6F4EE")
SURFACE = rl.HexColor("#FFFFFF")
SURFACE_ALT = rl.HexColor("#F0ECE1")
BORDER = rl.HexColor("#DFD8C8")
TEXT = rl.HexColor("#1E1B15")
TEXT_MUTED = rl.HexColor("#726B58")
ACCENT = rl.HexColor("#0B6E5C")
ACCENT_SOFT = rl.HexColor("#E3F1EC")

CLASS_RL_COLOR = {
    "Excelente": rl.HexColor("#0CA30C"),
    "Bom": rl.HexColor("#B4790A"),
    "Regular": rl.HexColor("#C1552C"),
    "Crítico": rl.HexColor("#D03B3B"),
}
CLASS_RL_SOFT = {
    "Excelente": rl.HexColor("#E3F5EA"),
    "Bom": rl.HexColor("#FBF0DE"),
    "Regular": rl.HexColor("#FBE6DC"),
    "Crítico": rl.HexColor("#FAE7E3"),
}

# Fontes nativas do reportlab como aproximação visual: Times (serifada) no
# lugar de Fraunces, Courier (monoespaçada) no lugar de IBM Plex Mono.
SERIF = "Times-Bold"
SERIF_REG = "Times-Roman"
MONO = "Courier"
MONO_BOLD = "Courier-Bold"
SANS = "Helvetica"
SANS_BOLD = "Helvetica-Bold"


def _class_color(classe):
    return CLASS_RL_COLOR.get(classe, ACCENT)


def _class_soft(classe):
    return CLASS_RL_SOFT.get(classe, ACCENT_SOFT)


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("Eyebrow", fontName=MONO_BOLD, fontSize=9, textColor=ACCENT, leading=11, spaceAfter=4))
    ss.add(ParagraphStyle("H1", fontName=SERIF, fontSize=24, textColor=TEXT, leading=28, spaceAfter=4))
    ss.add(ParagraphStyle("H2", fontName=SERIF, fontSize=15, textColor=TEXT, leading=18, spaceAfter=3))
    ss.add(ParagraphStyle("H3", fontName=SERIF, fontSize=13, textColor=TEXT, leading=16))
    ss.add(ParagraphStyle("Lede", fontName=SANS, fontSize=9.5, textColor=TEXT_MUTED, leading=14))
    ss.add(ParagraphStyle("Body", fontName=SANS, fontSize=9.5, textColor=TEXT, leading=13.5))
    ss.add(ParagraphStyle("Muted", fontName=SANS, fontSize=8.5, textColor=TEXT_MUTED, leading=11))
    ss.add(ParagraphStyle("TileLabel", fontName=SANS_BOLD, fontSize=7, textColor=TEXT_MUTED, leading=9))
    ss.add(ParagraphStyle("TileValue", fontName=SERIF, fontSize=17, textColor=TEXT, leading=20))
    ss.add(ParagraphStyle("StatLabel", fontName=SANS_BOLD, fontSize=6.5, textColor=TEXT_MUTED, leading=8))
    ss.add(ParagraphStyle("StatValue", fontName=MONO_BOLD, fontSize=11.5, textColor=TEXT, leading=14))
    ss.add(ParagraphStyle("ChartLabel", fontName=SANS_BOLD, fontSize=7.5, textColor=TEXT_MUTED, leading=10))
    ss.add(ParagraphStyle("Insight", fontName=SANS, fontSize=8.5, textColor=TEXT, leading=12.5))
    ss.add(ParagraphStyle("InsightTitle", fontName=MONO_BOLD, fontSize=7.5, textColor=ACCENT, leading=10))
    ss.add(ParagraphStyle("PillText", fontName=MONO_BOLD, fontSize=8, textColor=rl.white, leading=10, alignment=1))
    ss.add(ParagraphStyle("ScoreMono", fontName=MONO_BOLD, fontSize=11, textColor=TEXT_MUTED, leading=14))
    ss.add(ParagraphStyle("RadarCardName", fontName=SANS_BOLD, fontSize=8, textColor=TEXT, leading=10))
    ss.add(ParagraphStyle("RadarCardScore", fontName=MONO_BOLD, fontSize=9, textColor=TEXT_MUTED, leading=11))
    return ss


def _fmt_pct(v):
    return "—" if v is None else f"{v*100:.1f}%"


def _fmt_score(v):
    return "—" if v is None else f"{v:.1f}"


def _image_flowable(png_bytes: bytes, max_w, max_h) -> Image:
    from PIL import Image as PILImage

    pil = PILImage.open(io.BytesIO(png_bytes))
    ratio = pil.width / pil.height
    w, h = max_w, max_w / ratio
    if h > max_h:
        h = max_h
        w = max_h * ratio
    return Image(io.BytesIO(png_bytes), width=w, height=h)


def _pill(classe, styles, width=0.85 * inch):
    label = classe or "Sem classificação"
    t = Table([[Paragraph(label, styles["PillText"])]], colWidths=[width], rowHeights=[0.2 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _class_color(classe)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ROUNDEDCORNERS", [9, 9, 9, 9]),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return t


def _separated_cards(tiles, styles, w, gap):
    """tiles: [(label, value, extra_flowable_or_None), ...] — cartões brancos com
    borda, um por um (efeito de cartões separados, igual `.tile` do app.py)."""
    row_cells = []
    col_widths = []
    for i, (label, value, extra) in enumerate(tiles):
        content = [Paragraph(label.upper(), styles["TileLabel"]), Spacer(1, 5), Paragraph(str(value), styles["TileValue"])]
        if extra is not None:
            content.append(Spacer(1, 6))
            content.append(extra)
        card = Table([[c] for c in content], colWidths=[w - 20])
        card.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                    ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        row_cells.append(card)
        col_widths.append(w)
        if i < len(tiles) - 1:
            row_cells.append("")
            col_widths.append(gap)
    outer = Table([row_cells], colWidths=col_widths)
    outer.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return outer


def _mini_tiles_rows(stats: list[tuple[str, str]], styles, cols=4, gap=6, row_gap=6) -> list:
    """Retorna uma lista de flowables (uma Table auto-dimensionada por linha,
    com um Spacer entre elas) — evitar uma única Table com rowHeights fixos,
    que corta/sobrepõe o conteúdo quando o texto não cabe na altura forçada."""
    w = (CONTENT_W - gap * (cols - 1)) / cols
    flowables = []
    for start in range(0, len(stats), cols):
        chunk = stats[start : start + cols]
        row_cells, col_widths = [], []
        for i, (label, value) in enumerate(chunk):
            card = Table(
                [[Paragraph(label.upper(), styles["StatLabel"])], [Paragraph(value, styles["StatValue"])]],
                colWidths=[w - 16],
            )
            card.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), SURFACE_ALT),
                        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ]
                )
            )
            row_cells.append(card)
            col_widths.append(w)
            if i < len(chunk) - 1:
                row_cells.append("")
                col_widths.append(gap)
        row_t = Table([row_cells], colWidths=col_widths)
        row_t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        flowables.append(row_t)
        flowables.append(Spacer(1, row_gap))
    return flowables


def _radar_card(item, styles, card_w):
    png = charts.radar_chart_png(item["scores"], item["classe"], size=1.7)
    img = _image_flowable(png, card_w - 16, card_w - 16)
    score_txt = _fmt_score(item.get("score_final"))
    header = Table(
        [[Paragraph(item["name"], styles["RadarCardName"]), Paragraph(score_txt, styles["RadarCardScore"])]],
        colWidths=[(card_w - 16) * 0.66, (card_w - 16) * 0.34],
    )
    header.setStyle(TableStyle([("ALIGN", (1, 0), (1, 0), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    pill = _pill(item.get("classe"), styles, width=0.8 * inch) if item.get("classe") else Paragraph("sem dados", styles["Muted"])
    rows = [[header], [img], [pill]]
    card = Table(rows, colWidths=[card_w - 16])
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE_ALT),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return card


def _radar_cards_grid(items, styles, cols=5, gap=8):
    card_w = (CONTENT_W - gap * (cols - 1)) / cols
    rows_out = []
    for start in range(0, len(items), cols):
        chunk = items[start : start + cols]
        row_cells, col_widths = [], []
        for i, item in enumerate(chunk):
            row_cells.append(_radar_card(item, styles, card_w))
            col_widths.append(card_w)
            if i < len(chunk) - 1:
                row_cells.append("")
                col_widths.append(gap)
        while len(row_cells) < cols * 2 - 1:
            row_cells.append("")
            col_widths.append(gap if len(row_cells) % 2 == 1 else card_w)
        rows_out.append(row_cells)
    t = Table(rows_out, colWidths=col_widths)
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), gap), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def build_pdf(result: dict, config: dict, is_example: bool) -> bytes:
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=PAGE_SIZE, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN,
        title="Performance Analistas Clínicos",
    )
    story = []
    t = result["team"]

    # ---- cabeçalho (igual ao topo da página) ----
    story.append(Paragraph("ANÁLISE AUTOMÁTICA DE PERFORMANCE", styles["Eyebrow"]))
    story.append(Paragraph("Performance Analistas Clínicos", styles["H1"]))
    now = datetime.now().strftime("%d/%m/%Y às %H:%M")
    gerado = f"Gerado em {now}" + ("  •  dados de exemplo" if is_example else "")
    story.append(Paragraph(gerado, styles["Muted"]))
    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            "Calcula <b>notificação de resultados críticos</b>, <b>cumprimento de TAT</b> por protocolo "
            "(PA, UI, UTI, Sepse, Dor Torácica, AVE) e o <b>score final ponderado</b> de cada analista.",
            styles["Lede"],
        )
    )
    story.append(Spacer(1, 14))

    # ---- tiles principais ----
    pill_flowable = _pill(t["classe"], styles) if t["classe"] else None
    main_tiles = [
        ("Score final da equipe", _fmt_score(t["score_final"]), pill_flowable),
        ("Resultados críticos", str(t["rc_total"]), None),
        ("Críticos notificados", _fmt_pct(t["rc_notif_pct"]), None),
        ("Notificados no prazo", _fmt_pct(t["rc_prazo_pct"]), None),
        ("PA no prazo", _fmt_pct(t["pa"]["pct"]), None),
        ("UI no prazo", _fmt_pct(t["ui"]["pct"]), None),
        ("UTI no prazo", _fmt_pct(t["uti"]["pct"]), None),
    ]
    story.append(_separated_cards(main_tiles, styles, (CONTENT_W - 6 * 6) / 7, 6))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Score por bloco (equipe)", styles["Muted"]))
    story.append(Spacer(1, 6))
    block_tiles = [
        ("Score Críticos", _fmt_score(t["score_criticos"]), None),
        ("Score Protocolos", _fmt_score(t["score_protocolos"]), None),
        ("Score PA", _fmt_score(t["score_pa"]), None),
        ("Score UI", _fmt_score(t["score_ui"]), None),
        ("Score UTI Adulto", _fmt_score(t["score_uca"]), None),
    ]
    story.append(_separated_cards(block_tiles, styles, (CONTENT_W - 4 * 8) / 5, 8))

    story.append(PageBreak())

    # ---- gráfico de barras (largura total) ----
    rankable = [a for a in result["per_analyst"] if a["score_final"] is not None]
    bar_entries = [{"label": "Equipe", "value": t["score_final"], "classe": t["classe"]}] + [
        {"label": a["analista"], "value": a["score_final"], "classe": a["classe"]} for a in rankable
    ]
    if len(bar_entries) > 1:
        story.append(Paragraph("Score final por analista", styles["H2"]))
        png = charts.bar_chart_png(bar_entries, width=CONTENT_W / inch * 1.4, height=None)
        story.append(_image_flowable(png, CONTENT_W, PAGE_H - 2.4 * inch))

    story.append(PageBreak())

    # ---- radar — cards individuais, igual à página ----
    radar_items = [{"name": "Equipe", "scores": t, "classe": t["classe"], "score_final": t["score_final"]}] + [
        {"name": a["analista"], "scores": a, "classe": a["classe"], "score_final": a["score_final"]}
        for a in result["per_analyst"]
    ]
    chunk_size = 15
    chunks = [radar_items[i : i + chunk_size] for i in range(0, len(radar_items), chunk_size)]
    for idx, chunk in enumerate(chunks):
        title = "Perfil por bloco — radar"
        if len(chunks) > 1:
            title += f" ({idx+1}/{len(chunks)})"
        story.append(Paragraph(title, styles["H2"]))
        story.append(
            Paragraph(
                "Cada eixo mostra o score (0–100, equivalente a % de cumprimento): Resultados críticos, "
                "Protocolos, Pronto atendimento, Unidades de Internação e UTI Adulto.",
                styles["Muted"],
            )
        )
        story.append(Spacer(1, 8))
        story.append(_radar_cards_grid(chunk, styles, cols=5))
        story.append(PageBreak())

    # ---- páginas por analista ----
    for a in result["per_analyst"]:
        header_tbl = Table(
            [[Paragraph(a["analista"], styles["H1"]), _pill(a["classe"], styles, width=1.1 * inch)]],
            colWidths=[CONTENT_W - 1.3 * inch, 1.3 * inch],
        )
        header_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
        story.append(header_tbl)
        story.append(
            Paragraph(
                f"Score final: {_fmt_score(a['score_final'])}   ·   Comparado à Equipe ({_fmt_score(t['score_final'])})",
                styles["Muted"],
            )
        )
        story.append(Spacer(1, 10))

        stats = [
            ("RC Total", str(a["rc_total"])),
            ("RC Notificados", _fmt_pct(a["rc_notif_pct"])),
            ("RC no Prazo", _fmt_pct(a["rc_prazo_pct"])),
            ("PA no Prazo", _fmt_pct(a["pa"]["pct"])),
            ("UI no Prazo", _fmt_pct(a["ui"]["pct"])),
            ("UTI no Prazo", _fmt_pct(a["uti"]["pct"])),
            ("Sc. Protocolos", _fmt_score(a["score_protocolos"])),
            ("Score Final", _fmt_score(a["score_final"])),
        ]
        story.extend(_mini_tiles_rows(stats, styles, cols=4))
        story.append(Spacer(1, 6))

        col_w = (CONTENT_W - 0.25 * inch) / 2
        bar_png = charts.bar_chart_png(
            [
                {"label": "Equipe", "value": t["score_final"], "classe": t["classe"]},
                {"label": a["analista"], "value": a["score_final"], "classe": a["classe"]},
            ],
            width=col_w / inch,
            height=1.7,
        )
        radar_png = charts.radar_compare_png(a, a["classe"], t, size=col_w / inch)
        insight_text = build_insight(a, t)
        insight_box = Table(
            [[Paragraph("INSIGHT", styles["InsightTitle"])], [Paragraph(insight_text, styles["Insight"])]],
            colWidths=[col_w - 20],
        )
        insight_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), ACCENT_SOFT),
                    ("LINEBEFORE", (0, 0), (0, -1), 2.2, ACCENT),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, 0), 7),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
                ]
            )
        )
        left_col = Table(
            [
                [Paragraph("SCORE FINAL VS. EQUIPE", styles["ChartLabel"])],
                [_image_flowable(bar_png, col_w - 20, 1.9 * inch)],
                [Spacer(1, 8)],
                [insight_box],
            ],
            colWidths=[col_w - 20],
        )
        left_col.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        right_col = Table(
            [
                [Paragraph("PERFIL POR BLOCO VS. EQUIPE", styles["ChartLabel"])],
                [_image_flowable(radar_png, col_w - 20, 2.6 * inch)],
            ],
            colWidths=[col_w - 20],
        )
        right_col.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))

        for col in (left_col, right_col):
            col_wrap = Table([[col]], colWidths=[col_w])
            col_wrap.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), SURFACE_ALT),
                        ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ]
                )
            )
            if col is left_col:
                left_wrapped = col_wrap
            else:
                right_wrapped = col_wrap

        charts_row = Table([[left_wrapped, "", right_wrapped]], colWidths=[col_w, 0.25 * inch, col_w])
        charts_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        story.append(charts_row)
        story.append(PageBreak())

    # ---- tabela de detalhamento ----
    story.append(Paragraph("Detalhamento por analista", styles["H2"]))
    head = [
        "Analista", "RC Total", "RC Notif.", "RC no Prazo", "PA no Prazo", "UI no Prazo", "UTI no Prazo",
        "Sepse no Prazo", "DT no Prazo", "AVE no Prazo", "Sc. Críticos", "Sc. Protocolos", "Sc. PA", "Sc. UI",
        "Sc. UCA", "Score Final", "Classificação",
    ]

    def row_of(a):
        return [
            a["analista"], a["rc_total"], _fmt_pct(a["rc_notif_pct"]), _fmt_pct(a["rc_prazo_pct"]),
            _fmt_pct(a["pa"]["pct"]), _fmt_pct(a["ui"]["pct"]), _fmt_pct(a["uti"]["pct"]),
            _fmt_pct(a["sepse"]["pct"]), _fmt_pct(a["dt"]["pct"]), _fmt_pct(a["ave"]["pct"]),
            _fmt_score(a["score_criticos"]), _fmt_score(a["score_protocolos"]), _fmt_score(a["score_pa"]),
            _fmt_score(a["score_ui"]), _fmt_score(a["score_uca"]), _fmt_score(a["score_final"]), a["classe"] or "—",
        ]

    body = [row_of(t)] + [row_of(a) for a in result["per_analyst"]]
    table_data = [head] + body
    tbl = Table(table_data, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl.white),
        ("FONTNAME", (0, 0), (-1, -1), SANS),
        ("FONTSIZE", (0, 0), (-1, -1), 6.8),
        ("FONTNAME", (0, 0), (-1, 0), SANS_BOLD),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 1), (-1, 1), ACCENT_SOFT),
        ("FONTNAME", (0, 1), (-1, 1), SANS_BOLD),
    ]
    tbl.setStyle(TableStyle(style))
    story.append(tbl)

    doc.build(story)
    buf.seek(0)
    return buf.read()
