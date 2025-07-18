import feedparser
import threading
import time
import requests
import spacy
from flask import Flask, jsonify
from flask_cors import CORS

# --- AIモデルの読み込み ---
print("AIモデルを読み込んでいます...（初回起動時は時間がかかる場合があります）")
try:
    nlp = spacy.load('ja_ginza')
    print("AIモデルの読み込みが完了しました。")
except OSError:
    print("\nエラー: GiNZAモデルが見つかりません。")
    exit()

# --- 設定 (Configuration) ---
RSS_URL = "https://news.yahoo.co.jp/rss/categories/domestic.xml"
UPDATE_INTERVAL = 600
GEOCODING_API_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch?q="

# --- グローバル変数 (Global Variables) ---
news_data = []
stop_event = threading.Event()

# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# リアルタイムニュースが取得できなかった場合の、フォールバック用データ
FALLBACK_NEWS_DATA = [
    {
        "title": "【フォールバック表示】東京スカイツリーでイベント開催",
        "link": "#",
        "description": "現在、地名を含むリアルタイムニュースが見つからなかったため、サンプルデータを表示しています。",
        "coords": [35.7101, 139.8107],
        "location_type": "prefecture"
    },
    {
        "title": "【フォールバック表示】大阪城公園が桜で満開に",
        "link": "#",
        "description": "現在、地名を含むリアルタイムニュースが見つからなかったため、サンプルデータを表示しています。",
        "coords": [34.6873, 135.5259],
        "location_type": "city"
    }
]
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

# --- Flaskアプリケーションの初期化 ---
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "https://takumi-egg.github.io"}})

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
    return None

def extract_locations_with_nlp(text):
    """AIを使って地名を構造的に抽出する"""
    doc = nlp(text)
    all_entities = [(ent.text, ent.label_) for ent in doc.ents]
    if not all_entities: return {}
    
    target_labels = ['GPE', 'Province', 'City']
    potential_locations = [ent.text for ent in doc.ents if ent.label_ in target_labels]
    locations = {'prefecture': None, 'city': None, 'town': None}
    ambiguous_names = ['長崎', '宮崎', '鹿児島', '佐賀', '沖縄', '岡山', '富山', '石川', '福井', '山梨', '栃木', '青森', '秋田', '山形', '福島', '岩手', '宮城', '奈良', '岐阜', '静岡', '広島', '山口', '徳島', '高知', '大分', '熊本']

    for loc in potential_locations:
        if loc.endswith(('都', '道', '府', '県')): locations['prefecture'] = loc
        elif loc.endswith(('市', '区')): locations['city'] = loc
        elif loc.endswith(('町', '村')): locations['town'] = loc
        elif loc in ambiguous_names and not locations['prefecture']:
            locations['prefecture'] = loc + '県'
    return locations

def fetch_yahoo_news():
    """Yahoo!ニュースを取得し、AIで地名を抽出、ジオコーディングしてデータを更新する"""
    global news_data
    print(f"\n[{time.ctime()}] リアルタイムニュースの取得を開始します...")
    
    try:
        feed = feedparser.parse(RSS_URL)
        temp_news_list = []
        
        for entry in feed.entries:
            full_text = entry.title + " " + entry.get("description", "")
            found_locations = extract_locations_with_nlp(full_text)
            
            query_parts, final_location_type = [], 'other'
            if found_locations.get('town'):
                query_parts.append(found_locations['town']); final_location_type = 'town'
            if found_locations.get('city'):
                query_parts.append(found_locations['city']);
                if final_location_type == 'other': final_location_type = 'city'
            if found_locations.get('prefecture'):
                query_parts.append(found_locations['prefecture']);
                if final_location_type == 'other': final_location_type = 'prefecture'

            if query_parts:
                geocoding_query = "".join(reversed(query_parts))
                coords = get_coordinates(geocoding_query)
                if coords:
                    temp_news_list.append({
                        "title": entry.title, "link": entry.link,
                        "description": entry.get("description", ""),
                        "coords": coords, "location_type": final_location_type
                    })
        
        sort_order = {'prefecture': 0, 'ward': 1, 'city': 2, 'town': 3, 'village': 4, 'other': 5}
        sorted_news = sorted(temp_news_list, key=lambda item: sort_order.get(item['location_type'], 99))
        news_data = sorted_news
        print(f"[{time.ctime()}] 解析完了。{len(news_data)}件の地名付きニュースが見つかりました。")

    except Exception as e:
        print(f"[{time.ctime()}] ニュース取得処理でエラーが発生しました: {e}")

def update_news_periodically():
    while not stop_event.is_set():
        fetch_yahoo_news()
        stop_event.wait(UPDATE_INTERVAL)

@app.route('/api/news')
def get_news():
    """
    リアルタイムニュースがあればそれを返し、なければフォールバックデータを返すAPI
    """
    if news_data:
        print("リアルタイムニュースデータを返します。")
        return jsonify(news_data)
    else:
        print("リアルタイムニュースが見つからなかったため、フォールバックデータを返します。")
        return jsonify(FALLBACK_NEWS_DATA)

if __name__ == '__main__':
    fetch_yahoo_news()
    update_thread = threading.Thread(target=update_news_periodically)
    update_thread.daemon = True
    update_thread.start()
    app.run(host='0.0.0.0', port=5000)
