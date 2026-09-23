"""Motor de cálculo de performance dos analistas.

Replica a lógica da planilha de referência ("Configuração" + "Calculos" +
"Performance (Dados gerais)"), incluindo o bloco de Unidades de Internação (UI),
tratado de forma idêntica ao Pronto Atendimento (PA).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Configuração padrão (mirror do CONFIG default do artifact)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "tat": {
        "CRITICOAMB": 120,
        "CRITICOHOSP": 30,
        "PA": 60,
        "UI": 60,
        "UTI": 120,
        "SEPSE": 5,
        "DOR_TORACICA": 20,
        "AVE": 20,
    },
    "block_weights": {
        "criticos": 0.25,
        "protocolos": 0.35,
        "pa": 0.20,
        "ui": 0.15,
        "uti": 0.05,
    },
    "criticos": {
        "taxa_notificacao": 0.8,
        "taxa_prazo": 0.2,
        "penalidade": 1,
    },
    "protocolos": {
        "SEPSE": 0.5,
        "DOR_TORACICA": 0.3,
        "AVE": 0.2,
    },
    "class_min": {
        "excelente": 90,
        "bom": 80,
        "regular": 70,
        "critico": 50,  # exibido apenas; não usado na cadeia de classificação
    },
}

CAT_LABELS = {
    "CRITICOAMB": "Crítico ambulatorial",
    "CRITICOHOSP": "Crítico hospitalar",
    "PA": "Pronto atendimento",
    "UI": "Unidades de Internação",
    "UTI": "UTI Adulto",
    "SEPSE": "Sepse",
    "DOR_TORACICA": "Dor torácica",
    "AVE": "AVE",
}

CRITICAL_CATS = {"CRITICOAMB", "CRITICOHOSP"}

CLASS_KEY = {"Excelente": "good", "Bom": "warning", "Regular": "serious", "Crítico": "critical"}


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Leitura e normalização da planilha enviada
# ---------------------------------------------------------------------------

import unicodedata


def _norm(s: str) -> str:
    s = str(s or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s


def _map_headers(headers: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for h in headers:
        n = _norm(h)
        if "analista" not in mapping and "analista" in n:
            mapping["analista"] = h
        elif "categoria" not in mapping and "categoria" in n:
            mapping["categoria"] = h
        elif "hora_inicio" not in mapping and "inicio" in n:
            mapping["hora_inicio"] = h
        elif "hora_liberacao" not in mapping and "liberacao" in n:
            mapping["hora_liberacao"] = h
        elif "hora_notificacao" not in mapping and "notifica" in n:
            mapping["hora_notificacao"] = h
    return mapping


def load_raw_rows(file) -> tuple[pd.DataFrame, list[str]]:
    """Lê o arquivo enviado (xlsx) e retorna um DataFrame padronizado.

    Colunas de saída: analista, categoria, hora_inicio, hora_liberacao, hora_notificacao.
    """
    warnings: list[str] = []
    xls = pd.ExcelFile(file)
    sheet_name = "Dados" if "Dados" in xls.sheet_names else xls.sheet_names[0]
    df = pd.read_excel(xls, sheet_name=sheet_name)

    mapping = _map_headers(list(df.columns))
    if "analista" not in mapping or "categoria" not in mapping:
        raise ValueError(
            'Não encontrei as colunas "Analista" e "Categoria" na planilha '
            f'(aba "{sheet_name}"). Confira o formato esperado no modelo.'
        )

    out = pd.DataFrame(
        {
            "analista": df[mapping["analista"]],
            "categoria": df[mapping["categoria"]],
            "hora_inicio": df[mapping["hora_inicio"]] if "hora_inicio" in mapping else None,
            "hora_liberacao": df[mapping["hora_liberacao"]] if "hora_liberacao" in mapping else None,
            "hora_notificacao": df[mapping["hora_notificacao"]] if "hora_notificacao" in mapping else None,
        }
    )
    for col in ("hora_inicio", "hora_liberacao", "hora_notificacao"):
        out[col] = pd.to_datetime(out[col], errors="coerce")

    warnings.append(f'Lido a partir da aba "{sheet_name}".')
    return out, warnings


# ---------------------------------------------------------------------------
# Cálculo por linha
# ---------------------------------------------------------------------------


def _prepare_rows(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, dict]:
    tat = config["tat"]
    d = df.copy()
    d["analista"] = d["analista"].astype(str).str.strip()
    d["categoria"] = d["categoria"].astype(str).str.strip().str.upper().str.replace(r"\s+", "_", regex=True)

    mask_missing = d["analista"].eq("") | d["analista"].eq("nan") | d["categoria"].eq("") | d["categoria"].eq("nan")
    missing_count = int(mask_missing.sum())
    d = d[~mask_missing]

    d["tat_limite"] = d["categoria"].map(tat)
    unknown_count = int(d["tat_limite"].isna().sum())
    d = d[d["tat_limite"].notna()]

    d["critico"] = d["categoria"].isin(CRITICAL_CATS)
    tempo_liberacao_min = (d["hora_liberacao"] - d["hora_inicio"]).dt.total_seconds() / 60
    d["tempo_liberacao_min"] = tempo_liberacao_min
    d["dentro_prazo"] = (tempo_liberacao_min.notna()) & (tempo_liberacao_min <= d["tat_limite"])

    d["notificado"] = d["hora_notificacao"].notna()
    tat_notif_min = (d["hora_notificacao"] - d["hora_liberacao"]).dt.total_seconds() / 60
    d["tat_notif_min"] = tat_notif_min.where(d["critico"] & d["notificado"] & d["hora_liberacao"].notna())
    d["dentro_tat_notif"] = (
        d["critico"] & d["notificado"] & d["tat_notif_min"].notna() & (d["tat_notif_min"] <= d["tat_limite"])
    )

    warnings = []
    if unknown_count:
        warnings.append(f"{unknown_count} linha(s) ignorada(s) por categoria não reconhecida.")
    if missing_count:
        warnings.append(f"{missing_count} linha(s) ignorada(s) por falta de analista ou categoria.")

    return d, {"warnings": warnings, "row_count": len(d)}


def _block_stats(rows: pd.DataFrame, cat: str) -> dict:
    sub = rows[rows["categoria"] == cat]
    n = len(sub)
    np_ = int(sub["dentro_prazo"].sum())
    pct = (np_ / n) if n else None
    return {"n": n, "np": np_, "pct": pct}


def _classify(score: Optional[float], class_min: dict) -> Optional[str]:
    if score is None:
        return None
    if score >= class_min["excelente"]:
        return "Excelente"
    if score >= class_min["bom"]:
        return "Bom"
    if score >= class_min["regular"]:
        return "Regular"
    return "Crítico"


def _analyst_stats(rows: pd.DataFrame, config: dict) -> dict:
    rc_total = int(rows["critico"].sum())
    rc_notif = int((rows["critico"] & rows["notificado"]).sum())
    rc_notif_pct = (rc_notif / rc_total) if rc_total else None
    rc_prazo = int((rows["critico"] & rows["dentro_tat_notif"]).sum())
    rc_prazo_pct = (rc_prazo / rc_total) if rc_total else None
    tat_vals = rows.loc[rows["critico"] & rows["tat_notif_min"].notna() & (rows["tat_notif_min"] > 0), "tat_notif_min"]
    rc_media = float(tat_vals.mean()) if len(tat_vals) else None

    pa = _block_stats(rows, "PA")
    ui = _block_stats(rows, "UI")
    uti = _block_stats(rows, "UTI")
    sepse = _block_stats(rows, "SEPSE")
    dt = _block_stats(rows, "DOR_TORACICA")
    ave = _block_stats(rows, "AVE")

    crit_cfg = config["criticos"]
    score_criticos = None
    if rc_total:
        score_criticos = clamp(
            ((rc_notif_pct * crit_cfg["taxa_notificacao"]) + (rc_prazo_pct * crit_cfg["taxa_prazo"])) * 100
            - (rc_total - rc_notif) * crit_cfg["penalidade"],
            0,
            100,
        )
    score_uca = (uti["pct"] * 100) if uti["n"] else None

    proto_cfg = config["protocolos"]
    peso_s, peso_d, peso_a = proto_cfg["SEPSE"], proto_cfg["DOR_TORACICA"], proto_cfg["AVE"]
    num_p = (peso_s * sepse["pct"] if sepse["n"] > 0 else 0) + (peso_d * dt["pct"] if dt["n"] > 0 else 0) + (
        peso_a * ave["pct"] if ave["n"] > 0 else 0
    )
    den_p = (peso_s if sepse["n"] > 0 else 0) + (peso_d if dt["n"] > 0 else 0) + (peso_a if ave["n"] > 0 else 0)
    score_protocolos = (num_p / den_p * 100) if den_p > 0 else None

    score_pa = (pa["pct"] * 100) if pa["n"] else None
    score_ui = (ui["pct"] * 100) if ui["n"] else None

    w = config["block_weights"]
    terms = [
        (score_criticos, w["criticos"]),
        (score_uca, w["uti"]),
        (score_protocolos, w["protocolos"]),
        (score_pa, w["pa"]),
        (score_ui, w["ui"]),
    ]
    num_f = sum(s * wt for s, wt in terms if s is not None)
    den_f = sum(wt for s, wt in terms if s is not None)
    score_final = (num_f / den_f) if den_f > 0 else None
    classe = _classify(score_final, config["class_min"])

    return {
        "rc_total": rc_total,
        "rc_notif": rc_notif,
        "rc_notif_pct": rc_notif_pct,
        "rc_prazo": rc_prazo,
        "rc_prazo_pct": rc_prazo_pct,
        "rc_media": rc_media,
        "pa": pa,
        "ui": ui,
        "uti": uti,
        "sepse": sepse,
        "dt": dt,
        "ave": ave,
        "score_criticos": score_criticos,
        "score_uca": score_uca,
        "score_protocolos": score_protocolos,
        "score_pa": score_pa,
        "score_ui": score_ui,
        "score_final": score_final,
        "classe": classe,
    }


def compute(df: pd.DataFrame, config: dict) -> dict:
    """Roda o motor completo. Retorna dict com per_analyst (list), team (dict), warnings, row_count."""
    rows, meta = _prepare_rows(df, config)

    per_analyst = []
    for name, group in rows.groupby("analista", sort=False):
        stats = _analyst_stats(group, config)
        stats["analista"] = name
        per_analyst.append(stats)
    per_analyst.sort(key=lambda a: (a["score_final"] if a["score_final"] is not None else -1), reverse=True)

    def avg(values):
        v = [x for x in values if x is not None]
        return (sum(v) / len(v)) if v else None

    team_counts = _analyst_stats(rows, config)
    team_w = avg(a["score_criticos"] for a in per_analyst)
    team_x = avg(a["score_uca"] for a in per_analyst)
    team_y = avg(a["score_protocolos"] for a in per_analyst)
    team_z = avg(a["score_pa"] for a in per_analyst)
    team_u = avg(a["score_ui"] for a in per_analyst)

    w = config["block_weights"]
    terms = [
        (team_w, w["criticos"]),
        (team_x, w["uti"]),
        (team_y, w["protocolos"]),
        (team_z, w["pa"]),
        (team_u, w["ui"]),
    ]
    num_f = sum(s * wt for s, wt in terms if s is not None)
    den_f = sum(wt for s, wt in terms if s is not None)
    team_score_final = (num_f / den_f) if den_f > 0 else None
    team_classe = _classify(team_score_final, config["class_min"])

    team = dict(team_counts)
    team.update(
        {
            "analista": "Equipe",
            "score_criticos": team_w,
            "score_uca": team_x,
            "score_protocolos": team_y,
            "score_pa": team_z,
            "score_ui": team_u,
            "score_final": team_score_final,
            "classe": team_classe,
        }
    )

    return {
        "per_analyst": per_analyst,
        "team": team,
        "warnings": meta["warnings"],
        "row_count": meta["row_count"],
    }


# ---------------------------------------------------------------------------
# Nome de arquivo a partir das datas reais dos pedidos analisados
# ---------------------------------------------------------------------------

import unicodedata

MONTHS_PT = [
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def period_label_from_dates(dates) -> str:
    """A partir de uma série de datas (ex.: hora_inicio dos pedidos filtrados),
    devolve algo como "julho_2026" ou "maio_junho_2026" — os meses (e o ano)
    realmente presentes nos dados, não a data de hoje."""
    parsed = pd.to_datetime(pd.Series(dates), errors="coerce").dropna()
    if parsed.empty:
        return "periodo"

    year_months: dict[int, set[int]] = {}
    for d in parsed:
        year_months.setdefault(d.year, set()).add(d.month)

    parts = []
    for year in sorted(year_months):
        months = sorted(year_months[year])
        month_names = [MONTHS_PT[m - 1] for m in months]
        parts.append("_".join(month_names) + f"_{year}")
    return "_".join(parts)
