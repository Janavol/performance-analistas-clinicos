"""Gráficos (matplotlib) usados na tela do Streamlit e embutidos no PDF.

Os radares são desenhados manualmente em coordenadas cartesianas (não com o eixo
polar nativo do matplotlib) porque `Axes.set_xticks` num eixo polar, quando os
ângulos ultrapassam 2π (nosso primeiro eixo começa em +90°), faz o matplotlib
esticar `thetamax` para além de 360° e o "círculo" vira uma fatia — e mesmo
corrigindo isso, o posicionamento automático dos rótulos de eixo às vezes some ou
se sobrepõe. Desenhando à mão (como no SVG do artifact) temos controle total.
"""

from __future__ import annotations

import io
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLORS = {
    "good": "#0CA30C",
    "warning": "#B4790A",
    "serious": "#C1552C",
    "critical": "#D03B3B",
    "accent": "#0B6E5C",
    "border": "#DDD8CC",
    "surface_alt": "#F0ECE1",
    "text_muted": "#726B58",
    "text": "#1E1B15",
    "surface": "#FFFFFF",
}
CLASS_KEY = {"Excelente": "good", "Bom": "warning", "Regular": "serious", "Crítico": "critical"}

# Ordem dos eixos do radar: começa no topo e segue em sentido horário, igual ao artifact.
RADAR_AXES = [
    ("score_criticos", "Críticos"),
    ("score_protocolos", "Protocolos"),
    ("score_pa", "PA"),
    ("score_ui", "UI"),
    ("score_uca", "UTI"),
]


def color_for_class(classe):
    return COLORS.get(CLASS_KEY.get(classe), COLORS["accent"])


def _fig_to_png_bytes(fig, dpi=260) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0.05, facecolor=COLORS["surface"])
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Barras
# ---------------------------------------------------------------------------


def bar_chart_png(entries: list[dict], width=6.4, height=None) -> bytes:
    """entries: [{label, value, classe}], primeiro item é a referência (Equipe)."""
    import numpy as np

    n = len(entries)
    height = height or max(1.4, 0.38 * n + 0.55)
    fig, ax = plt.subplots(figsize=(width, height))
    labels = [e["label"] for e in entries]
    values = [e["value"] if e["value"] is not None else 0 for e in entries]
    colors = [color_for_class(e.get("classe")) for e in entries]

    y_pos = np.arange(n)[::-1]
    ax.barh(y_pos, values, color=colors, height=0.55, zorder=3)
    for y, v in zip(y_pos, values):
        ax.text(v + 1.5, y, f"{v:.1f}", va="center", fontsize=8.5, color=COLORS["text"], fontweight="bold")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8.5, color=COLORS["text"])
    ax.set_xlim(0, 108)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.tick_params(axis="x", colors=COLORS["text_muted"], labelsize=7.5)
    ax.grid(axis="x", color=COLORS["border"], linewidth=0.8, zorder=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(COLORS["border"])
    fig.tight_layout()
    return _fig_to_png_bytes(fig, dpi=320)


# ---------------------------------------------------------------------------
# Radar — desenho manual em coordenadas cartesianas (raio 1.0 = score 100)
# ---------------------------------------------------------------------------


def _radar_angles():
    n = len(RADAR_AXES)
    return [-math.pi / 2 + i * (2 * math.pi / n) for i in range(n)]


def _radar_axes_labels_align(angle):
    cos_a = math.cos(angle)
    if abs(cos_a) < 0.35:
        return "center"
    return "left" if cos_a > 0 else "right"


def _new_radar_ax(ax):
    ax.set_xlim(-2.05, 2.05)
    ax.set_ylim(-1.85, 1.85)
    ax.set_aspect("equal")
    ax.axis("off")


def _draw_radar_grid(ax, angles):
    for frac in (0.25, 0.5, 0.75, 1.0):
        pts = [(math.cos(a) * frac, math.sin(a) * frac) for a in angles]
        pts.append(pts[0])
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=COLORS["border"], linewidth=0.8, zorder=1)
    for a in angles:
        ax.plot([0, math.cos(a)], [0, math.sin(a)], color=COLORS["border"], linewidth=0.8, zorder=1)


