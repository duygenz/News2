from flask import Flask, jsonify, request
from flask_cors import CORS
import feedparser
import requests
from datetime import datetime
import pytz
import re
from urllib.parse import urljoin, urlparse
import logging
from concurrent.futures import ThreadPoolExecutor
import time

# Configure logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(**name**)

app = Flask(**name**)
CORS(app)

# RSS feeds configuration

RSS_FEEDS = {
‘vietstock_stocks’: {
‘url’: ‘https://vietstock.vn/830/chung-khoan/co-phieu.rss’,
‘name’: ‘VietStock - Cổ Phiếu’,
‘category’: ‘stocks’
},
‘cafef_market’: {
‘url’: ‘https://cafef.vn/thi-truong-chung-khoan.rss’,
‘name’: ‘CafeF - Thị Trường Chứng Khoán’,
‘category’: ‘market’
},
‘vietstock_expert’: {
‘url’: ‘https://vietstock.vn/145/chung-khoan/y-kien-chuyen-gia.rss’,
‘name’: ‘VietStock - Ý Kiến Chuyên Gia’,
‘category’: ‘expert’
},
‘vietstock_business’: {
‘url’: ‘https://vietstock.vn/737/doanh-nghiep/hoat-dong-kinh-doanh.rss’,
‘name’: ‘VietStock - Hoạt Động Kinh Doanh’,
‘category’: ‘business’
},
‘vietstock_dongduong’: {
‘url’: ‘https://vietstock.vn/1328/dong-duong/thi-truong-chung-khoan.rss’,
‘name’: ‘VietStock - Đông Dương’,
‘category’: ‘regional’
}
}

# Cache configuration

CACHE_DURATION = 300  # 5 minutes
cache = {}

def clean_html(text):
“”“Remove HTML tags and clean up text”””
if not text:
return “”
# Remove HTML tags
clean = re.compile(’<.*?>’)
text = re.sub(clean, ‘’, text)
# Clean up whitespace
text = ’ ’.join(text.split())
return text

def parse_date(date_string):
“”“Parse date string to ISO format”””
try:
if hasattr(date_string, ‘timetuple’):
# feedparser struct_time
dt = datetime(*date_string.timetuple()[:6])
else:
# Try to parse string
dt = datetime.strptime(date_string, ‘%a, %d %b %Y %H:%M:%S %z’)

```
    # Convert to Vietnam timezone
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    if dt.tzinfo is None:
        dt = vn_tz.localize(dt)
    else:
        dt = dt.astimezone(vn_tz)
    
    return dt.isoformat()
except Exception as e:
    logger.warning(f"Error parsing date {date_string}: {e}")
    return datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).isoformat()
```

def fetch_rss_feed(feed_key, feed_config):
“”“Fetch and parse a single RSS feed”””
try:
logger.info(f”Fetching RSS feed: {feed_config[‘name’]}”)

```
    # Set headers to mimic a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Fetch with requests first to handle headers
    response = requests.get(feed_config['url'], headers=headers, timeout=10)
    response.raise_for_status()
    
    # Parse with feedparser
    feed = feedparser.parse(response.content)
    
    if feed.bozo:
        logger.warning(f"Feed parsing warning for {feed_key}: {feed.bozo_exception}")
    
    articles = []
    for entry in feed.entries[:20]:  # Limit to 20 latest articles
        try:
            article = {
                'id': getattr(entry, 'id', entry.link),
                'title': clean_html(getattr(entry, 'title', 'Không có tiêu đề')),
                'link': getattr(entry, 'link', ''),
                'description': clean_html(getattr(entry, 'description', getattr(entry, 'summary', ''))),
                'published': parse_date(getattr(entry, 'published_parsed', getattr(entry, 'updated_parsed', datetime.now()))),
                'source': feed_config['name'],
                'category': feed_config['category'],
                'feed_key': feed_key
            }
            
            # Add image if available
            if hasattr(entry, 'media_content') and entry.media_content:
                article['image'] = entry.media_content[0].get('url', '')
            elif hasattr(entry, 'enclosures') and entry.enclosures:
                article['image'] = entry.enclosures[0].get('href', '')
            
            articles.append(article)
        except Exception as e:
            logger.error(f"Error processing entry in {feed_key}: {e}")
            continue
    
    logger.info(f"Successfully fetched {len(articles)} articles from {feed_config['name']}")
    return articles
    
except Exception as e:
    logger.error(f"Error fetching RSS feed {feed_key}: {e}")
    return []
```

