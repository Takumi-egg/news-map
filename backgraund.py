import threading
import time
from flask import Flask, jsonify
from flask_cors import CORS

# このテスト版では、外部ライブラリはFlaskとCORS以外不要です

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "https://takumi-egg.github.io"}})

# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# テスト専用の固定ニュースデータ
# 実際のニュース取得やAI解析をすべてスキップし、常にこのデータを返すようにします。
TEST_NEWS_DATA = [
    {
        "title": "【テスト】東京スカイツリーでイベント開催",
        "link": "#",
        "description": "これは動作確認用のテストデータです。東京都の座標にピンが立つはずです。",
        "coords": [35.7101, 139.8107], # 東京スカイツリーの座標
        "location_type": "prefecture"
    },
    {
        "title": "【テスト】大阪城公園が桜で満開に",
        "link": "#",
        "description": "これは動作確認用のテストデータです。大阪府の座標にピンが立つはずです。",
        "coords": [34.6873, 135.5259], # 大阪城の座標
        "location_type": "city"
    },
    {
        "title": "【テスト】札幌市で雪まつりの準備開始",
        "link": "#",
        "description": "これは動作確認用のテストデータです。北海道の座標にピンが立つはずです。",
        "coords": [43.0621, 141.3544], # 札幌市の座標
        "location_type": "city"
    }
]
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

@app.route('/api/news')
def get_news():
    """
    テストデータをJSON形式で返すAPI
    """
    print("テストデータのリクエストを受け取りました。")
    return jsonify(TEST_NEWS_DATA)

if __name__ == '__main__':
    # このテスト版では、バックグラウンドでの更新処理は不要です
    print("テストモードでサーバーを起動します。")
    app.run(host='0.0.0.0', port=5000)
