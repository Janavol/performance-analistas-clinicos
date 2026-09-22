"""Performance Analistas Clínicos — painel Streamlit.

Calcula automaticamente a performance dos analistas (notificação de resultados
críticos, cumprimento de TAT por protocolo e score final ponderado) a partir de
uma planilha de pedidos, com exportação em Excel e PDF que funciona para
qualquer pessoa que abrir o link do app — sem depender de permissões do Claude.
"""

from __future__ import annotations

import copy
from datetime import datetime

import pandas as pd
import streamlit as st

import charts
import components
import engine
import excel_export
import pdf_report
from components import (
    CLASS_CSS,
    analyst_card_html,
    pill_html,
    radar_card_html,
    tile_html,
    tiles_row_html,
)
from insights import build_insight

st.set_page_config(page_title="Performance Analistas Clínicos", layout="wide", page_icon="📊")

# ---------------------------------------------------------------------------
# Estilos — components.BASE_CSS é a mesma folha de estilo usada no PDF
# (via WeasyPrint); aqui só somam-se os seletores específicos do Streamlit.
# ---------------------------------------------------------------------------
st.markdown(
    components.FONT_LINKS
    + f"<style>{components.BASE_CSS}</style>"
    + """
    <style>
    .stApp { background-color: #F6F4EE; }
    h1, h2, h3,
    .stApp h1, .stApp h2, .stApp h3,
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3 {
        color: #1E1B15 !important;
        font-family: 'Fraunces', Georgia, serif !important;
    }
    [data-testid="stMarkdownContainer"] h1 { font-weight: 600 !important; }
    div[data-testid="stImage"] { display:flex; justify-content:center; }
    .radar-card { margin-bottom:8px; }
    .insight-box { align-self:stretch; }
    @media (max-width: 640px) { .analyst-charts { flex-direction:column; } }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Estado inicial (session_state) — lido no topo, widgets renderizados no fim
# ---------------------------------------------------------------------------
st.session_state.setdefault("config", copy.deepcopy(engine.DEFAULT_CONFIG))
st.session_state.setdefault("show_example", False)
st.session_state.setdefault("uploaded_rows", None)  # DataFrame padronizado (None = nada carregado)
st.session_state.setdefault("uploaded_name", None)
st.session_state.setdefault("selected_analysts", None)  # lista; None = ainda não inicializado
st.session_state.setdefault("upload_warning", None)

config = st.session_state["config"]
show_example = st.session_state["show_example"]
raw_df = st.session_state["uploaded_rows"]
has_data = raw_df is not None or show_example


def build_example_df() -> pd.DataFrame:
    def mk(name, cat, day, hour, mins_taken):
        start = datetime(2026, 8, day, hour, 0)
        rel = start + pd.Timedelta(minutes=mins_taken)
        return {"analista": name, "categoria": cat, "hora_inicio": start, "hora_liberacao": rel, "hora_notificacao": pd.NaT}

    people = [
        {"name": "LUIZAEM", "pa": [45, 70], "ui": [50, 80], "uti": [140], "sepse": [(3, True)], "dt": [(15, True)], "ave": [(25, False)],
         "crit": [("CRITICOAMB", True, 90, 90), ("CRITICOHOSP", True, 25, 25), ("CRITICOAMB", False, 90, None)]},
        {"name": "WILLIANC", "pa": [50], "ui": [45], "uti": [95], "sepse": [(4, True)], "dt": [(12, True)], "ave": [(10, True)],
         "crit": [("CRITICOAMB", True, 60, 60), ("CRITICOHOSP", True, 18, 18)]},
        {"name": "ANACJV", "pa": [80, 40], "ui": [75], "uti": [60], "sepse": [(6, False)], "dt": [(25, False)], "ave": [(18, True)],
         "crit": [("CRITICOAMB", True, 150, 150), ("CRITICOAMB", False, 90, None)]},
        {"name": "JAKELINESR", "pa": [55], "ui": [40, 55], "uti": [110], "sepse": [(4, True)], "dt": [(18, True)], "ave": [(19, True)],
         "crit": [("CRITICOHOSP", True, 20, 20), ("CRITICOAMB", True, 80, 80)]},
    ]
    rows = []
    day, hour = 1, 1

    def next_hour():
        nonlocal hour
        hour = (hour + 2) % 20 + 1
        return hour

    for p in people:
        for mins in p["pa"]:
            rows.append(mk(p["name"], "PA", day, hour, mins)); next_hour()
        for mins in p["ui"]:
            rows.append(mk(p["name"], "UI", day, hour, mins)); next_hour()
        for mins in p["uti"]:
            rows.append(mk(p["name"], "UTI", day, hour, mins)); next_hour()
        for mins, ok in p["sepse"]:
            rows.append(mk(p["name"], "SEPSE", day, hour, mins if ok else mins + 8)); next_hour()
        for mins, ok in p["dt"]:
            rows.append(mk(p["name"], "DOR_TORACICA", day, hour, mins if ok else mins + 15)); next_hour()
        for mins, ok in p["ave"]:
            rows.append(mk(p["name"], "AVE", day, hour, mins if ok else mins + 20)); next_hour()
        for cat, notified, rel_min, notif_min in p["crit"]:
            start = datetime(2026, 8, day, hour, 0)
            rel = start + pd.Timedelta(minutes=rel_min)
            notif = rel + pd.Timedelta(minutes=notif_min) if notified else pd.NaT
            rows.append({"analista": p["name"], "categoria": cat, "hora_inicio": start, "hora_liberacao": rel, "hora_notificacao": notif})
            next_hour()
        day = day + 1 if day < 28 else 1

    return pd.DataFrame(rows)


source_df = raw_df if raw_df is not None else (build_example_df() if show_example else None)

# ---------------------------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------------------------
st.markdown('<div class="eyebrow">Análise automática de performance</div>', unsafe_allow_html=True)
st.markdown("# Performance Analistas Clínicos")
st.markdown(
    '<p class="lede">Calcula <b>notificação de resultados críticos</b>, <b>cumprimento de TAT</b> por protocolo '
    "(PA, UI, UTI, Sepse, Dor Torácica, AVE) e o <b>score final ponderado</b> de cada analista. "
    'Envie sua planilha, ajuste os parâmetros e selecione os analistas no painel no fim da página.</p>',
    unsafe_allow_html=True,
)

result = None
all_names: list[str] = []

if not has_data:
    st.info("📄 Nenhuma planilha carregada. Role até o fim da página para enviar a sua, ajustar a configuração de cálculo, ou marque **Ver dados de exemplo** para pré-visualizar o painel.")
else:
    engine_result_full = engine.compute(source_df, config)
    all_names = sorted({a["analista"] for a in engine_result_full["per_analyst"]}, key=lambda s: s.lower())

    if st.session_state["selected_analysts"] is None:
        st.session_state["selected_analysts"] = list(all_names)
    else:
        st.session_state["selected_analysts"] = [n for n in st.session_state["selected_analysts"] if n in all_names]

    selected = st.session_state["selected_analysts"]

    if not all_names:
        st.warning("Nenhum analista reconhecido nesta planilha. Confira o formato no modelo de download, no fim da página.")
    elif not selected:
        st.warning('Nenhum analista selecionado. Marque ao menos um em "Analistas no relatório", no fim da página.')
    else:
        filtered_df = source_df[source_df["analista"].astype(str).str.strip().isin(selected)]
        result = engine.compute(filtered_df, config)

        if show_example and raw_df is None:
            st.markdown(
                '<div style="background:#E3F1EC;color:#0B6E5C;border-radius:10px;padding:10px 14px;font-size:13px;font-weight:600;">'
                "ℹ️ Dados de exemplo ilustrativos — envie sua planilha para calcular a performance real da equipe.</div>",
                unsafe_allow_html=True,
            )

        t = result["team"]

        # ---- tiles (mesmo cartão/fonte do artifact) ----
        def pct(v):
            return f"{v*100:.1f}%" if v is not None else "—"

        def sc(v):
            return f"{v:.1f}" if v is not None else "—"

        main_tiles = [
            tile_html("Score final da equipe", sc(t["score_final"]), pill_html(t["classe"])),
            tile_html("Resultados críticos", t["rc_total"]),
            tile_html("Críticos notificados", pct(t["rc_notif_pct"])),
            tile_html("Notificados no prazo", pct(t["rc_prazo_pct"])),
            tile_html("PA no prazo", pct(t["pa"]["pct"])),
            tile_html("UI no prazo", pct(t["ui"]["pct"])),
            tile_html("UTI no prazo", pct(t["uti"]["pct"])),
        ]
        st.markdown(tiles_row_html(main_tiles), unsafe_allow_html=True)

        # ---- block score tiles (score por protocolo/bloco) ----
        st.markdown('<div class="section-caption">Score por bloco (equipe)</div>', unsafe_allow_html=True)
        block_tiles = [
            tile_html("Score Críticos", sc(t["score_criticos"])),
            tile_html("Score Protocolos", sc(t["score_protocolos"])),
            tile_html("Score PA", sc(t["score_pa"])),
            tile_html("Score UI", sc(t["score_ui"])),
            tile_html("Score UTI Adulto", sc(t["score_uca"])),
        ]
        st.markdown(tiles_row_html(block_tiles), unsafe_allow_html=True)

        st.divider()

        # ---- bar chart ----
        st.subheader("Score final por analista")
        rankable = [a for a in result["per_analyst"] if a["score_final"] is not None]
        bar_entries = [{"label": "Equipe", "value": t["score_final"], "classe": t["classe"]}] + [
            {"label": a["analista"], "value": a["score_final"], "classe": a["classe"]} for a in rankable
        ]
        if len(bar_entries) > 1:
            st.image(charts.bar_chart_png(bar_entries, width=14), use_container_width=True)
        else:
            st.caption("Nenhum analista com dados suficientes para gerar score.")

        st.divider()

        # ---- radar cards (mesmo estilo do artifact: cartão pequeno com borda + pill) ----
        st.subheader("Perfil por bloco — radar")
        st.caption("Cada eixo mostra o score (0–100, equivalente a % de cumprimento): Resultados críticos, Protocolos, Pronto atendimento, Unidades de Internação e UTI Adulto.")
        radar_items = [{"name": "Equipe", "scores": t, "classe": t["classe"], "score_final": t["score_final"]}] + [
            {"name": a["analista"], "scores": a, "classe": a["classe"], "score_final": a["score_final"]}
            for a in result["per_analyst"]
        ]
        radar_cols_per_row = 5
        for start in range(0, len(radar_items), radar_cols_per_row):
            row_items = radar_items[start : start + radar_cols_per_row]
            row_cols = st.columns(radar_cols_per_row)
            for col, item in zip(row_cols, row_items):
                with col:
                    st.markdown(radar_card_html(item), unsafe_allow_html=True)

        st.divider()

        # ---- per-analyst analysis ----
        st.subheader("Análise por analista")
        st.caption("Resumo individual, comparação com a equipe e insight automático — a mesma análise que sai em página própria no PDF.")
        for a in result["per_analyst"]:
            with st.expander(f"**{a['analista']}**" + (f" — score final {a['score_final']:.1f}" if a["score_final"] is not None else ""), expanded=False):
                st.markdown(analyst_card_html(a, t), unsafe_allow_html=True)

        st.divider()

        # ---- detail table ----
        st.subheader("Detalhamento por analista")
        st.caption('Réplica das colunas da planilha "Performance (Dados gerais)".')

        def row_dict(a):
            return {
                "Analista": a["analista"], "RC Total": a["rc_total"], "RC Notif.": a["rc_notif_pct"],
                "RC no Prazo": a["rc_prazo_pct"], "PA no Prazo": a["pa"]["pct"], "UI no Prazo": a["ui"]["pct"],
                "UTI no Prazo": a["uti"]["pct"], "Sepse no Prazo": a["sepse"]["pct"], "DT no Prazo": a["dt"]["pct"],
                "AVE no Prazo": a["ave"]["pct"], "Sc. Críticos": a["score_criticos"], "Sc. Protocolos": a["score_protocolos"],
                "Sc. PA": a["score_pa"], "Sc. UI": a["score_ui"], "Sc. UCA": a["score_uca"],
                "Score Final": a["score_final"], "Classificação": a["classe"],
            }

        table_df = pd.DataFrame([row_dict(t)] + [row_dict(a) for a in result["per_analyst"]])
        pct_cols = ["RC Notif.", "RC no Prazo", "PA no Prazo", "UI no Prazo", "UTI no Prazo", "Sepse no Prazo", "DT no Prazo", "AVE no Prazo"]
        fmt = {c: "{:.1%}" for c in pct_cols}
        fmt.update({c: "{:.1f}" for c in ["Sc. Críticos", "Sc. Protocolos", "Sc. PA", "Sc. UI", "Sc. UCA", "Score Final"]})
        st.dataframe(table_df.style.format(fmt, na_rep="—"), use_container_width=True, hide_index=True)

        st.divider()

        # ---- downloads ----
        dl1, dl2 = st.columns(2)
        excel_bytes = excel_export.build_excel(result, config)
        dl1.download_button(
            "⬇️ Baixar Excel da análise", data=excel_bytes,
            file_name="analise-performance-analistas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        is_example = show_example and raw_df is None
        pdf_bytes = pdf_report.build_pdf(result, config, is_example)
        dl2.download_button(
            "⬇️ Baixar PDF da análise", data=pdf_bytes,
            file_name="analise-performance-analistas.pdf", mime="application/pdf",
            type="primary", use_container_width=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# Controles: upload, configuração, filtro — sempre no fim da página
# ---------------------------------------------------------------------------
with st.expander("📤 Enviar planilha", expanded=not has_data):
    up_col1, up_col2 = st.columns([2, 1])
    with up_col1:
        uploaded = st.file_uploader("Planilha de pedidos (.xlsx)", type=["xlsx", "xls"], key="file_uploader")
        if uploaded is not None and uploaded.name != st.session_state.get("uploaded_name"):
            try:
                df, warns = engine.load_raw_rows(uploaded)
                st.session_state["uploaded_rows"] = df
                st.session_state["uploaded_name"] = uploaded.name
                st.session_state["show_example"] = False
                st.session_state["selected_analysts"] = None
                st.session_state["upload_warning"] = "  ".join(warns) if warns else None
                st.rerun()
            except Exception as e:
                st.error(f"Não consegui ler essa planilha: {e}")
        if st.session_state["uploaded_name"]:
            st.success(f'"{st.session_state["uploaded_name"]}" carregado.')
    with up_col2:
        st.write("")
        st.write("")
        st.download_button(
            "Baixar modelo de planilha", data=excel_export.build_template(),
            file_name="modelo-performance-analistas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        if st.button("Ver dados de exemplo" if not show_example else "Limpar", use_container_width=True):
            if show_example or raw_df is not None:
                st.session_state["uploaded_rows"] = None
                st.session_state["uploaded_name"] = None
                st.session_state["show_example"] = False
                st.session_state["selected_analysts"] = None
            else:
                st.session_state["show_example"] = True
                st.session_state["selected_analysts"] = None
            st.rerun()

with st.expander("⚙️ Configuração do cálculo", expanded=False):
    st.caption('Os valores padrão reproduzem a aba "Configuração" da planilha de referência. Qualquer alteração recalcula o painel imediatamente.')
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Limites de TAT (minutos)**")
        for cat, label in engine.CAT_LABELS.items():
            config["tat"][cat] = st.number_input(label, value=int(config["tat"][cat]), step=5, key=f"tat_{cat}")
    with c2:
        st.markdown("**Peso dos blocos no score final**")
        config["block_weights"]["criticos"] = st.number_input("Resultados críticos", value=float(config["block_weights"]["criticos"]), step=0.05, key="bw_criticos")
        config["block_weights"]["protocolos"] = st.number_input("Protocolos", value=float(config["block_weights"]["protocolos"]), step=0.05, key="bw_protocolos")
        config["block_weights"]["pa"] = st.number_input("Pronto atendimento", value=float(config["block_weights"]["pa"]), step=0.05, key="bw_pa")
        config["block_weights"]["ui"] = st.number_input("Unidades de Internação", value=float(config["block_weights"]["ui"]), step=0.05, key="bw_ui")
        config["block_weights"]["uti"] = st.number_input("UTI Adulto", value=float(config["block_weights"]["uti"]), step=0.05, key="bw_uti")
    with c3:
        st.markdown("**Composição — resultados críticos**")
        config["criticos"]["taxa_notificacao"] = st.number_input("Peso taxa de notificação", value=float(config["criticos"]["taxa_notificacao"]), step=0.05, key="cc_notif")
        config["criticos"]["taxa_prazo"] = st.number_input("Peso taxa dentro do prazo", value=float(config["criticos"]["taxa_prazo"]), step=0.05, key="cc_prazo")
        config["criticos"]["penalidade"] = st.number_input("Penalidade por não notificado", value=float(config["criticos"]["penalidade"]), step=0.5, key="cc_pen")
        st.markdown("**Peso interno dos protocolos**")
        config["protocolos"]["SEPSE"] = st.number_input("Sepse", value=float(config["protocolos"]["SEPSE"]), step=0.05, key="pp_sepse")
        config["protocolos"]["DOR_TORACICA"] = st.number_input("Dor torácica", value=float(config["protocolos"]["DOR_TORACICA"]), step=0.05, key="pp_dt")
        config["protocolos"]["AVE"] = st.number_input("AVE", value=float(config["protocolos"]["AVE"]), step=0.05, key="pp_ave")
    st.markdown("**Faixas de classificação (score mínimo)**")
    cm1, cm2, cm3 = st.columns(3)
    config["class_min"]["excelente"] = cm1.number_input("Excelente", value=int(config["class_min"]["excelente"]), step=1, key="cm_exc")
    config["class_min"]["bom"] = cm2.number_input("Bom", value=int(config["class_min"]["bom"]), step=1, key="cm_bom")
    config["class_min"]["regular"] = cm3.number_input("Regular", value=int(config["class_min"]["regular"]), step=1, key="cm_reg")

with st.expander(f"✅ Analistas no relatório ({len(st.session_state['selected_analysts'] or [])} de {len(all_names)})" if all_names else "✅ Analistas no relatório", expanded=False):
    if not all_names:
        st.caption("Envie uma planilha (ou veja os dados de exemplo) para listar os analistas.")
    else:
        bcol1, bcol2 = st.columns(2)
        if bcol1.button("Selecionar todos", use_container_width=True):
            st.session_state["selected_analysts"] = list(all_names)
            st.rerun()
        if bcol2.button("Limpar seleção", use_container_width=True):
            st.session_state["selected_analysts"] = []
            st.rerun()
        st.multiselect("Analistas incluídos", options=all_names, key="selected_analysts")
