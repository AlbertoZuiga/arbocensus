DEFAULT_CONFIG_PRESET = "default"

# Named, predefined solver-price profiles the admin can pick when launching a job.
# Each varies only the arc-additive knobs already exposed by pipeline.run(); nothing
# here changes production DEFAULTS (spatial_span_coef, DEFAULT_PENALTIES) — the
# "default" preset reproduces them exactly. The two alternates reuse coefficient
# values already measured in prior experiment cycles (span-c100, arc-w30), offered
# here as named options rather than reopened as defaults.
CONFIG_PRESETS = {
    "default": {
        "label": "Producción (default)",
        "time_span_coef": 0,
        "arc_coef": 1,
    },
    "temporal_span_100": {
        "label": "Span temporal 100 (rutas más compactas, más caminata)",
        "time_span_coef": 100,
        "arc_coef": 1,
    },
    "arc_linear_30": {
        "label": "Peso de arco lineal 30 (menos cruces donde el travel tiene holgura)",
        "time_span_coef": 0,
        "arc_coef": 30,
    },
}

CONFIG_PRESET_CHOICES = [(key, value["label"]) for key, value in CONFIG_PRESETS.items()]
