"""
============================================================
   بوت تيليجرام يبعث إحصائيات قناة يوتيوب يوميًا
============================================================

هذا الملف مقسّم لأقسام واضحة، كل قسم مكتوب عليه اسمه بالعربي
باش ما تتوه وانت تدور على شي. الأقسام بالترتيب:

  1. الإعدادات (البيانات: توكن البوت، مفتاح يوتيوب...) ← عدّل هنا فقط
  2. جلب بيانات القناة من يوتيوب
  3. جلب بيانات آخر فيديو
  4. حفظ واسترجاع الإحصائيات القديمة (باش نحسب نمو اليوم)
  5. تجهيز شكل الرسالة
  6. إرسال الرسالة لتيليجرام
  7. التشغيل الرئيسي (الجزء اللي يشغّل كل شي بالترتيب)

⚠️ تنبيه أمان: بعد ما تعبّي القسم 1 بقيمك الحقيقية، هذا الملف
يصير فيه بيانات حساسة. خله بمستودع (repository) Private على
GitHub، ولا تشاركه مع حد.
"""

import os
import json
import sys
import requests
from datetime import datetime


# ============================================================
#   القسم 1: الإعدادات — عدّل القيم الأربعة هذي بقيمك أنت
# ============================================================
#   افتح الملف بـ GitHub (زر القلم ✏️ أعلى يمين الملف)، امسح
#   القيمة اللي بين علامتي التنصيص "..." وحط قيمتك مكانها،
#   وخلي علامتي التنصيص. بعدها دوس "Commit changes".
# ------------------------------------------------------------
TELEGRAM_BOT_TOKEN = "7877222126:AAG-eEYeERhc4n7Ab3ZeyWNQyNZOG9ZTUwo"
TELEGRAM_CHAT_ID = "7562287602"
YOUTUBE_API_KEY = "AIzaSyARuuiwL1doe2c_Rrq5NQxlSxVl-Lil33E"
YOUTUBE_CHANNEL_ID = "UCB1pJIKkykXhuliewOddx6Q"

# (تلقائي) لو شغّلته عبر GitHub Actions ومعرّف Secrets، تاخذ
# الأولوية على القيم فوق. غير كذا يستخدم القيم اللي كتبتها انت.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", YOUTUBE_API_KEY)
YOUTUBE_CHANNEL_ID = os.environ.get("YOUTUBE_CHANNEL_ID", YOUTUBE_CHANNEL_ID)

# ملف يخزن فيه آخر إحصائية، باش نقدر نحسب "نمو اليوم" مقارنة بالأمس
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
    """يتأكد إن كل البيانات المطلوبة معبّاة قبل ما يبلش"""
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
    """يجيب إحصائيات القناة + آخر فيديو نزل"""
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

    # آخر فيديو نزل
    last_video = get_last_video(uploads_playlist_id)
    channel_info["last_video"] = last_video

    return channel_info