def _draw_radar_axis_labels(ax, angles, fontsize=8.5):
    for a, (_, label) in zip(angles, RADAR_AXES):
        x, y = math.cos(a) * 1.62, math.sin(a) * 1.62
        ax.text(x, y, label, fontsize=fontsize, color=COLORS["text_muted"], ha=_radar_axes_labels_align(a), va="center", zorder=5)


def _draw_radar_shape(ax, angles, scores, color, linewidth=1.8, linestyle="-", fill_alpha=0.28, show_values=True, value_fontsize=8):
    fracs = [max(0, min(100, (scores.get(k) or 0))) / 100 for k, _ in RADAR_AXES]
    pts = [(math.cos(a) * f, math.sin(a) * f) for a, f in zip(angles, fracs)]
    pts_closed = pts + pts[:1]
    xs, ys = zip(*pts_closed)
    if fill_alpha:
        ax.fill(xs, ys, color=color, alpha=fill_alpha, zorder=2)
    ax.plot(xs, ys, color=color, linewidth=linewidth, linestyle=linestyle, zorder=3)
    if show_values:
        for a, f, (k, _) in zip(angles, fracs, RADAR_AXES):
            val = scores.get(k)
            if val is None:
                continue
            value_r = min(f + 0.13, 1.22)
            vx, vy = math.cos(a) * value_r, math.sin(a) * value_r
            ax.text(
                vx, vy, f"{val:.1f}", fontsize=value_fontsize, fontweight="bold", color=color,
                ha=_radar_axes_labels_align(a), va="center", zorder=4,
            )


def radar_chart_png(scores: dict, classe, size=2.15, show_values=True) -> bytes:
    """Radar de um único analista (ou equipe) — cartão pequeno, igual ao artifact."""
    fig, ax = plt.subplots(figsize=(size, size))
    _new_radar_ax(ax)
    angles = _radar_angles()
    _draw_radar_grid(ax, angles)
    _draw_radar_axis_labels(ax, angles, fontsize=7.8)
    color = color_for_class(classe)
    _draw_radar_shape(ax, angles, scores, color, show_values=show_values, value_fontsize=7.3)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return _fig_to_png_bytes(fig, dpi=320)


def radar_compare_png(scores_a: dict, classe_a, scores_b: dict, size=2.7) -> bytes:
    """scores_a = analista (colorido, com valores), scores_b = equipe (contorno tracejado neutro)."""
    fig, ax = plt.subplots(figsize=(size, size + 0.35))
    _new_radar_ax(ax)
    angles = _radar_angles()
    _draw_radar_grid(ax, angles)
    _draw_radar_axis_labels(ax, angles, fontsize=8)

    _draw_radar_shape(ax, angles, scores_b, COLORS["text_muted"], linewidth=1.4, linestyle="--", fill_alpha=0.06, show_values=False)
    color = color_for_class(classe_a)
    _draw_radar_shape(ax, angles, scores_a, color, linewidth=2.0, show_values=True, value_fontsize=7.6)

    legend_handles = [
        plt.Line2D([0], [0], color=color, linewidth=2.2, label="Analista"),
        plt.Line2D([0], [0], color=COLORS["text_muted"], linewidth=1.6, linestyle="--", label="Equipe"),
    ]
    ax.legend(
        handles=legend_handles, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=2,
        fontsize=7.5, frameon=False, handlelength=1.6, columnspacing=1.2,
    )
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0.1)
    return _fig_to_png_bytes(fig, dpi=320)


def radar_grid_png(items: list[dict], cols=4, size_each=1.9) -> bytes:
    """items: [{name, scores, classe, score_final}]. Grade de radares (para o PDF)."""
    n = len(items)
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(size_each * cols, (size_each + 0.5) * rows))
    axes_flat = axes.flatten() if n > 1 else [axes]
    angles = _radar_angles()
    for i, item in enumerate(items):
        ax = axes_flat[i]
        _new_radar_ax(ax)
        _draw_radar_grid(ax, angles)
        _draw_radar_axis_labels(ax, angles, fontsize=6.6)
        color = color_for_class(item.get("classe"))
        _draw_radar_shape(ax, angles, item["scores"], color, linewidth=1.4, show_values=True, value_fontsize=5.8)
        title = f"{item['name']}  ({item['score_final']:.1f})" if item.get("score_final") is not None else item["name"]
        ax.set_title(title, fontsize=8, color=COLORS["text"], pad=6)
    for j in range(n, len(axes_flat)):
        axes_flat[j].axis("off")
    fig.subplots_adjust(wspace=0.35, hspace=0.45, left=0.02, right=0.98, top=0.92, bottom=0.02)
    return _fig_to_png_bytes(fig, dpi=260)