def get_cached_news():
“”“Get news from cache or fetch new data”””
current_time = time.time()

```
# Check if cache is valid
if 'data' in cache and 'timestamp' in cache:
    if current_time - cache['timestamp'] < CACHE_DURATION:
        logger.info("Returning cached news data")
        return cache['data']

logger.info("Cache expired or empty, fetching fresh news data")

# Fetch all feeds concurrently
all_articles = []
with ThreadPoolExecutor(max_workers=5) as executor:
    future_to_feed = {
        executor.submit(fetch_rss_feed, feed_key, feed_config): feed_key 
        for feed_key, feed_config in RSS_FEEDS.items()
    }
    
    for future in future_to_feed:
        try:
            articles = future.result(timeout=15)
            all_articles.extend(articles)
        except Exception as e:
            feed_key = future_to_feed[future]
            logger.error(f"Error fetching {feed_key}: {e}")

# Sort by published date (newest first)
all_articles.sort(key=lambda x: x['published'], reverse=True)

# Update cache
cache['data'] = all_articles
cache['timestamp'] = current_time

logger.info(f"Fetched total {len(all_articles)} articles")
return all_articles
```

@app.route(’/’)
def home():
“”“API documentation”””
return jsonify({
‘message’: ‘API Tin Tức Chứng Khoán Việt Nam’,
‘version’: ‘1.0.0’,
‘endpoints’: {
‘/api/news’: ‘Lấy tất cả tin tức’,
‘/api/news?category=stocks’: ‘Lọc theo danh mục’,
‘/api/news?source=vietstock_stocks’: ‘Lọc theo nguồn’,
‘/api/news?limit=10’: ‘Giới hạn số lượng bài viết’,
‘/api/sources’: ‘Danh sách các nguồn tin’
},
‘categories’: [‘stocks’, ‘market’, ‘expert’, ‘business’, ‘regional’],
‘sources’: list(RSS_FEEDS.keys())
})

@app.route(’/api/news’)
def get_news():
“”“Get news with optional filtering”””
try:
# Get query parameters
category = request.args.get(‘category’, ‘’).lower()
source = request.args.get(‘source’, ‘’).lower()
limit = request.args.get(‘limit’, type=int)

```
    # Get all articles
    articles = get_cached_news()
    
    # Apply filters
    if category:
        articles = [a for a in articles if a['category'] == category]
    
    if source:
        articles = [a for a in articles if a['feed_key'] == source]
    
    # Apply limit
    if limit and limit > 0:
        articles = articles[:limit]
    
    return jsonify({
        'success': True,
        'total': len(articles),
        'articles': articles,
        'cached': 'data' in cache and time.time() - cache['timestamp'] < CACHE_DURATION,
        'last_updated': datetime.fromtimestamp(cache.get('timestamp', time.time())).isoformat() if 'timestamp' in cache else None
    })
    
except Exception as e:
    logger.error(f"Error in get_news: {e}")
    return jsonify({
        'success': False,
        'error': str(e),
        'articles': []
    }), 500
```

@app.route(’/api/sources’)
def get_sources():
“”“Get list of available news sources”””
sources = []
for key, config in RSS_FEEDS.items():
sources.append({
‘key’: key,
‘name’: config[‘name’],
‘category’: config[‘category’],
‘url’: config[‘url’]
})

```
return jsonify({
    'success': True,
    'sources': sources
})
```

@app.route(’/api/health’)
def health_check():
“”“Health check endpoint”””
return jsonify({
‘status’: ‘healthy’,
‘timestamp’: datetime.now().isoformat(),
‘cache_status’: ‘active’ if ‘data’ in cache else ‘empty’
})

@app.errorhandler(404)
def not_found(error):
return jsonify({
‘success’: False,
‘error’: ‘Endpoint not found’,
‘message’: ‘Vui lòng kiểm tra lại URL API’
}), 404

@app.errorhandler(500)
def internal_error(error):
return jsonify({
‘success’: False,
‘error’: ‘Internal server error’,
‘message’: ‘Đã xảy ra lỗi server’
}), 500

if **name** == ‘**main**’:
port = int(os.environ.get(‘PORT’, 5000))
app.run(host=‘0.0.0.0’, port=port, debug=False)
