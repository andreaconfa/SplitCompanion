from pathlib import Path


def test_meta_contract_is_explicit_and_additive(client):
    response = client.get('/api/meta')
    assert response.status_code == 200
    data = response.json()
    assert data['api_version'] == 1
    assert data['compatibility'] == {'min_api_version': 1, 'max_api_version': 1}
    assert {'avatars', 'statistics', 'subscription_credits'} <= set(data['capabilities'])
    assert 'secret' not in str(data).lower()


def test_source_archive_fixed_path_only(client, monkeypatch, tmp_path):
    from app.config import get_settings
    source = tmp_path / 'source.tar.gz'
    source.write_bytes(b'public-source-test')
    monkeypatch.setattr(get_settings(), 'source_archive', str(source))
    response = client.get('/api/source')
    assert response.status_code == 200
    assert response.content == b'public-source-test'
    assert 'attachment' in response.headers['content-disposition']
    source.unlink()
    assert client.get('/api/source').status_code == 404


def test_compose_is_app_only_and_persistent():
    root = Path(__file__).resolve().parents[2]
    text = (root / 'compose.yaml').read_text()
    assert text.count('type: bind') == 2
    assert 'create_host_path: false' in text
    assert '127.0.0.1' in text
    assert 'caddy:' not in text
    assert not (root / 'compose.caddy.yaml').exists()
