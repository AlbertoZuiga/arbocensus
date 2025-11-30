import os
import json
import pathlib

import pytest
from importlib import util
import pathlib

# Load the app module directly from file to avoid PYTHONPATH import issues
app_path = pathlib.Path(__file__).parents[1] / 'app.py'
spec = util.spec_from_file_location('bbox_selector.app', str(app_path))
module = util.module_from_spec(spec)
spec.loader.exec_module(module)
flask_app = module.app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # ensure no DB env variables interfere
    monkeypatch.delenv('ARBOCENSUS_API_DB_URL', raising=False)
    monkeypatch.delenv('ARBOCENSUS_DB_URL', raising=False)
    # ensure GOOGLE_API_KEY is present for template rendering
    monkeypatch.setenv('GOOGLE_API_KEY', 'test-google-key')
    # put cwd to bbox_selector so saved_bbox.json path is predictable
    orig_cwd = os.getcwd()
    os.chdir(pathlib.Path(__file__).parents[1])
    flask_app.config['TESTING'] = True
    client = flask_app.test_client()
    yield client
    os.chdir(orig_cwd)
    # cleanup saved_bbox.json if present
    try:
        p = pathlib.Path(pathlib.Path(__file__).parents[1]) / 'saved_bbox.json'
        if p.exists():
            p.unlink()
    except Exception:
        pass


def test_index(client):
    r = client.get('/')
    assert r.status_code == 200
    # basic sanity: page should contain the Google Maps script key (inlined)
    assert b'googleapis' in r.data or b'Google' in r.data


def test_save_and_trees(client):
    payload = { 'north': -33.4, 'south': -33.6, 'east': -70.4, 'west': -70.8 }
    r = client.post('/save', json=payload)
    assert r.status_code == 200
    j = r.get_json()
    assert j.get('ok') is True

    # saved_bbox.json should exist
    p = pathlib.Path(pathlib.Path(__file__).parents[1]) / 'saved_bbox.json'
    assert p.exists()
    data = json.loads(p.read_text(encoding='utf-8'))
    assert data['north'] == payload['north']

    # /trees should return an ok response and trees list (likely empty in tests)
    r2 = client.get('/trees?north=-33.4&south=-33.6&east=-70.4&west=-70.8')
    assert r2.status_code == 200
    j2 = r2.get_json()
    assert j2.get('ok') is True
    assert isinstance(j2.get('trees'), list)


def test_save_with_trees_payload(client):
    payload = { 'north': -33.4, 'south': -33.6, 'east': -70.4, 'west': -70.8,
                'trees': [ { 'lat': -33.5, 'lng': -70.5, 'meta': {'id': 123} } ] }
    r = client.post('/save', json=payload)
    assert r.status_code == 200
    j = r.get_json()
    assert j.get('ok') is True

    p = pathlib.Path(pathlib.Path(__file__).parents[1]) / 'saved_bbox.json'
    assert p.exists()
    data = json.loads(p.read_text(encoding='utf-8'))
    assert data['north'] == payload['north']
    assert 'trees' in data
    assert isinstance(data['trees'], list)
    assert data['trees'][0]['meta']['id'] == 123
