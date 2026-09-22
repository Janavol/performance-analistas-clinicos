"""Gráficos (matplotlib) usados na tela do Streamlit e embutidos no PDF."""

from __future__ import annotations

import io
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

COLORS = {
    "good": "#0CA30C",
    "warning": "#B4790A",
    "serious": "#C1552C",
    "critical": "#D03B3B",
    "accent": "#0B6E5C",
    "border": "#DDD8CC",
    "text_muted": "#726B58",
    "text": "#1E1B15",
    "surface": "#FFFFFF",
}
CLASS_KEY = {"Excelente": "good", "Bom": "warning", "Regular": "serious", "Crítico": "critical"}

RADAR_AXES = [
    ("score_criticos", "Críticos"),
    ("score_protocolos", "Protocolos"),
    ("score_pa", "PA"),
    ("score_ui", "UI"),
    ("score_uca", "UTI"),
]


def color_for_class(classe):
    return COLORS.get(CLASS_KEY.get(classe), COLORS["accent"])


def _fig_to_png_bytes(fig, dpi=170) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor=COLORS["surface"])
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def bar_chart_png(entries: list[dict], width=7.2, height=None) -> bytes:
    """entries: [{label, value, classe}], primeiro item destacado como referência (Equipe)."""
    n = len(entries)
    height = height or max(1.6, 0.42 * n + 0.6)
    fig, ax = plt.subplots(figsize=(width, height))
    labels = [e["label"] for e in entries]
    values = [e["value"] if e["value"] is not None else 0 for e in entries]
    colors = [color_for_class(e.get("classe")) for e in entries]

    y_pos = np.arange(n)[::-1]
    ax.barh(y_pos, values, color=colors, height=0.55, zorder=3)
    for y, v in zip(y_pos, values):
        ax.text(v + 1.5, y, f"{v:.1f}", va="center", fontsize=9, color=COLORS["text"], fontweight="bold")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9.5, color=COLORS["text"])
    ax.set_xlim(0, 108)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.tick_params(axis="x", colors=COLORS["text_muted"], labelsize=8.5)
    ax.grid(axis="x", color=COLORS["border"], linewidth=0.8, zorder=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(COLORS["border"])
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def _radar_setup(ax, size_labels=9):
    n = len(RADAR_AXES)
    angles = [i / n * 2 * math.pi + math.pi / 2 for i in range(n)]
    ax.set_theta_offset(0)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles)
    ax.set_xticklabels([label for _, label in RADAR_AXES], fontsize=size_labels, color=COLORS["text_muted"])
    # set_xticks() with angles > 2π (our labels start at +90°) makes matplotlib
    # autoscale thetamax past 360°, squashing the polar plot into a wedge — force
    # the full circle back explicitly.
    ax.set_thetamin(0)
    ax.set_thetamax(360)
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels([])
    ax.spines["polar"].set_color(COLORS["border"])
    ax.grid(color=COLORS["border"], linewidth=0.8)
    ax.set_facecolor(COLORS["surface"])
    return angles


def radar_chart_png(scores: dict, classe, size=3.0) -> bytes:
    fig = plt.figure(figsize=(size, size))
    ax = fig.add_subplot(111, polar=True)
    angles = _radar_setup(ax)
    angles_closed = angles + angles[:1]
    values = [max(0, min(100, scores.get(k) or 0)) for k, _ in RADAR_AXES]
    values_closed = values + values[:1]
    color = color_for_class(classe)
    ax.plot(angles_closed, values_closed, color=color, linewidth=1.8)
    ax.fill(angles_closed, values_closed, color=color, alpha=0.28)
    return _fig_to_png_bytes(fig, dpi=160)


def radar_compare_png(scores_a: dict, classe_a, scores_b: dict, size=3.4) -> bytes:
    """scores_a = analista (colorido), scores_b = equipe (contorno tracejado neutro)."""
    fig = plt.figure(figsize=(size, size))
    ax = fig.add_subplot(111, polar=True)
    angles = _radar_setup(ax, size_labels=8.5)
    angles_closed = angles + angles[:1]

    values_b = [max(0, min(100, scores_b.get(k) or 0)) for k, _ in RADAR_AXES]
    ax.plot(angles_closed, values_b + values_b[:1], color=COLORS["text_muted"], linewidth=1.5, linestyle="--", label="Equipe")
    ax.fill(angles_closed, values_b + values_b[:1], color=COLORS["text_muted"], alpha=0.07)

    values_a = [max(0, min(100, scores_a.get(k) or 0)) for k, _ in RADAR_AXES]
    color = color_for_class(classe_a)
    ax.plot(angles_closed, values_a + values_a[:1], color=color, linewidth=2.0, label="Analista")
    ax.fill(angles_closed, values_a + values_a[:1], color=color, alpha=0.30)

    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.12), fontsize=8, frameon=False)
    return _fig_to_png_bytes(fig, dpi=160)


def radar_grid_png(items: list[dict], cols=4, size_each=2.4) -> bytes:
    """items: [{name, scores, classe, score_final}]. Grade única de radares (equipe + analistas)."""
    n = len(items)
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(
        rows, cols, figsize=(size_each * cols, (size_each + 0.55) * rows), subplot_kw={"polar": True}
    )
    axes_flat = np.array(axes).reshape(-1)
    for i, item in enumerate(items):
        ax = axes_flat[i]
        angles = _radar_setup(ax, size_labels=7.5)
        angles_closed = angles + angles[:1]
        values = [max(0, min(100, item["scores"].get(k) or 0)) for k, _ in RADAR_AXES]
        values_closed = values + values[:1]
        color = color_for_class(item.get("classe"))
        ax.plot(angles_closed, values_closed, color=color, linewidth=1.6)
        ax.fill(angles_closed, values_closed, color=color, alpha=0.28)
        title = f"{item['name']}  ({item['score_final']:.1f})" if item.get("score_final") is not None else item["name"]
        ax.set_title(title, fontsize=8.5, color=COLORS["text"], pad=14)
    for j in range(n, len(axes_flat)):
        axes_flat[j].axis("off")
    fig.subplots_adjust(wspace=0.5, hspace=0.6)
    return _fig_to_png_bytes(fig, dpi=150)
