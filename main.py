import requests
import feedparser
from bs4 import BeautifulSoup
import json
import time
import os
from requests.auth import HTTPBasicAuth

# === CẤU HÌNH ===
FEED_URL = "https://coin68.com/rss/trang-chu.rss"
WORDPRESS_SITE = "https://infuxy.com"
WP_USER = "Anhtu997-"
WP_APP_PASSWORD = "fIaW iJoa k9W1 OBDZ 1fMy wVnB"
GEMINI_API_KEY = "AIzaSyDqKuh-i2zjx4aXcBRAA08781xTTFKuyVM"
POSTED_URLS_FILE = "posted_urls.txt"

CATEGORY_ID = 80  # category bạn yêu cầu

def fetch_feed():
    return feedparser.parse(FEED_URL)

def extract_article_content_and_image(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = soup.find_all("p")
        content = " ".join(p.get_text() for p in paragraphs)
        img = soup.find("img")
        thumbnail = img["src"] if img and "src" in img.attrs else None
        return content.strip(), thumbnail
    except Exception as e:
        print(f"❌ Lỗi lấy nội dung từ {url}: {e}")
        return "", None

def summarize_with_gemini(content):
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{
                "text": f"Tóm tắt nội dung dưới đây theo phong cách SEO, khoảng 200 từ, tránh trùng lặp:\n\n{content}"
            }]
        }]
    }
    try:
        response = requests.post(endpoint, headers=headers, params={"key": GEMINI_API_KEY}, json=data)
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"❌ Gemini error: {e}")
        return content[:300] + "..."

def translate_title_with_gemini(title):
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{
                "text": f"Dịch tiêu đề sau sang tiếng Anh, chuẩn SEO, ngắn gọn:\n\n{title}"
            }]
        }]
    }
    try:
        response = requests.post(endpoint, headers=headers, params={"key": GEMINI_API_KEY}, json=data)
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"❌ Translate error: {e}")
        return title

def upload_featured_image(image_url):
    try:
        img_data = requests.get(image_url).content
        filename = image_url.split("/")[-1]
        headers = {
            "Content-Disposition": f"attachment; filename={filename}"
        }
        response = requests.post(
            f"{WORDPRESS_SITE}/wp-json/wp/v2/media",
            headers=headers,
            data=img_data,
            auth=HTTPBasicAuth(WP_USER, WP_APP_PASSWORD)
        )
        if response.status_code in [200, 201]:
            return response.json()["id"]
        else:
            print("❌ Không upload được ảnh.")
            return None
    except Exception as e:
        print(f"❌ Upload ảnh lỗi: {e}")
        return None

def post_to_wordpress(title, content, link, thumbnail_url):
    featured_image_id = upload_featured_image(thumbnail_url) if thumbnail_url else None

    data = {
        "title": title,
        "content": content + f"<p><a href='{link}'>Nguồn: Coin68</a></p>",
        "status": "publish",
        "categories": [CATEGORY_ID],
        "tags": ["Coin68", "Crypto"],
    }

    if featured_image_id:
        data["featured_media"] = featured_image_id

    try:
        response = requests.post(
            f"{WORDPRESS_SITE}/wp-json/wp/v2/posts",
            auth=HTTPBasicAuth(WP_USER, WP_APP_PASSWORD),
            headers={"Content-Type": "application/json"},
            json=data
        )
        print(f"✅ Đăng bài: {title} — Status {response.status_code}")
        return response.status_code == 201
    except Exception as e:
        print(f"❌ Post error: {e}")
        return False

def load_posted_urls():
    try:
        with open(POSTED_URLS_FILE, "r") as f:
            return set(line.strip() for line in f.readlines())
    except:
        return set()

def save_posted_url(url):
    with open(POSTED_URLS_FILE, "a") as f:
        f.write(url + "\n")

def main_loop():
    while True:
        print("🔄 Kiểm tra bài mới...")
        feed = fetch_feed()
        posted_urls = load_posted_urls()
        for entry in feed.entries:
            if entry.link in posted_urls:
                continue
            raw_content, thumbnail = extract_article_content_and_image(entry.link)
            if not raw_content or len(raw_content) < 200:
                continue
            summary = summarize_with_gemini(raw_content)
            translated_title = translate_title_with_gemini(entry.title)
            success = post_to_wordpress(translated_title, summary, entry.link, thumbnail)
            if success:
                save_posted_url(entry.link)
        print("✅ Xong một vòng. Ngủ 60 phút...\n")
        time.sleep(3600)

if __name__ == "__main__":
    main_loop()
