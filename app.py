from flask import Flask, jsonify, request
from flask_cors import CORS
import feedparser
import requests
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
import re
import hashlib
import threading
import time
from collections import defaultdict
import logging

# Cấu hình logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(**name**)

app = Flask(**name**)
CORS(app)

# Cấu hình múi giờ Việt Nam

VN_TZ = pytz.timezone(‘Asia/Ho_Chi_Minh’)

# RSS feeds configuration

RSS_FEEDS = {
‘vietstock_stocks’: {
‘url’: ‘https://vietstock.vn/830/chung-khoan/co-phieu.rss’,
‘category’: ‘Cổ phiếu’,
‘source’: ‘VietStock’
},
‘cafef_market’: {
‘url’: ‘https://cafef.vn/thi-truong-chung-khoan.rss’,
‘category’: ‘Thị trường’,
‘source’: ‘CafeF’
},
‘vietstock_expert’: {
‘url’: ‘https://vietstock.vn/145/chung-khoan/y-kien-chuyen-gia.rss’,
‘category’: ‘Ý kiến chuyên gia’,
‘source’: ‘VietStock’
},
‘vietstock_business’: {
‘url’: ‘https://vietstock.vn/737/doanh-nghiep/hoat-dong-kinh-doanh.rss’,
‘category’: ‘Hoạt động kinh doanh’,
‘source’: ‘VietStock’
},
‘vietstock_dongduong’: {
‘url’: ‘https://vietstock.vn/1328/dong-duong/thi-truong-chung-khoan.rss’,
‘category’: ‘Thị trường Đông Dương’,
‘source’: ‘VietStock’
}
}

# Cache để lưu trữ tin tức

news_cache = defaultdict(list)
last_update = None
cache_duration = 300  # 5 phút

class NewsProcessor:
@staticmethod
def clean_html(text):
“”“Làm sạch HTML và định dạng text”””
if not text:
return “”

```
    # Parse HTML
    soup = BeautifulSoup(text, 'html.parser')
    
    # Loại bỏ các thẻ không cần thiết
    for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
        tag.decompose()
    
    # Lấy text sạch
    clean_text = soup.get_text()
    
    # Làm sạch khoảng trắng
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    return clean_text

@staticmethod
def extract_summary(description, max_length=200):
    """Tạo tóm tắt từ mô tả"""
    if not description:
        return ""
    
    clean_desc = NewsProcessor.clean_html(description)
    
    # Tách câu
    sentences = re.split(r'[.!?]+', clean_desc)
    
    summary = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > 10:  # Bỏ qua câu quá ngắn
            if len(summary + sentence) < max_length:
                summary += sentence + ". "
            else:
                break
    
    return summary.strip()

@staticmethod
def generate_id(title, link):
    """Tạo ID duy nhất cho bài viết"""
    content = f"{title}{link}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()

@staticmethod
def parse_date(date_str):
    """Parse ngày tháng từ RSS"""
    try:
        if date_str:
            # Thử parse theo format RFC 2822
            parsed_date = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
            return parsed_date.astimezone(VN_TZ)
    except:
        pass
    
    # Nếu không parse được, dùng thời gian hiện tại
    return datetime.now(VN_TZ)
```

def fetch_rss_feed(feed_key, feed_config):
“”“Lấy dữ liệu từ một RSS feed”””
try:
logger.info(f”Fetching {feed_key} from {feed_config[‘url’]}”)

