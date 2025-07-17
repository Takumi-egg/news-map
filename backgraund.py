import feedparser
import threading
import time
import requests
import spacy # AI(spaCy)ライブラリをインポート
from flask import Flask, jsonify
from flask_cors import CORS

# --- AIモデルの読み込み ---
print("AIモデルを読み込んでいます...（初回起動時は時間がかかる場合があります）")
try:
    nlp = spacy.load('ja_ginza')
    print("AIモデルの読み込みが完了しました。")
except OSError:
    print("\nエラー: GiNZAモデルが見つかりません。")
    print("インストールコマンドを試してください: py -m pip install spacy ginza ja-ginza\n")
    exit()

# --- 設定 (Configuration) ---
RSS_URL = "https://news.yahoo.co.jp/rss/categories/domestic.xml"
UPDATE_INTERVAL = 600
GEOCODING_API_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch?q="

# --- グローバル変数 (Global Variables) ---
news_data = []
stop_event = threading.Event()

# --- Flaskアプリケーションの初期化 ---
app = Flask(__name__)
CORS(app)

def get_coordinates(place_name):
    """地名から国土地理院APIを使って緯度・経度を取得する関数"""
    try:
        response = requests.get(f"{GEOCODING_API_URL}{place_name}")
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                lon, lat = data[0]["geometry"]["coordinates"]
                print(f"  -> ジオコーディング成功: {place_name} -> [{lat}, {lon}]")
                return [lat, lon]
    except Exception as e:
        print(f"  -> ジオコーディング中にエラーが発生しました: {place_name}, Error: {e}")
    
    print(f"  -> ジオコーディング失敗: {place_name}")
    return None

# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# 新しい地名抽出ロジック
def extract_locations_with_nlp(text):
    """
    AI(spaCy/GiNZA)を使ってテキストから地名を構造的に抽出する。
    戻り値: {'prefecture': '〇〇県', 'city': '〇〇市', 'town': '〇〇町'} のような辞書
    """
    doc = nlp(text)
    
    all_entities = [(ent.text, ent.label_) for ent in doc.ents]
    if all_entities:
        print(f"  AIが認識した全固有名詞: {all_entities}")
    else:
        print("  AIは固有名詞を認識できませんでした。")

    target_labels = ['GPE', 'Province', 'City']
    potential_locations = [ent.text for ent in doc.ents if ent.label_ in target_labels]
    
    # 抽出した地名を格納する辞書
    locations = {
        'prefecture': None,
        'city': None, # 市と区
        'town': None  # 町と村
    }

    # 県名と同じ名前を持つ市名のリスト（「長崎」のような曖昧さを解決するため）
    ambiguous_names = ['長崎', '宮崎', '鹿児島', '佐賀', '沖縄', '岡山', '富山', '石川', '福井', '山梨', '栃木', '青森', '秋田', '山形', '福島', '岩手', '宮城', '奈良', '岐阜', '静岡', '広島', '山口', '徳島', '高知', '大分', '熊本']

    # 抽出された地名候補を分類し、辞書に格納する
    for loc in potential_locations:
        if loc.endswith(('都', '道', '府', '県')):
            locations['prefecture'] = loc
        elif loc.endswith('市') or loc.endswith('区'):
            locations['city'] = loc
        elif loc.endswith('町') or loc.endswith('村'):
            locations['town'] = loc
        # 「長崎」のように県名にも市名にもなりうる単語の処理
        elif loc in ambiguous_names:
            # すでに県が特定されていない場合に限り、これを県とみなす
            if not locations['prefecture']:
                locations['prefecture'] = loc + '県'

    print(f"  -> 構造化された地名: {locations}")
    return locations
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

def fetch_yahoo_news():
    """Yahoo!ニュースを取得し、AIで地名を抽出、ジオコーディングしてデータを更新する"""
    global news_data
    print(f"\n[{time.ctime()}] 国内ニュースの取得を開始します...")
    
    try:
        feed = feedparser.parse(RSS_URL)
        temp_news_list = []
        
        print("\n--- 各ニュースの解析プロセス ---")
        for entry in feed.entries:
            print(f"\n[解析対象] {entry.title}")

            full_text = entry.title + " " + entry.get("description", "")
            # ★ 構造化された地名データを取得
            found_locations = extract_locations_with_nlp(full_text)
            
            # ★ ジオコーディング用のクエリを作成
            query_parts = []
            final_location_type = 'other' # ソート用のタイプ

            # 最も詳細な地名から順にクエリ部品を追加
            if found_locations.get('town'):
                query_parts.append(found_locations['town'])
                final_location_type = 'town'
            if found_locations.get('city'):
                query_parts.append(found_locations['city'])
                if final_location_type == 'other': final_location_type = 'city'
            if found_locations.get('prefecture'):
                query_parts.append(found_locations['prefecture'])
                if final_location_type == 'other': final_location_type = 'prefecture'

            if query_parts:
                # 正しい住所の順（県→市→町）になるようにリストを逆順にして結合
                geocoding_query = "".join(reversed(query_parts))
                print(f"  -> ジオコーディングクエリ: '{geocoding_query}'")
                coords = get_coordinates(geocoding_query)
                
                if coords:
                    temp_news_list.append({
                        "title": entry.title,
                        "link": entry.link,
                        "description": entry.get("description", "概要はありません。"),
                        "coords": coords,
                        "location_type": final_location_type
                    })
                    print("  => 結果: このニュースをリストに追加します。")
                else:
                    print("  => 結果: 座標が取得できなかったため、リストに追加しません。")
            else:
                print("  => 結果: 地名が抽出できなかったため、リストに追加しません。")

        # 抽出したニュースリストを、地名の種類に基づいてソートする
        sort_order = {
            'prefecture': 0, 'ward': 1, 'city': 2, 'town': 3, 'village': 4, 'other': 5
        }
        sorted_news = sorted(temp_news_list, key=lambda item: sort_order.get(item['location_type'], 99))
        news_data = sorted_news

        print(f"\n--- 解析・ソート完了 ---")
        print(f"[{time.ctime()}] {len(news_data)}件の位置情報付き国内ニュースを取得しました。")

    except Exception as e:
        print(f"[{time.ctime()}] ニュース取得処理でエラーが発生しました: {e}")

def update_news_periodically():
    while not stop_event.is_set():
        fetch_yahoo_news()
        stop_event.wait(UPDATE_INTERVAL)

@app.route('/api/news')
def get_news():
    return jsonify(news_data)

if __name__ == '__main__':
    fetch_yahoo_news()
    update_thread = threading.Thread(target=update_news_periodically)
    update_thread.daemon = True
    update_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=True)
