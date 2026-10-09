import os
import sqlite3
import logging
import asyncio
from datetime import datetime, timezone, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN ortam değişkeni tanımlı değil.")

DB_PATH = "/data/bot.sqlite3" if os.path.isdir("/data") and os.access("/data", os.W_OK) else "bot.sqlite3"
IMAGE_PATH = os.path.join(os.path.dirname(__file__), "assets", "welcome.png")
CONTACT = "İletişim @jakeperr"
MENU_TEXT = "Ana menü: Lütfen bir bölüm seçin."

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

FOREX_TEXT = """📊 Forex Insights (Eğitim)

Forex, farklı ülke para birimlerinin birbirine karşı değerinin işlem gördüğü küresel döviz piyasasıdır. Bu bölümde canlı fiyat veya alım-satım sinyali yoktur; yalnızca eğitim amaçlı kavramlar yer alır.

• Para çifti: EUR/USD gibi iki para biriminin oranı.
• Pip: Döviz fiyatındaki en küçük standart hareket birimi.
• Spread: Alış ve satış fiyatı arasındaki fark.
• Kaldıraç: Küçük teminatla büyük pozisyon açmayı sağlar; riski artırır.
• Temel analiz: Faiz, enflasyon, merkez bankası kararları gibi etkenler.
• Teknik analiz: Grafik, destek/direnç, trend ve indikatörler.

Risk uyarısı: Forex yüksek kaldıraç nedeniyle hızlı kayıplara yol açabilir. Bu içerik yatırım tavsiyesi değildir."""

CRYPTO_TEXT = """₿ Crypto Insights (Eğitim)

Kripto varlıklar, blockchain adı verilen dağıtık defter teknolojisi üzerinde çalışabilir. Bu bölüm canlı fiyat, haber veya sinyal içermez.

• Blockchain: İşlemlerin bloklar halinde zincirlendiği dağıtık kayıt sistemi.
• Cüzdan: Kripto varlıkları saklamak için kullanılan araç; seed phrase gizli tutulmalıdır.
• Volatilite: Kripto fiyatları kısa sürede çok sert hareket edebilir.
• Merkeziyetsizlik: Bazı ağlarda aracı kurum olmadan işlem yapılabilir.
• Akıllı sözleşme: Koşullar gerçekleştiğinde otomatik çalışan kod.

Güvenlik: Şifre, OTP, özel anahtar veya seed phrase paylaşmayın. Bu içerik yatırım tavsiyesi değildir."""

MARKET_TEXT = """🌍 Market Overview (Eğitim)

Bu bölüm forex ve kripto piyasalarına genel bir bakış sunar. Canlı piyasa verisi bağlı değildir; fiyat, haber veya ekonomik takvim gösterilmez.

Forex piyasası genellikle hafta içi 24 saat açıktır ve para çiftleri üzerinden işlem görür. Kripto piyasası ise 7/24 açık olabilir ve yüksek volatilite gösterebilir.

Ortak riskler:
• Kaldıraç ve volatilite.
• Likidite farklılıkları.
• Duygusal kararlar.
• Yetersiz risk yönetimi.

Eğitim amacı: Temel kavramları öğrenmek, riskleri tanımak ve bilinçli karar altyapısı oluşturmaktır. Yatırım tavsiyesi değildir."""

ABOUT_TEXT = """ℹ️ Hakkında

Güncel Giriş Adresleri botu; forex, kripto para, döviz hareketleri, finansal terminoloji ve genel piyasa kavramları hakkında Türkçe eğitim içeriği sunar.

Bu bot:
• Canlı fiyat, sinyal veya yatırım tavsiyesi vermez.
• Kullanıcıdan şifre, OTP, cüzdan seed phrase veya özel anahtar istemez.
• Telegram kullanıcı ID’nizi ve zaman damgalarını yalnızca çalışma ve toplu istatistik için saklar.

Yasal uyarı: İçerik yalnızca genel bilgilendirme ve eğitim amaçlıdır; finansal veya yatırım tavsiyesi değildir."""

SCHEDULED_TIPS = [
    "📘 Forex eğitimi: Pip, fiyattaki en küçük standart hareket birimidir. Örneğin EUR/USD'de 1 pip genellikle 0.0001'dir.",
    "📘 Kripto eğitimi: Volatilite, fiyatın kısa sürede sert dalgalanmasıdır. Risk yönetimi bu nedenle önemlidir.",
    "📘 Risk yönetimi: Bir işlemde riske edilecek tutar, toplam sermayenin küçük bir yüzdesiyle sınırlandırılmalıdır.",
    "📘 Forex eğitimi: Spread, alış ve satış fiyatı arasındaki farktır; işlem maliyetini etkiler.",
    "📘 Kripto eğitimi: Seed phrase, cüzdanınıza erişim sağlar. Kimseyle paylaşılmamalıdır.",
    "📘 Piyasa eğitimi: Kaldıraç kazançları büyütebilir gibi görünse de kayıpları da aynı oranda büyütebilir.",
    "📘 Temel analiz: Merkez bankası faiz kararları ve enflasyon verileri döviz kurlarını etkileyebilir.",
    "📘 Teknik analiz: Destek ve direnç seviyeleri, fiyatın durduğu veya zorlandığı bölgeleri gösterir.",
]


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            notifications INTEGER NOT NULL DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_starts (
            user_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            PRIMARY KEY (user_id, start_date)
        )
    """)
    conn.commit()
    conn.close()


def register_user(user_id: int):
    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (user_id, first_seen, last_seen, notifications)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(user_id) DO UPDATE SET last_seen = excluded.last_seen
    """, (user_id, now, now))
    c.execute("""
        INSERT OR IGNORE INTO daily_starts (user_id, start_date)
        VALUES (?, ?)
    """, (user_id, today))
    conn.commit()
    conn.close()