```
    # Cấu hình headers để tránh bị block
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Fetch RSS feed
    response = requests.get(feed_config['url'], headers=headers, timeout=10)
    response.raise_for_status()
    
    # Parse RSS
    feed = feedparser.parse(response.content)
    
    articles = []
    for entry in feed.entries[:20]:  # Lấy tối đa 20 bài mới nhất
        try:
            article = {
                'id': NewsProcessor.generate_id(entry.title, entry.link),
                'title': entry.title.strip(),
                'link': entry.link,
                'summary': NewsProcessor.extract_summary(
                    entry.get('summary', '') or entry.get('description', '')
                ),
                'published': NewsProcessor.parse_date(
                    entry.get('published', '')
                ).isoformat(),
                'category': feed_config['category'],
                'source': feed_config['source'],
                'feed_key': feed_key
            }
            
            # Thêm hình ảnh nếu có
            if hasattr(entry, 'media_content') and entry.media_content:
                article['image'] = entry.media_content[0].get('url', '')
            elif hasattr(entry, 'enclosures') and entry.enclosures:
                article['image'] = entry.enclosures[0].get('href', '')
            
            articles.append(article)
            
        except Exception as e:
            logger.error(f"Error processing entry from {feed_key}: {str(e)}")
            continue
    
    logger.info(f"Successfully fetched {len(articles)} articles from {feed_key}")
    return articles
    
except Exception as e:
    logger.error(f"Error fetching {feed_key}: {str(e)}")
    return []
```

def update_news_cache():
“”“Cập nhật cache tin tức”””
global last_update

```
logger.info("Starting news cache update...")

all_articles = []
threads = []

# Fetch tất cả feeds song song
def fetch_feed(feed_key, feed_config):
    articles = fetch_rss_feed(feed_key, feed_config)
    all_articles.extend(articles)

for feed_key, feed_config in RSS_FEEDS.items():
    thread = threading.Thread(target=fetch_feed, args=(feed_key, feed_config))
    threads.append(thread)
    thread.start()

# Đợi tất cả threads hoàn thành
for thread in threads:
    thread.join()

# Sắp xếp theo thời gian mới nhất
all_articles.sort(key=lambda x: x['published'], reverse=True)

# Cập nhật cache
news_cache.clear()
news_cache['all'] = all_articles

# Phân loại theo category
for article in all_articles:
    category = article['category']
    if category not in news_cache:
        news_cache[category] = []
    news_cache[category].append(article)

# Phân loại theo source
for article in all_articles:
    source = article['source']
    source_key = f"source_{source.lower()}"
    if source_key not in news_cache:
        news_cache[source_key] = []
    news_cache[source_key].append(article)

last_update = datetime.now(VN_TZ)
logger.info(f"Cache updated successfully with {len(all_articles)} articles")
```

def should_update_cache():
“”“Kiểm tra có cần cập nhật cache không”””
if last_update is None:
return True

```
time_since_update = datetime.now(VN_TZ) - last_update
return time_since_update.total_seconds() > cache_duration
```

# API Routes

@app.route(’/’)
def home():
“”“Trang chủ API”””
return jsonify({
‘message’: ‘Vietnamese Stock News API’,
‘version’: ‘1.0.0’,
‘endpoints’: {
‘all_news’: ‘/api/news’,
‘by_category’: ‘/api/news/category/<category>’,
‘by_source’: ‘/api/news/source/<source>’,
‘search’: ‘/api/news/search?q=<query>’,
‘latest’: ‘/api/news/latest/<count>’,
‘stats’: ‘/api/stats’
},
‘last_update’: last_update.isoformat() if last_update else None
})

@app.route(’/api/news’)
def get_all_news():
“”“Lấy tất cả tin tức”””
if should_update_cache():
update_news_cache()

```
page = request.args.get('page', 1, type=int)
per_page = request.args.get('per_page', 20, type=int)

# Giới hạn per_page
per_page = min(per_page, 100)

all_articles = news_cache.get('all', [])

# Phân trang
start = (page - 1) * per_page
end = start + per_page
articles = all_articles[start:end]

return jsonify({
    'success': True,
    'data': articles,
    'pagination': {
        'page': page,
        'per_page': per_page,
        'total': len(all_articles),
        'pages': (len(all_articles) + per_page - 1) // per_page
    },
    'last_update': last_update.isoformat() if last_update else None
})
```

