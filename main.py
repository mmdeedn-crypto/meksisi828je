"""
============================================================
   بوت تيليجرام يبعث إحصائيات قناة يوتيوب يوميًا
============================================================
"""

import os
import json
import sys
import requests
from datetime import datetime


# ============================================================
#   القسم 1: الإعدادات المعجّبة ببياناتك
# ============================================================
TELEGRAM_BOT_TOKEN = "7877222126:AAG-eEYeERhc4n7Ab3ZeyWNQyNZOG9ZTUwo"
TELEGRAM_CHAT_ID = "7562287602"
YOUTUBE_API_KEY = "AIzaSyARuuiwL1doe2c_Rrq5NQxISxVI-LiL33E"
YOUTUBE_CHANNEL_ID = "UCB1pJIKkykXhuliewOddx6Q"

# البيئة الاحتياطية لـ GitHub Actions
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", YOUTUBE_API_KEY)
YOUTUBE_CHANNEL_ID = os.environ.get("YOUTUBE_CHANNEL_ID", YOUTUBE_CHANNEL_ID)

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "stats_history.json")

_PLACEHOLDERS = {
    "TELEGRAM_BOT_TOKEN": "ضع_توكن_البوت_هنا",
    "TELEGRAM_CHAT_ID": "ضع_آيدي_الشات_هنا",
    "YOUTUBE_API_KEY": "ضع_مفتاح_يوتيوب_هنا",
    "YOUTUBE_CHANNEL_ID": "ضع_آيدي_القناة_هنا",
}
REQUIRED_VARS = {
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    "YOUTUBE_API_KEY": YOUTUBE_API_KEY,
    "YOUTUBE_CHANNEL_ID": YOUTUBE_CHANNEL_ID,
}


def check_env():
    missing = [
        k for k, v in REQUIRED_VARS.items()
        if not v or v == _PLACEHOLDERS[k]
    ]
    if missing:
        print(f"خطأ: لازم تعبّي هالقيم بالقسم 1 أعلى الملف: {', '.join(missing)}")
        sys.exit(1)


# ============================================================
#   القسم 2: جلب بيانات القناة من يوتيوب
# ============================================================
def get_channel_stats():
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {
        "part": "statistics,snippet,contentDetails",
        "id": YOUTUBE_CHANNEL_ID,
        "key": YOUTUBE_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("items"):
        raise ValueError("ما لقيتش القناة، تأكد من YOUTUBE_CHANNEL_ID")

    item = data["items"][0]
    stats = item["statistics"]
    snippet = item["snippet"]
    uploads_playlist_id = item["contentDetails"]["relatedPlaylists"]["uploads"]

    channel_info = {
        "title": snippet["title"],
        "subscribers": int(stats.get("subscriberCount", 0)),
        "views": int(stats.get("viewCount", 0)),
        "video_count": int(stats.get("videoCount", 0)),
    }

    last_video = get_last_video(uploads_playlist_id)
    channel_info["last_video"] = last_video

    return channel_info


# ============================================================
#   القسم 3: جلب بيانات آخر فيديو
# ============================================================
def get_last_video(uploads_playlist_id):
    url = "https://www.googleapis.com/youtube/v3/playlistItems"
    params = {
        "part": "snippet",
        "playlistId": uploads_playlist_id,
        "maxResults": 1,
        "key": YOUTUBE_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("items"):
        return None

    video_snippet = data["items"][0]["snippet"]
    video_id = video_snippet["resourceId"]["videoId"]

    stats_url = "https://www.googleapis.com/youtube/v3/videos"
    stats_params = {
        "part": "statistics",
        "id": video_id,
        "key": YOUTUBE_API_KEY,
    }
    stats_resp = requests.get(stats_url, params=stats_params, timeout=15)
    stats_resp.raise_for_status()
    stats_data = stats_resp.json()
    video_stats = stats_data["items"][0]["statistics"] if stats_data.get("items") else {}

    return {
        "title": video_snippet["title"],
        "video_id": video_id,
        "published_at": video_snippet["publishedAt"],
        "views": int(video_stats.get("viewCount", 0)),
        "likes": int(video_stats.get("likeCount", 0)),
        "comments": int(video_stats.get("commentCount", 0)),
    }


# ============================================================
#   القسم 4: حفظ واسترجاع الإحصائيات
# ============================================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_history(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def format_number(n):
    return f"{n:,}"


# ============================================================
#   القسم 5: تجهيز شكل الرسالة
# ============================================================
def build_message(stats, previous):
    today = datetime.now().strftime("%Y-%m-%d")

    subs_growth_line = ""
    if previous:
        diff = stats["subscribers"] - previous.get("subscribers", stats["subscribers"])
        sign = "+" if diff >= 0 else ""
        subs_growth_line = f"   └ نمو اليوم: {sign}{format_number(diff)}\n"

    views_growth_line = ""
    if previous:
        diff_views = stats["views"] - previous.get("views", stats["views"])
        sign = "+" if diff_views >= 0 else ""
        views_growth_line = f"   └ نمو اليوم: {sign}{format_number(diff_views)}\n"

    msg = (
        f"📊 *تقرير قناة {stats['title']}*\n"
        f"📅 {today}\n\n"
        f"👥 *المشتركين:* {format_number(stats['subscribers'])}\n"
        f"{subs_growth_line}"
        f"👁 *إجمالي المشاهدات:* {format_number(stats['views'])}\n"
        f"{views_growth_line}"
        f"🎬 *عدد الفيديوهات:* {format_number(stats['video_count'])}\n"
    )

    if stats.get("last_video"):
        v = stats["last_video"]
        msg += (
            f"\n🆕 *آخر فيديو:*\n"
            f"«{v['title']}»\n"
            f"   👁 {format_number(v['views'])}  "
            f"👍 {format_number(v['likes'])}  "
            f"💬 {format_number(v['comments'])}\n"
            f"   🔗 https://youtu.be/{v['video_id']}\n"
        )

    return msg


# ============================================================
#   القسم 6: إرسال الرسالة لتيليجرام
# ============================================================
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, data=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ============================================================
#   القسم 7: التشغيل الرئيسي
# ============================================================
def main():
    check_env()

    print("جاري جلب إحصائيات القناة...")
    stats = get_channel_stats()

    history = load_history()
    previous = history.get("last_stats")

    message = build_message(stats, previous)

    print("جاري إرسال الرسالة لتيليجرام...")
    send_telegram_message(message)

    history["last_stats"] = {
        "subscribers": stats["subscribers"],
        "views": stats["views"],
        "video_count": stats["video_count"],
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    save_history(history)

    print("تم الإرسال بنجاح ✅")


if __name__ == "__main__":
    main()