# ============================================================
#   القسم 3: جلب بيانات آخر فيديو نزل بالقناة
# ============================================================
def get_last_video(uploads_playlist_id):
    """يجيب آخر فيديو من قائمة تشغيل الرفعات + إحصائياته"""
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

    # جيب إحصائيات الفيديو (مشاهدات/لايكات/تعليقات)
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
#   القسم 4: حفظ واسترجاع الإحصائيات القديمة (نمو اليوم)
# ============================================================
def load_history():
    """يقرا آخر إحصائية محفوظة (يعني إحصائية أمس)"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_history(data):
    """يحفظ الإحصائية الحالية باش تصير هي "أمس" بالتقرير الجاي"""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def format_number(n):
    """يفرمت الأرقام بفواصل: 12345 → 12,345"""
    return f"{n:,}"


# ============================================================
#   القسم 5: تجهيز شكل الرسالة اللي بتنبعث لتيليجرام
# ============================================================
ARABIC_WEEKDAYS = {
    0: "الاثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس",
    4: "الجمعة", 5: "السبت", 6: "الأحد",
}

DIVIDER = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"


def growth_line(current, previous_value, label):
    """يبني سطر نمو بشكل موحّد (▲ زيادة / ▼ نقصان / ● ثبات)"""
    diff = current - previous_value
    if diff > 0:
        arrow, sign = "▲", "+"
    elif diff < 0:
        arrow, sign = "▼", ""
    else:
        arrow, sign = "●", ""
    return f"   {arrow} {label}: {sign}{format_number(diff)} عن أمس\n"


def build_message(stats, previous):
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    weekday = ARABIC_WEEKDAYS[now.weekday()]

    avg_views_per_video = (
        stats["views"] // stats["video_count"] if stats["video_count"] else 0
    )

    # ---------- الترويسة (اسم القناة يجي تلقائي من يوتيوب) ----------
    msg = (
        f"🔥 *تقرير {stats['title']}* 🔥\n"
        f"🗓 {weekday} • {today}\n"
        f"{DIVIDER}\n\n"
    )

    # ---------- المؤشرات الرئيسية ----------
    msg += "📈 *النظرة العامة*\n\n"

    msg += f"👥 المشتركين: *{format_number(stats['subscribers'])}*\n"
    if previous and "subscribers" in previous:
        msg += growth_line(stats["subscribers"], previous["subscribers"], "التغيّر")

    msg += f"\n👁 إجمالي المشاهدات: *{format_number(stats['views'])}*\n"
    if previous and "views" in previous:
        msg += growth_line(stats["views"], previous["views"], "التغيّر")

    msg += f"\n🎬 عدد الفيديوهات: *{format_number(stats['video_count'])}*\n"
    if previous and "video_count" in previous:
        msg += growth_line(stats["video_count"], previous["video_count"], "فيديو جديد")

    msg += f"\n📊 متوسط المشاهدات لكل فيديو: *{format_number(avg_views_per_video)}*\n"

    # نسبة نمو المشتركين كمؤشر مئوي (لو عندنا أمس)
    if previous and "subscribers" in previous and previous["subscribers"]:
        pct = round(
            ((stats["subscribers"] - previous["subscribers"]) / previous["subscribers"]) * 100, 3
        )
        msg += f"📐 نسبة نمو المشتركين: *{pct}%*\n"

    # ---------- آخر فيديو ----------
    if stats.get("last_video"):
        v = stats["last_video"]
        engagement = (
            round((v["likes"] / v["views"]) * 100, 1) if v["views"] else 0
        )
        comment_rate = (
            round((v["comments"] / v["views"]) * 100, 2) if v["views"] else 0
        )
        msg += (
            f"\n{DIVIDER}\n\n"
            f"🆕 *آخر فيديو منشور*\n\n"
            f"「{v['title']}」\n\n"
            f"   👁 {format_number(v['views'])} مشاهدة\n"
            f"   👍 {format_number(v['likes'])} إعجاب\n"
            f"   💬 {format_number(v['comments'])} تعليق\n"
            f"   💯 نسبة التفاعل (إعجاب/مشاهدة): {engagement}%\n"
            f"   📝 نسبة التعليقات: {comment_rate}%\n\n"
            f"🔗 https://youtu.be/{v['video_id']}\n"
        )

    # ---------- تذييل ----------
    msg += f"\n{DIVIDER}\n🤖 تقرير يومي تلقائي"

    return msg


# ============================================================
#   القسم 6: إرسال الرسالة لتيليجرام
# ============================================================
def send_telegram_message(text):
    """يبعث الرسالة الجاهزة للبوت متاعك على تيليجرام"""
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
#   القسم 7: التشغيل الرئيسي — هذا اللي يشغّل كل شي بالترتيب
# ============================================================
def main():
    # الخطوة أ: تأكد إن البيانات كلها موجودة
    check_env()

    # الخطوة ب: جيب إحصائيات القناة الحالية من يوتيوب
    print("جاري جلب إحصائيات القناة...")
    stats = get_channel_stats()

    # الخطوة ج: جيب إحصائيات أمس (لو موجودة) باش نحسب النمو
    history = load_history()
    previous = history.get("last_stats")

    # الخطوة د: جهّز نص الرسالة
    message = build_message(stats, previous)

    # الخطوة هـ: ابعث الرسالة لتيليجرام
    print("جاري إرسال الرسالة لتيليجرام...")
    send_telegram_message(message)

    # الخطوة و: احفظ إحصائيات اليوم باش تصير "أمس" بالتقرير الجاي
    history["last_stats"] = {
        "subscribers": stats["subscribers"],
        "views": stats["views"],
        "video_count": stats["video_count"],
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    save_history(history)

    print("تم الإرسال بنجاح ✅")


# نقطة انطلاق السكريبت — من هنا يبلش كل شي لما تشغّل الملف
if __name__ == "__main__":
    main()
