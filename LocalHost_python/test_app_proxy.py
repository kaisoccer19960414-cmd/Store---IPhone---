import pytest
from app_proxy import app


@pytest.fixture
def client():
    """Flaskアプリの「テスト専用の分身」を作る。実際のネットワーク通信は発生しない"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_一覧取得はログイン不要で成功する(client):
    """GET /quiz_data は、誰でも(ログインしていなくても)見られるはず"""
    response = client.get('/quiz_data?limit=5')
    assert response.status_code == 200


def test_保存はログインしていないと拒否される(client):
    """POST /quiz_data に、トークン無しでアクセスすると401が返るはず"""
    response = client.post('/quiz_data', json={'question': 'テスト投稿'})
    assert response.status_code == 401
    assert response.get_json()['error'] == 'ログインが必要です'


def test_authors一覧もログイン不要で成功する(client):
    response = client.get('/authors')
    assert response.status_code == 200