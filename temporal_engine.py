"""Motor da análise por temporalidade — combina N planilhas exportadas pelo
primeiro módulo (aba "Análise atual" → Baixar Excel da análise) em uma série
histórica, e calcula a evolução da equipe e de cada analista entre períodos."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from engine import _strip_accents

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")

PERIOD_COL = "Período"

# Colunas esperadas na aba "Performance" do Excel exportado pelo módulo principal.
NUMERIC_COLS = [
    "RC Total", "RC Notificados (%)", "RC Notificados no prazo (%)",
    "PA Liberado no prazo (%)", "UI Liberado no prazo (%)", "UTI Liberado no prazo (%)",
    "Sepse no prazo (%)", "DT no prazo (%)", "AVE no prazo (%)",
    "Score Res. Críticos", "Score UCA", "Score Protocolos", "Score PA", "Score UI",
    "Score Final",
]
KEEP_COLS = ["Analista", "Classificação"] + NUMERIC_COLS


def load_period_file(file, label: str) -> tuple[pd.DataFrame, list[str]]:
    """Lê a aba "Performance" de um arquivo exportado e devolve um DataFrame
    padronizado, com a coluna Período preenchida com `label`."""
    warnings: list[str] = []
    try:
        df = pd.read_excel(file, sheet_name="Performance")
    except ValueError:
        xls = pd.ExcelFile(file)
        df = pd.read_excel(xls, sheet_name=xls.sheet_names[0])
        warnings.append(f'"{label}": aba "Performance" não encontrada — usei a primeira aba do arquivo.')

    missing = [c for c in KEEP_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f'"{label}" não parece um Excel exportado pelo módulo de análise '
            f'(faltam colunas: {", ".join(missing)}). Envie o arquivo baixado em "Baixar Excel da análise".'
        )

    out = df[KEEP_COLS].copy()
    for c in NUMERIC_COLS:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out[PERIOD_COL] = label
    return out, warnings


def combine(files_labels: list[tuple]) -> tuple[pd.DataFrame, list[str]]:
    """files_labels: [(file, label), ...]. Retorna (df combinado, warnings)."""
    frames = []
    warnings: list[str] = []
    seen_labels: dict[str, int] = {}
    for file, label in files_labels:
        label = (label or "Período").strip() or "Período"
        if label in seen_labels:
            seen_labels[label] += 1
            label = f"{label} ({seen_labels[label]})"
        else:
            seen_labels[label] = 1
        df, warns = load_period_file(file, label)
        frames.append(df)
        warnings.extend(warns)
    combined = pd.concat(frames, ignore_index=True)
    return combined, warnings


def period_order(df: pd.DataFrame) -> list[str]:
    """Ordem de aparição dos períodos (preserva a ordem de upload/rótulo)."""
    return list(dict.fromkeys(df[PERIOD_COL]))


def team_series(df: pd.DataFrame) -> pd.DataFrame:
    periods = period_order(df)
    t = df[df["Analista"] == "Equipe"].copy()
    t[PERIOD_COL] = pd.Categorical(t[PERIOD_COL], categories=periods, ordered=True)
    return t.sort_values(PERIOD_COL)


def analyst_names(df: pd.DataFrame) -> list[str]:
    names = df.loc[df["Analista"] != "Equipe", "Analista"].unique().tolist()
    return sorted(names, key=lambda s: s.lower())


def analyst_series(df: pd.DataFrame, name: str) -> pd.DataFrame:
    periods = period_order(df)
    a = df[df["Analista"] == name].copy()
    a[PERIOD_COL] = pd.Categorical(a[PERIOD_COL], categories=periods, ordered=True)
    return a.sort_values(PERIOD_COL)


def _first_last_delta(series: pd.DataFrame, col: str = "Score Final"):
    s = series.dropna(subset=[col])
    if len(s) < 1:
        return None, None, None
    first_val = s.iloc[0][col]
    last_val = s.iloc[-1][col]
    delta = last_val - first_val if len(s) >= 2 else None
    return first_val, last_val, delta


def compute(df: pd.DataFrame) -> dict:
    periods = period_order(df)
    team_df = team_series(df)
    team_first, team_last, team_delta = _first_last_delta(team_df)

    analysts = []
    for name in analyst_names(df):
        s = analyst_series(df, name)
        first, last, delta = _first_last_delta(s)
        analysts.append(
            {
                "analista": name,
                "series": s,
                "first": first,
                "last": last,
                "delta": delta,
                "n_periods": int(s["Score Final"].notna().sum()),
                "classe_atual": s.dropna(subset=["Score Final"])["Classificação"].iloc[-1] if s["Score Final"].notna().any() else None,
            }
        )

    with_delta = [a for a in analysts if a["delta"] is not None]
    biggest_gain = max(with_delta, key=lambda a: a["delta"]) if with_delta else None
    biggest_drop = min(with_delta, key=lambda a: a["delta"]) if with_delta else None

    return {
        "periods": periods,
        "team_df": team_df,
        "team_first": team_first,
        "team_last": team_last,
        "team_delta": team_delta,
        "analysts": analysts,
        "biggest_gain": biggest_gain,
        "biggest_drop": biggest_drop,
        "raw": df,
    }


def build_temporal_insight(result: dict) -> str:
    parts = []
    periods = result["periods"]
    if len(periods) < 2:
        return "Envie ao menos dois períodos para calcular a evolução."

    td = result["team_delta"]
    if td is not None:
        direction = "subiu" if td > 0.5 else "caiu" if td < -0.5 else "ficou estável"
        parts.append(
            f"O score final da equipe {direction} de {result['team_first']:.1f} ({periods[0]}) "
            f"para {result['team_last']:.1f} ({periods[-1]})"
            + (f", uma variação de {td:+.1f} pontos." if abs(td) > 0.5 else ".")
        )

    g = result["biggest_gain"]
    d = result["biggest_drop"]
    if g and g["delta"] and g["delta"] > 0.5:
        parts.append(f"Maior evolução individual: {g['analista']} ({g['delta']:+.1f} pontos).")
    if d and d["delta"] and d["delta"] < -0.5 and (not g or d["analista"] != g["analista"]):
        parts.append(f"Maior queda individual: {d['analista']} ({d['delta']:+.1f} pontos).")

    return " ".join(parts) if parts else "Sem variação relevante entre os períodos enviados."


def filename_from_periods(periods: list[str]) -> str:
    """A planilha "Performance" não carrega datas brutas (só os scores já
    agregados), então aqui o "período" vem dos rótulos que a própria pessoa
    deu a cada arquivo enviado — ex.: ["Maio","Junho","Julho"] -> "maio_junho_julho_2026"."""
    parts = []
    for p in periods:
        slug = re.sub(r"[^a-z0-9]+", "_", _strip_accents(str(p)).lower()).strip("_")
        if slug:
            parts.append(slug)
    joined = "_".join(parts) if parts else "periodos"
    if not re.search(r"20\d{2}", joined):
        joined += f"_{datetime.now(BRASILIA_TZ).year}"
    return joined
