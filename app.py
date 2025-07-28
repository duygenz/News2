import feedparser
from fastapi import FastAPI
from sentence_transformers import SentenceTransformer

# Initialize FastAPI app
app = FastAPI()

# Load a very lightweight sentence transformer model
# 'all-MiniLM-L6-v2' is a great choice: it's small and fast.
model = SentenceTransformer('all-MiniLM-L6-v2')

# List of your RSS feeds
RSS_FEEDS = [
    "https://vietstock.vn/830/chung-khoan/co-phieu.rss",
    "https://cafef.vn/thi-truong-chung-khoan.rss",
    "https://vietstock.vn/145/chung-khoan/y-kien-chuyen-gia.rss",
    "https://vietstock.vn/737/doanh-nghiep/hoat-dong-kinh-doanh.rss",
    "https://vietstock.vn/1328/dong-duong/thi-truong-chung-khoan.rss"
]

@app.get("/news-vectors")
def get_news_vectors():
    """
    Fetches news from RSS feeds and returns titles and their corresponding vectors.
    """
    news_items = []
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            # We only process entries that have a title
            if hasattr(entry, 'title'):
                news_items.append(entry.title)

    # Generate vectors for all the collected titles
    if news_items:
        vectors = model.encode(news_items).tolist() # .tolist() to make it JSON serializable
        # Combine titles and vectors into a list of dictionaries
        response_data = [{"title": title, "vector": vector} for title, vector in zip(news_items, vectors)]
        return response_data

    return {"message": "No news items found."}

# A simple root endpoint to check if the API is running
@app.get("/")
def read_root():
    return {"status": "API is running"}

