from apps.optimization.experiment_log import PLACEHOLDER, record_experiment


def test_record_experiment_writes_report(settings, tmp_path):
    settings.EXPERIMENTS_DIR = tmp_path

    path = record_experiment(
        slug="unit-test",
        title="Corrida de prueba",
        command="manage.py seed_demo",
        params={"trees": 15, "distribution": "uniform"},
        metrics={"total_routes": 2, "balance_score": 0.959},
        analysis={"que_ocurrio": "Se sembraron 15 árboles."},
    )

    assert path.parent == tmp_path
    assert path.name.endswith("-unit-test.md")

    text = path.read_text(encoding="utf-8")
    assert "# Corrida de prueba" in text
    assert "| total_routes | 2 |" in text
    assert "Se sembraron 15 árboles." in text
    assert "## Hipótesis" in text
    assert PLACEHOLDER in text


def test_record_experiment_creates_missing_directory(settings, tmp_path):
    target = tmp_path / "nested" / "experiments"
    settings.EXPERIMENTS_DIR = target

    path = record_experiment(
        slug="dir-test",
        title="Dir",
        command="cmd",
        params={},
        metrics={"x": 1},
    )

    assert target.is_dir()
    assert path.exists()