@app.route(’/api/news/category/<category>’)
def get_news_by_category(category):
“”“Lấy tin tức theo danh mục”””
if should_update_cache():
update_news_cache()

```
articles = news_cache.get(category, [])

return jsonify({
    'success': True,
    'data': articles,
    'category': category,
    'count': len(articles),
    'last_update': last_update.isoformat() if last_update else None
})
```

@app.route(’/api/news/source/<source>’)
def get_news_by_source(source):
“”“Lấy tin tức theo nguồn”””
if should_update_cache():
update_news_cache()

```
source_key = f"source_{source.lower()}"
articles = news_cache.get(source_key, [])

return jsonify({
    'success': True,
    'data': articles,
    'source': source,
    'count': len(articles),
    'last_update': last_update.isoformat() if last_update else None
})
```

@app.route(’/api/news/search’)
def search_news():
“”“Tìm kiếm tin tức”””
if should_update_cache():
update_news_cache()

```
query = request.args.get('q', '').lower()
if not query:
    return jsonify({
        'success': False,
        'message': 'Query parameter is required'
    }), 400

all_articles = news_cache.get('all', [])

# Tìm kiếm trong title và summary
filtered_articles = [
    article for article in all_articles
    if query in article['title'].lower() or query in article['summary'].lower()
]

return jsonify({
    'success': True,
    'data': filtered_articles,
    'query': query,
    'count': len(filtered_articles),
    'last_update': last_update.isoformat() if last_update else None
})
```

@app.route(’/api/news/latest/<int:count>’)
def get_latest_news(count):
“”“Lấy tin tức mới nhất”””
if should_update_cache():
update_news_cache()

```
# Giới hạn count
count = min(count, 50)

all_articles = news_cache.get('all', [])
latest_articles = all_articles[:count]

return jsonify({
    'success': True,
    'data': latest_articles,
    'count': len(latest_articles),
    'last_update': last_update.isoformat() if last_update else None
})
```

@app.route(’/api/stats’)
def get_stats():
“”“Thống kê API”””
if should_update_cache():
update_news_cache()

```
all_articles = news_cache.get('all', [])

# Thống kê theo category
category_stats = defaultdict(int)
source_stats = defaultdict(int)

for article in all_articles:
    category_stats[article['category']] += 1
    source_stats[article['source']] += 1

return jsonify({
    'success': True,
    'stats': {
        'total_articles': len(all_articles),
        'by_category': dict(category_stats),
        'by_source': dict(source_stats),
        'last_update': last_update.isoformat() if last_update else None,
        'cache_duration_seconds': cache_duration
    }
})
```

@app.route(’/api/refresh’)
def refresh_cache():
“”“Refresh cache thủ công”””
update_news_cache()
return jsonify({
‘success’: True,
‘message’: ‘Cache refreshed successfully’,
‘last_update’: last_update.isoformat()
})

# Error handlers

@app.errorhandler(404)
def not_found(error):
return jsonify({
‘success’: False,
‘message’: ‘Endpoint not found’
}), 404

@app.errorhandler(500)
def internal_error(error):
return jsonify({
‘success’: False,
‘message’: ‘Internal server error’
}), 500

# Background task để cập nhật cache định kỳ

def background_updater():
“”“Cập nhật cache trong background”””
while True:
try:
if should_update_cache():
update_news_cache()
time.sleep(60)  # Kiểm tra mỗi phút
except Exception as e:
logger.error(f”Background update error: {str(e)}”)
time.sleep(60)

if **name** == ‘**main**’:
# Khởi tạo cache lần đầu
update_news_cache()

```
# Bắt đầu background updater
updater_thread = threading.Thread(target=background_updater, daemon=True)
updater_thread.start()

# Chạy app
port = int(os.environ.get('PORT', 5000))
app.run(host='0.0.0.0', port=port, debug=False)
```