def get_notifications(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT notifications FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row[0]) if row else False


def set_notifications(user_id: int, enabled: bool):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE users SET notifications = ? WHERE user_id = ?",
        (1 if enabled else 0, user_id),
    )
    conn.commit()
    conn.close()


def daily_users_count():
    today = datetime.now(timezone.utc).date().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT COUNT(DISTINCT user_id) FROM daily_starts WHERE start_date = ?",
        (today,),
    )
    count = c.fetchone()[0]
    conn.close()
    return count, today


def get_opted_in_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE notifications = 1")
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]


def main_menu_keyboard(user_id: int):
    notif_on = get_notifications(user_id)
    notif_label = "🔔 Bildirimler: Açık" if notif_on else "🔔 Bildirimler: Kapalı"
    keyboard = [
        [
            InlineKeyboardButton("📊 Forex Insights", callback_data="menu:forex"),
            InlineKeyboardButton("₿ Crypto Insights", callback_data="menu:crypto"),
        ],
        [
            InlineKeyboardButton("🌍 Market Overview", callback_data="menu:market"),
        ],
        [
            InlineKeyboardButton("👥 Daily Users", callback_data="menu:daily"),
            InlineKeyboardButton("ℹ️ About", callback_data="menu:about"),
        ],
        [
            InlineKeyboardButton("📩 Contact", callback_data="menu:contact"),
            InlineKeyboardButton(notif_label, callback_data="menu:notif"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id)

    if os.path.exists(IMAGE_PATH):
        try:
            with open(IMAGE_PATH, "rb") as photo:
                await update.message.reply_photo(photo=photo, caption=CONTACT)
        except Exception:
            logger.exception("welcome.png gönderilemedi")
            await update.message.reply_text(CONTACT)
    else:
        await update.message.reply_text(CONTACT + "\n\n(Uyarı: assets/welcome.png bulunamadı.)")

    welcome = (
        f"Merhaba {user.first_name or 'kullanıcı'}! 👋\n\n"
        "Güncel Giriş Adresleri botuna hoş geldiniz. "
        "Forex, kripto ve genel piyasa kavramları hakkında Türkçe eğitim içerikleri bulabilirsiniz.\n\n"
        "Aşağıdaki menüden bir bölüm seçin."
    )
    await update.message.reply_text(
        welcome,
        reply_markup=main_menu_keyboard(user.id),
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    user_id = query.from_user.id

    if data == "menu:forex":
        await query.edit_message_text(FOREX_TEXT, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Geri", callback_data="menu:back")
        ]]))
    elif data == "menu:crypto":
        await query.edit_message_text(CRYPTO_TEXT, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Geri", callback_data="menu:back")
        ]]))
    elif data == "menu:market":
        await query.edit_message_text(MARKET_TEXT, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Geri", callback_data="menu:back")
        ]]))
    elif data == "menu:daily":
        count, today = daily_users_count()
        text = (
            f"👥 Daily Users Today (UTC): {count} — {today}\n\n"
            "Bu istatistik yalnızca toplu sayı gösterir. "
            "Kullanıcı adı, Telegram ID veya özel liste paylaşılmaz."
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Geri", callback_data="menu:back")
        ]]))
    elif data == "menu:about":
        await query.edit_message_text(ABOUT_TEXT, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Geri", callback_data="menu:back")
        ]]))
    elif data == "menu:contact":
        await query.edit_message_text(CONTACT, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Geri", callback_data="menu:back")
        ]]))
    elif data == "menu:notif":
        current = get_notifications(user_id)
        new_state = not current
        set_notifications(user_id, new_state)
        status = "açıldı" if new_state else "kapatıldı"
        text = (
            f"🔔 Bildirimler {status}.\n\n"
            "Bildirimler yalnızca siz açtıysanız gönderilir. "
            "Dilediğiniz zaman bu menüden açıp kapatabilirsiniz."
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Geri", callback_data="menu:back")
        ]]))
    elif data == "menu:back":
        await query.edit_message_text(
            MENU_TEXT,
            reply_markup=main_menu_keyboard(user_id),
        )
    else:
        await query.edit_message_text(
            "Bilinmeyen işlem.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Geri", callback_data="menu:back")
            ]]),
        )


async def send_scheduled_tips(context: ContextTypes.DEFAULT_TYPE):
    index = context.bot_data.get("tip_index", 0)
    tip = SCHEDULED_TIPS[index % len(SCHEDULED_TIPS)]
    context.bot_data["tip_index"] = index + 1

    user_ids = get_opted_in_users()
    logger.info("Zamanlanmış eğitim mesajı gönderilecek kullanıcı sayısı: %s", len(user_ids))

    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=tip)
        except Exception as exc:
            logger.warning("Zamanlanmış mesaj gönderilemedi user_id=%s: %s", user_id, exc)
        await asyncio.sleep(0.05)


async def post_init(application: Application):
    application.job_queue.run_repeating(
        send_scheduled_tips,
        interval=timedelta(minutes=20),
        first=10,
        name="educational_tips",
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Güncelleme işlenirken hata oluştu:", exc_info=context.error)


def main():
    init_db()
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_error_handler(error_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