# ---------------------------------------------------------------------------
# Linhas de tendência — análise por temporalidade
# ---------------------------------------------------------------------------

# Paleta categórica fixa (não é a paleta de status/classificação — aqui as
# cores só distinguem séries num gráfico de linha, sem significado de severidade).
TREND_PALETTE = ["#0B6E5C", "#B4790A", "#5B6EE1", "#C1552C", "#7A4FB5", "#2A8C8C"]


def _setup_trend_axes(ax, x_labels):
    n = len(x_labels)
    ax.set_xlim(-0.4, n - 0.6)
    ax.set_xticks(range(n))
    ax.set_xticklabels(x_labels, fontsize=8.5, color=COLORS["text_muted"], rotation=0 if n <= 6 else 30, ha="right" if n > 6 else "center")
    ax.set_ylim(0, 105)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.tick_params(axis="y", colors=COLORS["text_muted"], labelsize=8)
    ax.grid(axis="y", color=COLORS["border"], linewidth=0.8, zorder=0)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(COLORS["border"])
    ax.spines["bottom"].set_color(COLORS["border"])


def trend_line_png(x_labels, series: list, width=8.5, height=3.4, show_legend=True, show_values=None) -> bytes:
    """series: [{"label": str, "values": [float|None, ...], "color": "#hex" (opcional)}].
    show_values: None = automático (rótulos só quando há 1-2 séries; com mais, os
    números colidem entre linhas próximas, então mostramos só a grade + legenda)."""
    if show_values is None:
        show_values = len(series) <= 2
    fig, ax = plt.subplots(figsize=(width, height))
    _setup_trend_axes(ax, x_labels)
    for i, s in enumerate(series):
        color = s.get("color") or TREND_PALETTE[i % len(TREND_PALETTE)]
        xs = [i for i, v in enumerate(s["values"]) if v is not None]
        ys = [v for v in s["values"] if v is not None]
        ax.plot(xs, ys, color=color, linewidth=2.2, marker="o", markersize=5, label=s["label"], zorder=3)
        if show_values:
            for x, y in zip(xs, ys):
                ax.annotate(f"{y:.1f}", (x, y), textcoords="offset points", xytext=(0, 8), fontsize=7.5, color=color, ha="center", fontweight="bold")
    if show_legend and len(series) > 1:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=min(len(series), 5), fontsize=8.5, frameon=False)
    fig.tight_layout()
    return _fig_to_png_bytes(fig, dpi=260)


def mini_trend_png(x_labels, values, color=None, classe=None, width=2.6, height=1.7) -> bytes:
    """Mini gráfico de linha para cartões pequenos (grade por analista)."""
    color = color or color_for_class(classe)
    fig, ax = plt.subplots(figsize=(width, height))
    n = len(x_labels)
    ax.set_xlim(-0.35, n - 0.65)
    ax.set_ylim(0, 105)
    ax.set_yticks([0, 50, 100])
    ax.tick_params(axis="y", colors=COLORS["text_muted"], labelsize=6.5)
    ax.set_xticks(range(n))
    ax.set_xticklabels(x_labels, fontsize=6, color=COLORS["text_muted"], rotation=30, ha="right")
    ax.grid(axis="y", color=COLORS["border"], linewidth=0.6, zorder=0)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(COLORS["border"])
    ax.spines["bottom"].set_color(COLORS["border"])
    xs = [i for i, v in enumerate(values) if v is not None]
    ys = [v for v in values if v is not None]
    ax.plot(xs, ys, color=color, linewidth=1.8, marker="o", markersize=3.5, zorder=3)
    for x, y in zip(xs, ys):
        ax.annotate(f"{y:.0f}", (x, y), textcoords="offset points", xytext=(0, 5), fontsize=6, color=color, ha="center", fontweight="bold")
    fig.tight_layout()
    return _fig_to_png_bytes(fig, dpi=240)
