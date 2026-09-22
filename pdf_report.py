"""Geração do relatório em PDF (reportlab)."""

from __future__ import annotations

import io
import math
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

ACCENT = rl.HexColor("#0B6E5C")
ACCENT_SOFT = rl.HexColor("#E3F1EC")
TEXT = rl.HexColor("#1E1B15")
TEXT_MUTED = rl.HexColor("#726B58")
BORDER = rl.HexColor("#DDD8CC")
SURFACE_ALT = rl.HexColor("#F0ECE1")

CLASS_RL_COLOR = {
    "Excelente": rl.HexColor("#0CA30C"),
    "Bom": rl.HexColor("#B4790A"),
    "Regular": rl.HexColor("#C1552C"),
    "Crítico": rl.HexColor("#D03B3B"),
}


def _class_color(classe):
    return CLASS_RL_COLOR.get(classe, ACCENT)


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("H1", parent=ss["Heading1"], fontSize=20, textColor=TEXT, spaceAfter=4))
    ss.add(ParagraphStyle("H2", parent=ss["Heading2"], fontSize=14, textColor=TEXT, spaceAfter=6))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=10, textColor=TEXT, leading=14))
    ss.add(ParagraphStyle("Muted", parent=ss["Normal"], fontSize=9, textColor=TEXT_MUTED, leading=12))
    ss.add(ParagraphStyle("StatLabel", parent=ss["Normal"], fontSize=7.5, textColor=TEXT_MUTED, leading=9))
    ss.add(ParagraphStyle("StatValue", parent=ss["Normal"], fontSize=13, textColor=TEXT, leading=16, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("Insight", parent=ss["Normal"], fontSize=9.5, textColor=TEXT, leading=14))
    ss.add(ParagraphStyle("InsightTitle", parent=ss["Normal"], fontSize=8.5, textColor=ACCENT, leading=11, fontName="Helvetica-Bold"))
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


def _stat_cards_table(stats: list[tuple[str, str]], styles, cols=4, cell_w=None) -> Table:
    cell_w = cell_w or (PAGE_W - 2 * MARGIN) / cols
    data = []
    row = []
    for i, (label, value) in enumerate(stats):
        p = Paragraph(f"<font color='#726B58' size=7.5>{label}</font><br/><b><font size=13>{value}</font></b>", styles["Body"])
        row.append(p)
        if len(row) == cols:
            data.append(row)
            row = []
    if row:
        while len(row) < cols:
            row.append("")
        data.append(row)
    t = Table(data, colWidths=[cell_w] * cols, rowHeights=0.55 * inch)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE_ALT),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def _class_pill(classe, styles):
    color = _class_color(classe)
    label = classe or "Sem classificação"
    t = Table([[Paragraph(f"<font color='white'><b>{label}</b></font>", styles["Body"])]], colWidths=[1.3 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), color),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ROUNDEDCORNERS", [8, 8, 8, 8]),
            ]
        )
    )
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
    content_w = PAGE_W - 2 * MARGIN

    # ---- cover + summary ----
    story.append(Paragraph("Performance Analistas Clínicos", styles["H1"]))
    now = datetime.now().strftime("%d/%m/%Y às %H:%M")
    sub = f"Gerado em {now}" + ("  •  dados de exemplo" if is_example else "")
    story.append(Paragraph(sub, styles["Muted"]))
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            f"<b>Score final da equipe:</b> {_fmt_score(t['score_final'])} ({t['classe'] or '—'})<br/>"
            f"<b>Resultados críticos:</b> {t['rc_total']}  |  Notificados: {_fmt_pct(t['rc_notif_pct'])}  |  "
            f"Notificados no prazo: {_fmt_pct(t['rc_prazo_pct'])}<br/>"
            f"PA no prazo: {_fmt_pct(t['pa']['pct'])}   UI no prazo: {_fmt_pct(t['ui']['pct'])}   "
            f"UTI no prazo: {_fmt_pct(t['uti']['pct'])}   Sepse no prazo: {_fmt_pct(t['sepse']['pct'])}   "
            f"Dor torácica no prazo: {_fmt_pct(t['dt']['pct'])}   AVE no prazo: {_fmt_pct(t['ave']['pct'])}",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 16))

    # ---- bar chart ----
    rankable = [a for a in result["per_analyst"] if a["score_final"] is not None]
    bar_entries = [{"label": "Equipe", "value": t["score_final"], "classe": t["classe"]}] + [
        {"label": a["analista"], "value": a["score_final"], "classe": a["classe"]} for a in rankable
    ]
    if len(bar_entries) > 1:
        story.append(Paragraph("Score final por analista", styles["H2"]))
        png = charts.bar_chart_png(bar_entries, width=content_w / inch, height=None)
        story.append(_image_flowable(png, content_w, PAGE_H - 2.6 * inch))

    story.append(PageBreak())

    # ---- radar grid ----
    radar_items = [{"name": "Equipe", "scores": t, "classe": t["classe"], "score_final": t["score_final"]}] + [
        {"name": a["analista"], "scores": a, "classe": a["classe"], "score_final": a["score_final"]}
        for a in result["per_analyst"]
    ]
    chunk_size = 12
    chunks = [radar_items[i : i + chunk_size] for i in range(0, len(radar_items), chunk_size)]
    for idx, chunk in enumerate(chunks):
        title = "Perfil por bloco — radar"
        if len(chunks) > 1:
            title += f" ({idx+1}/{len(chunks)})"
        story.append(Paragraph(title, styles["H2"]))
        story.append(
            Paragraph(
                "Cada eixo mostra o score (0–100, equivalente a % de cumprimento): Críticos, Protocolos, PA, UI, UTI.",
                styles["Muted"],
            )
        )
        story.append(Spacer(1, 6))
        png = charts.radar_grid_png(chunk, cols=4)
        story.append(_image_flowable(png, content_w, PAGE_H - 2.2 * inch))
        story.append(PageBreak())

    # ---- per-analyst pages ----
    for a in result["per_analyst"]:
        header_tbl = Table(
            [[Paragraph(a["analista"], styles["H1"]), _class_pill(a["classe"], styles)]],
            colWidths=[content_w - 1.4 * inch, 1.4 * inch],
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
            ("RC TOTAL", str(a["rc_total"])),
            ("RC NOTIFICADOS", _fmt_pct(a["rc_notif_pct"])),
            ("RC NO PRAZO", _fmt_pct(a["rc_prazo_pct"])),
            ("PA NO PRAZO", _fmt_pct(a["pa"]["pct"])),
            ("UI NO PRAZO", _fmt_pct(a["ui"]["pct"])),
            ("UTI NO PRAZO", _fmt_pct(a["uti"]["pct"])),
            ("SC. PROTOCOLOS", _fmt_score(a["score_protocolos"])),
            ("SCORE FINAL", _fmt_score(a["score_final"])),
        ]
        story.append(_stat_cards_table(stats, styles, cols=4))
        story.append(Spacer(1, 14))

        col_w = (content_w - 0.25 * inch) / 2
        bar_png = charts.bar_chart_png(
            [
                {"label": "Equipe", "value": t["score_final"], "classe": t["classe"]},
                {"label": a["analista"], "value": a["score_final"], "classe": a["classe"]},
            ],
            width=col_w / inch,
            height=1.7,
        )
        radar_png = charts.radar_compare_png(a, a["classe"], t, size=col_w / inch)
        charts_tbl = Table(
            [
                [Paragraph("Score final vs. Equipe", styles["Muted"]), Paragraph("Perfil por bloco vs. Equipe", styles["Muted"])],
                [
                    _image_flowable(bar_png, col_w, 1.9 * inch),
                    _image_flowable(radar_png, col_w, 2.3 * inch),
                ],
            ],
            colWidths=[col_w, col_w],
        )
        charts_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 1), (-1, 1), 6)]))
        story.append(charts_tbl)
        story.append(Spacer(1, 14))

        insight_text = build_insight(a, t)
        insight_tbl = Table(
            [[Paragraph("INSIGHT AUTOMÁTICO", styles["InsightTitle"])], [Paragraph(insight_text, styles["Insight"])]],
            colWidths=[content_w],
        )
        insight_tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), ACCENT_SOFT),
                    ("LINEBEFORE", (0, 0), (0, -1), 2.5, ACCENT),
                    ("LEFTPADDING", (0, 0), (-1, -1), 14),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
                ]
            )
        )
        story.append(insight_tbl)
        story.append(PageBreak())

    # ---- detail table ----
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
        ("FONTSIZE", (0, 0), (-1, -1), 6.8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 1), (-1, 1), ACCENT_SOFT),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
    ]
    tbl.setStyle(TableStyle(style))
    story.append(tbl)

    doc.build(story)
    buf.seek(0)
    return buf.read()
