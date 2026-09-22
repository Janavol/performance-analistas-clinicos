"""Geração de insight automático por analista, comparado à equipe."""

from __future__ import annotations


def _fmt_score(v):
    return "—" if v is None else f"{v:.1f}"


BLOCK_DEFS = [
    ("score_criticos", "Resultados Críticos"),
    ("score_protocolos", "Protocolos"),
    ("score_pa", "Pronto Atendimento"),
    ("score_ui", "Unidades de Internação"),
    ("score_uca", "UTI Adulto"),
]


def build_insight(a: dict, team: dict) -> str:
    parts: list[str] = []

    diff = None
    if a.get("score_final") is not None and team.get("score_final") is not None:
        diff = a["score_final"] - team["score_final"]

    if diff is None:
        diff_phrase = ""
    elif diff > 1:
        diff_phrase = f", {abs(diff):.1f} pontos acima da média da equipe"
    elif diff < -1:
        diff_phrase = f", {abs(diff):.1f} pontos abaixo da média da equipe"
    else:
        diff_phrase = ", praticamente na média da equipe"

    classe = a.get("classe") or "sem classificação"
    parts.append(
        f"{a['analista']} encerrou o período com score final de {_fmt_score(a.get('score_final'))} "
        f"({classe}){diff_phrase}."
    )

    blocks = []
    for key, label in BLOCK_DEFS:
        value = a.get(key)
        if value is None:
            continue
        team_value = team.get(key)
        gap = (value - team_value) if team_value is not None else None
        blocks.append({"key": key, "label": label, "value": value, "gap": gap})

    if blocks:
        ranked = sorted([b for b in blocks if b["gap"] is not None], key=lambda b: b["gap"], reverse=True)
        strongest = ranked[0] if ranked else None
        weakest = ranked[-1] if ranked else None

        if strongest and strongest["gap"] > 0.5:
            parts.append(
                f"O ponto forte é {strongest['label']} ({_fmt_score(strongest['value'])}), "
                f"{strongest['gap']:.1f} pontos acima da equipe nesse bloco."
            )
        if weakest and weakest["gap"] < -0.5 and (not strongest or weakest["key"] != strongest["key"]):
            parts.append(
                f"O bloco que mais precisa de atenção é {weakest['label']} ({_fmt_score(weakest['value'])}), "
                f"{abs(weakest['gap']):.1f} pontos abaixo da equipe."
            )
        else:
            lowest_abs = min(blocks, key=lambda b: b["value"])
            if lowest_abs["value"] < 70:
                parts.append(
                    f"Vale observar {lowest_abs['label']}, com score de {_fmt_score(lowest_abs['value'])}, "
                    'abaixo da faixa "Bom".'
                )

    if a.get("rc_total", 0) > 0:
        nao_notif = a["rc_total"] - a["rc_notif"]
        if nao_notif > 0:
            parts.append(f"{nao_notif} de {a['rc_total']} resultado(s) crítico(s) não foram notificados no período.")
        else:
            parts.append(f"Todos os {a['rc_total']} resultados críticos foram notificados.")

    return " ".join(parts)
