"""Aba "Análise por Temporalidade" — independente do módulo principal.

Recebe N planilhas Excel exportadas pelo módulo principal ("Baixar Excel da
análise"), uma por período (ex.: um arquivo por mês), e compara a evolução do
score da equipe e de cada analista entre os períodos enviados.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import charts
import components
import temporal_engine as te
import temporal_pdf

BLOCK_COLS = [
    ("Score Res. Críticos", "Críticos"),
    ("Score Protocolos", "Protocolos"),
    ("Score PA", "PA"),
    ("Score UI", "UI"),
    ("Score UCA", "UTI Adulto"),
]


def render():
    st.session_state.setdefault("temporal_result", None)

    st.markdown('<div class="eyebrow">Comparativo entre períodos</div>', unsafe_allow_html=True)
    st.markdown("# Análise por Temporalidade")
    st.markdown(
        '<p class="lede">Envie os arquivos Excel exportados na aba "Análise atual" '
        '(botão "Baixar Excel da análise") para comparar a evolução do score da equipe '
        "e de cada analista ao longo do tempo.</p>",
        unsafe_allow_html=True,
    )

    result = st.session_state["temporal_result"]

    if not result:
        st.info('📈 Nenhuma análise gerada ainda. Envie os arquivos no fim da página e clique em **Gerar análise**.')
    else:
        _render_results(result)

    st.divider()
    _render_upload_section(result)


def _render_upload_section(result):
    st.subheader("Enviar arquivos por período")
    uploaded = st.file_uploader(
        "Selecione os arquivos Excel (um por período)", type=["xlsx"],
        accept_multiple_files=True, key="temporal_files",
    )

    labels = []
    if uploaded:
        st.caption("Nomeie cada período (a ordem de exibição segue a ordem de envio):")
        cols = st.columns(min(3, len(uploaded)))
        for i, f in enumerate(uploaded):
            default = Path(f.name).stem
            with cols[i % len(cols)]:
                label = st.text_input(f.name, value=default, key=f"temporal_label_{i}_{f.name}")
            labels.append(label)

    can_generate = bool(uploaded) and len(uploaded) >= 1
    if st.button("📊 Gerar análise", type="primary", use_container_width=True, disabled=not can_generate):
        try:
            files_labels = list(zip(uploaded, labels))
            combined, warns = te.combine(files_labels)
            st.session_state["temporal_result"] = te.compute(combined)
            if warns:
                st.session_state["temporal_warning"] = "  ".join(warns)
            else:
                st.session_state["temporal_warning"] = None
            st.rerun()
        except Exception as e:
            st.error(f"Não consegui processar os arquivos: {e}")

    if st.session_state.get("temporal_warning"):
        st.warning(st.session_state["temporal_warning"])

    if result is not None:
        pdf_bytes = temporal_pdf.build_pdf(result)
        period_label = te.filename_from_periods(result["periods"])
        st.download_button(
            "⬇️ Baixar PDF", data=pdf_bytes, file_name=f"performancecumulativaac_{period_label}.pdf",
            mime="application/pdf", type="primary", use_container_width=True,
        )


def _render_results(result):
    periods = result["periods"]
    team_df = result["team_df"]
    last_row = team_df.dropna(subset=["Score Final"])
    team_classe = last_row["Classificação"].iloc[-1] if len(last_row) else None

    def sc(v):
        return f"{v:.1f}" if v is not None else "—"

    def delta_txt(v):
        return f"{v:+.1f}" if v is not None else "—"

    tiles = [
        components.tile_html("Períodos analisados", len(periods)),
        components.tile_html("Score inicial da equipe", sc(result["team_first"])),
        components.tile_html("Score atual da equipe", sc(result["team_last"]), components.pill_html(team_classe)),
        components.tile_html("Variação da equipe", delta_txt(result["team_delta"])),
        components.tile_html("Analistas comparados", len(result["analysts"])),
    ]
    st.markdown(components.tiles_row_html(tiles), unsafe_allow_html=True)

    st.markdown(
        f'<div class="insight-box"><div class="insight-title">Insight</div><p>{te.build_temporal_insight(result)}</p></div>',
        unsafe_allow_html=True,
    )

    st.divider()

    st.subheader("Evolução do score da equipe")
    team_png = charts.trend_line_png(
        periods, [{"label": "Equipe", "values": team_df["Score Final"].tolist(), "color": charts.COLORS["accent"]}],
        show_legend=False,
    )
    st.image(team_png, use_container_width=True)

    st.subheader("Evolução por bloco (equipe)")
    block_series = [{"label": label, "values": team_df[col].tolist()} for col, label in BLOCK_COLS]
    st.image(charts.trend_line_png(periods, block_series), use_container_width=True)

    st.divider()

    st.subheader("Evolução individual por analista")
    st.caption("Score final de cada analista em cada período enviado, com a variação do primeiro ao último período em que aparece.")
    st.markdown(components.trend_grid_html(result["analysts"], periods), unsafe_allow_html=True)

    st.divider()

    st.subheader("Tabela comparativa")
    pivot = (
        result["raw"][result["raw"]["Analista"] != "Equipe"]
        .pivot_table(index="Analista", columns=te.PERIOD_COL, values="Score Final", aggfunc="first")
    )
    pivot = pivot.reindex(columns=periods)
    st.dataframe(pivot.style.format("{:.1f}", na_rep="—"), use_container_width=True)
