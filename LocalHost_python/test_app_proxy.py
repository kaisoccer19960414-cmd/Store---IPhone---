import pytest
from app_proxy import app, create_jwt_token


@pytest.fixture
def client():
    """Flaskアプリの「テスト専用の分身」を作る。実際のネットワーク通信は発生しない"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def auth_headers():
    """本物のパスコード入力を再現する代わりに、アプリ自身の関数で正しいトークンを直接発行する"""
    token = create_jwt_token()
    return {'Authorization': f'Bearer {token}'}


def test_一覧取得はログイン不要で成功する(client):
    """GET /quiz_data は、誰でも(ログインしていなくても)見られるはず"""
    response = client.get('/quiz_data?limit=5')
    assert response.status_code == 200


def test_保存はログインしていないと拒否される(client):
    """POST /quiz_data に、トークン無しでアクセスすると401が返るはず"""
    response = client.post('/quiz_data', json={'question': 'テスト投稿'})
    assert response.status_code == 401
    assert response.get_json()['error'] == 'ログインが必要です'


def test_ログイン済みでも空のquestionは拒否される(client, auth_headers):
    """ログインしていても、questionが空文字なら400が返るはず"""
    response = client.post('/quiz_data', json={'question': ''}, headers=auth_headers)
    assert response.status_code == 400
    assert response.get_json()['error'] == 'question is required'


def test_authors一覧もログイン不要で成功する(client):
    response = client.get('/authors')
    assert response.status_code == 200