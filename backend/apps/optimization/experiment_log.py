from datetime import UTC, datetime

from django.conf import settings

SECTIONS = [
    ("que_ocurrio", "Qué ocurrió"),
    ("por_que", "Por qué ocurrió"),
    ("posibles_causas", "Posibles causas"),
    ("hipotesis", "Hipótesis"),
    ("como_validar", "Cómo validar cada hipótesis"),
    ("soluciones", "Posibles soluciones o enfoques alternativos"),
    ("experimentos", "Métricas o experimentos recomendados para confirmar"),
]

PLACEHOLDER = "_Pendiente de completar (rellenar tras analizar la corrida)._"


def _render_block(value):
    if value is None:
        return PLACEHOLDER
    if isinstance(value, str):
        return value
    return "\n".join(f"- {item}" for item in value)


def _render_params(params):
    return "\n".join(f"- `{key}`: {value}" for key, value in params.items())


def _render_metrics(metrics):
    lines = ["| Métrica | Valor |", "| --- | --- |"]
    lines += [f"| {key} | {value} |" for key, value in metrics.items()]
    return "\n".join(lines)


def record_experiment(*, slug, title, command, params, metrics, analysis=None):
    analysis = analysis or {}
    now = datetime.now(UTC)

    directory = settings.EXPERIMENTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{now:%Y%m%d-%H%M%S}-{slug}.md"

    parts = [
        f"# {title}",
        "",
        f"- Fecha (UTC): {now.isoformat(timespec='seconds')}",
        f"- Comando: `{command}`",
        "- Parámetros:",
        _render_params(params),
        "",
        "## Métricas",
        "",
        _render_metrics(metrics),
        "",
    ]
    for key, heading in SECTIONS:
        parts += [f"## {heading}", "", _render_block(analysis.get(key)), ""]

    path.write_text("\n".join(parts), encoding="utf-8")
    return path
