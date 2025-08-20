from telegram import Chat, Message


def _extract_forward_origin_chat(msg: Message):
    fo = getattr(msg, "forward_origin", None)
    if fo is not None:
        chat = getattr(fo, "chat", None) or getattr(fo, "from_chat", None)
        if chat is not None:
            return chat
    return getattr(msg, "forward_from_chat", None)



# ---- Linked channel cache helpers (added) ----
_GROUP_LINKED_ID_CACHE: dict[int, int | None] = {}

async def _get_linked_id(chat_id: int, bot) -> int | None:
    """Fetch linked_chat_id reliably using get_chat (cached)."""
    if chat_id in _GROUP_LINKED_ID_CACHE:
        return _GROUP_LINKED_ID_CACHE[chat_id]
    try:
        chat = await bot.get_chat(chat_id)
        linked_id = getattr(chat, "linked_chat_id", None)
        _GROUP_LINKED_ID_CACHE[chat_id] = linked_id
        return linked_id
    except Exception:
        _GROUP_LINKED_ID_CACHE[chat_id] = None
        return None
# ---- end helpers ----
async def is_linked_channel_autoforward(msg: Message, bot) -> bool:
    """
    TRUE faqat guruhning bog'langan kanalidan avtomatik forward bo'lgan postlar uchun.
    - msg.is_automatic_forward True
    - get_chat(chat_id).linked_chat_id mavjud
    - va (sender_chat.id == linked_id) yoki (forward_origin chat.id == linked_id)
    - origin yashirilgan bo‘lsa ham fallback True (is_automatic_forward bo‘lsa)
    """
    try:
        if not getattr(msg, "is_automatic_forward", False):
            return False
        linked_id = await _get_linked_id(msg.chat_id, bot)
        if not linked_id:
            return False
        sc = getattr(msg, "sender_chat", None)
        if sc and getattr(sc, "id", None) == linked_id:
            return True
        fwd_chat = _extract_forward_origin_chat(msg)
        if fwd_chat and getattr(fwd_chat, "id", None) == linked_id:
            return True
        # Fallback: origin yashirilgan bo‘lishi mumkin
        return True
    except Exception:
        return False
        linked_id = getattr(msg.chat, "linked_chat_id", None)
        if not linked_id:
            return False
        fwd_chat = _extract_forward_origin_chat(msg)
        if fwd_chat and getattr(fwd_chat, "id", None) == linked_id:
            return True
    except Exception:
        pass
    return False
from telegram import Update, BotCommand, BotCommandScopeAllPrivateChats, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ChatMemberHandler, ContextTypes, filters

def admin_add_link(bot_username: str) -> str:
    rights = [
        'delete_messages','restrict_members','invite_users',
        'pin_messages','manage_topics','manage_video_chats','manage_chat'
    ]
    rights_param = '+'.join(rights)
    return f"https://t.me/{bot_username}?startgroup&admin={rights_param}"

import threading
import os
import re
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from flask import Flask

# ----------- Small keep-alive web server -----------
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot ishlayapti!"

def run_web():
    app_flask.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))

def start_web():
    threading.Thread(target=run_web, daemon=True).start()

# ----------- Config -----------
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN") or "YOUR_TOKEN_HERE"

WHITELIST = {165553982, "Yunus1995"}
TUN_REJIMI = False
KANAL_USERNAME = None

MAJBUR_LIMIT = 0
FOYDALANUVCHI_HISOBI = defaultdict(int)
RUXSAT_USER_IDS = set()
BLOK_VAQTLARI = {}  # (chat_id, user_id) -> until_datetime (UTC)

# ✅ To'liq yozish ruxsatlari (guruh sozlamalari ruxsat bergan taqdirda)
FULL_PERMS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_invite_users=True,
)

# Blok uchun ruxsatlar (3 daqiqa): faqat yozish yopiladi, odam qo'shishga ruxsat qoldiriladi
BLOCK_PERMS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_invite_users=True,
)

# So'kinish lug'ati
UYATLI_SOZLAR = {"am", "ammisan", "ammislar", "ammislar?", "ammisizlar", "ammisizlar?", "amsan", "ammisan?", "amlar", "amlatta", "amyalaq", "amyalar", "amyaloq", "amxor", "am yaliman", "am yalayman", "am latta", "aminga",
"aminga ske", "aminga sikay", "buyingdi ami", "buyingdi omi", "buyingni ami", "buyindi omi", "buynami", "biyindi ami", "blya", "biyundiami", "blyat", "buynami", "buyingdi omi", "buyingni ami",
"buyundiomi", "dalbayob", "dalbayobmisan", "dalbayoblar", "dalbayobmisan?", "debil", "dolboyob", "durak", "fuck", "fakyou", "fuckyou", "foxisha", "foxishasan", "foxishamisan?", "foxishalar", "fohisha", "fohishasan", "fohishamisan?",
"fohishalar", "gandon", "gandonmisan", "gandonmisan?", "gandonlar", "haromi", "huy", "haromilar", "horomi", "horomilar", "idinnaxxuy", "idinaxxuy", "idin naxuy", "idin naxxuy", "isqirt", "isqirtsan", "isqirtlar", "jalap", "jalaplar",
"jalapsan", "jalapkot", "jalapkoz", "kot", "kotmislar", "kotmislar?", "kotmisizlar", "kutagim", "kotmisizlar?", "kotlar", "kotak", "kotmisan", "kotmisan?", "kotsan", "ko'tsan", "ko'tmisan", "ko't", "ko'tlar", "kotinga ske", "kotinga sikay", "kotingaske", "kotagim", "kotinga", "ko'tinga",
"kotingga", "kotvacha", "ko'tak", "lanati", "lanat", "lanatilar", "lanatisan", "mudak", "naxxuy", "og'zingaskay", "og'zinga skey", "ogzinga skey", "og'zinga skay", "ogzingaskay", "otti qotagi", "otni qotagi", "horomilar",
"huyimga", "huygami", "otti qo'tag'i", "ogzinga skay", "onagniomi", "onagni omi", "onangniami", "onagni ami", "pashol naxuy", "pasholnaxuy", "padarlanat", "padarlanatlar", "padarlanatsan", "pasholnaxxuy", "pidor",
"poshol naxxuy", "posholnaxxuy", "poxxuy", "poxuy", "qanjik", "qanjiq", "qanjiqsan", "qanjiqlar", "qonjiq", "qotaq", "qotaqlar", "qotaqsan", "qotaqmisan", "qotaqxor", "qo'taq", "qo'taqxo'r", "chochoq", "chochaq",
"qotagim", "qo'tag'im", "qotoqlar", "qo'toqlar", "qotag'im", "qotoglar", "qo'tog'lar", "qotagim", "skiy", "skay", "sikey", "sik", "skaman", "sikaman", "skasizmi", "sikasizmi", "sikay", "sikalak", "skishaman", "skishamiz",
"skishamizmi?", "sikishaman", "sikishamiz", "skey" "sikish", "sikishish", "skay", "soska", "suka", "sukalar", "tashak", "tashaklar", "tashaq", "tashaqlar", "toshoq", "toshoqlar", "toshok", "xuy", "xuramilar", "xuy",
"xuyna", "xaromi", "xoramilar", "xoromi", "xoromilar", "g'ar", "ам", "аммисан", "аммислар", "аммислар?", "аммисизлар", "аммисизлар?", "амсан", "аммисан?", "амлар", "амлатта", "амялақ", "амялар", "амялоқ", "амхор", "ам ялиман", "ам ялайман", "ам латта", "аминга",
"аминга ске", "аминга сикай", "буйингди ами", "буйингди оми", "буйингни ами", "буйинди оми", "буйнами", "бийинди ами", "бля", "биюндиами", "блят", "буйнами", "буйингди оми", "буйингни ами",
"буюндиоми", "далбаёб", "далбаёбмисан", "далбаёблар", "далбаёбмисан?", "дебил", "долбоёб", "дурак", "фуcк", "факёу", "фуcкёу", "фохиша", "фохишасан", "фохишамисан?", "фохишалар", "фоҳиша", "фоҳишасан", "фоҳишамисан?",
"фоҳишалар", "гандон", "гандонмисан", "гандонмисан?", "гандонлар", "ҳароми", "ҳуй", "ҳаромилар", "ҳороми", "ҳоромилар", "идиннаххуй", "идинаххуй", "идин нахуй", "идин наххуй", "исқирт", "исқиртсан", "исқиртлар", "жалап", "жалаплар",
"жалапсан", "жалапкот", "жалапкоз", "кот", "котмислар", "котмислар?", "котмисизлар", "кутагим", "котмисизлар?", "котлар", "котак", "котмисан", "котмисан?", "котсан", "кўтсан", "кўтмисан", "кўт", "кўтлар", "котинга ске", "котинга сикай", "котингаске", "котагим", "котинга", "кўтинга",
"котингга", "котвача", "кўтак", "ланати", "ланат", "ланатилар", "ланатисан", "мудак", "наххуй", "оғзингаскай", "оғзинга скей", "огзинга скей", "оғзинга скай", "огзингаскай", "отти қотаги", "отни қотаги", "ҳоромилар",
"ҳуйимга", "ҳуйгами", "отти қўтағи", "огзинга скай", "онагниоми", "онагни оми", "онангниами", "онагни ами", "пашол нахуй", "пашолнахуй", "падарланат", "падарланатлар", "падарланатсан", "пашолнаххуй", "пидор", "пошол наххуй",
"пошолнаххуй", "поххуй", "похуй", "қанжик", "қанжиқ", "қанжиқсан", "қанжиқлар", "қонжиқ", "қотақ", "қотақлар", "қотақсан", "қотақмисан", "қотақхор", "қўтақ", "қўтақхўр", "чочоқ", "чочақ",
"қотагим", "қўтағим", "қотоқлар", "қўтоқлар", "қотағим", "қотоглар", "қўтоғлар", "қотагим", "ский", "скай", "сикей", "сик", "скаман", "сикаман", "скасизми", "сикасизми", "сикай", "сикалак", "скишаман", "скишамиз",
"скишамизми?", "сикишаман", "сикишамиз", "скей" "сикиш", "сикишиш", "скай", "соска", "сука", "сукалар", "ташак", "ташаклар", "ташақ", "ташақлар", "тошоқ", "тошоқлар", "тошок", "хуй", "хурамилар", "хуй",
"хуйна", "хароми", "хорамилар", "хороми", "хоромилар", "ғар"}

# Game/inline reklama kalit so'zlar/domenlar
SUSPECT_KEYWORDS = {"open game", "play", "играть", "открыть игру", "game", "cattea", "gamee", "hamster", "notcoin", "tap to earn", "earn", "clicker"}
SUSPECT_DOMAINS = {"cattea", "gamee", "hamster", "notcoin", "tgme", "t.me/gamee", "textra.fun", "ton"}

import os
import json
import asyncio
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest, RetryAfter, TimedOut, NetworkError, TelegramError

# ----------- Helpers -----------

# ----------- DM Broadcast (Owner only) -----------
SUB_USERS_FILE = "subs_users.json"

def _load_ids(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

def _save_ids(path: str, data: set):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sorted(list(data)), f, ensure_ascii=False, indent=2)
    except Exception as e:
        try:
            log.warning(f"IDs saqlashda xatolik: {e}")
        except Exception:
            print(f"IDs saqlashda xatolik: {e}")

def add_chat_to_subs(chat):
    # faqat private foydalanuvchilar ro'yxati
    s = _load_ids(SUB_USERS_FILE)
    s.add(chat.id)
    _save_ids(SUB_USERS_FILE, s)
    return "user"

def remove_chat_from_subs(chat):
    s = _load_ids(SUB_USERS_FILE)
    if chat.id in s:
        s.remove(chat.id)
        _save_ids(SUB_USERS_FILE, s)
    return "user"

# OWNER_ID ni Render environment variables orqali berish mumkin:
# OWNER_ID=123456789  (yoki kodda to'g'ridan-to'g'ri almashtiring)
OWNER_IDS = {165553982}

def is_owner(update: Update) -> bool:
    u = update.effective_user
    return bool(u and u.id in OWNER_IDS)

async def is_admin(update: Update) -> bool:
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user
    if not chat:
        return False
    try:
        # Anonymous admin (message on behalf of the group itself)
        if msg and getattr(msg, "sender_chat", None):
            sc = msg.sender_chat
            if sc.id == chat.id:
                return True
            # Linked channel posting into a supergroup
            linked_id = getattr(chat, "linked_chat_id", None)
            if linked_id and sc.id == linked_id:
                return True
        # Regular user-based admin check
        if user:
            member = await update.get_bot().get_chat_member(chat.id, user.id)
            return member.status in ("administrator", "creator", "owner")
        return False
    except Exception as e:
        log.warning(f"is_admin tekshiruvda xatolik: {e}")
        return False

async def is_privileged_message(msg, bot) -> bool:
    """Adminlar, creatorlar yoki guruh/linked kanal nomidan yozilgan (sender_chat) xabarlar uchun True."""
    try:
        chat = msg.chat
        user = msg.from_user
        # Anonymous admin (group) yoki linked kanal
        if getattr(msg, "sender_chat", None):
            sc = msg.sender_chat
            if sc.id == chat.id:
                return True
            linked_id = getattr(chat, "linked_chat_id", None)
            if linked_id and sc.id == linked_id:
                return True
        # Odatdagi admin/creator
        if user:
            member = await bot.get_chat_member(chat.id, user.id)
            if member.status in ("administrator", "creator", "owner"):
                return True
    except Exception as e:
        log.warning(f"is_privileged_message xatolik: {e}")
    return False

async def kanal_tekshir(user_id: int, bot) -> bool:
    global KANAL_USERNAME
    if not KANAL_USERNAME:
        return True
    try:
        member = await bot.get_chat_member(KANAL_USERNAME, user_id)
        return member.status in ("member", "creator", "administrator")
    except Exception as e:
        log.warning(f"kanal_tekshir xatolik: {e}")
        return False

def matndan_sozlar_olish(matn: str):
    return re.findall(r"\b\w+\b", (matn or "").lower())

def add_to_group_kb(bot_username: str):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("➕ Добавить в группу", url=admin_add_link(bot_username))]]
    )

def has_suspicious_buttons(msg) -> bool:
    try:
        kb = msg.reply_markup.inline_keyboard if msg.reply_markup else []
        for row in kb:
            for btn in row:
                if getattr(btn, "callback_game", None) is not None:
                    return True
                u = getattr(btn, "url", "") or ""
                if u:
                    low = u.lower()
                    if any(dom in low for dom in SUSPECT_DOMAINS) or any(x in low for x in ("game", "play", "tgme")):
                        return True
                wa = getattr(btn, "web_app", None)
                if wa and getattr(wa, "url", None):
                    if any(dom in wa.url.lower() for dom in SUSPECT_DOMAINS):
                        return True
        return False
    except Exception:
        return False

# ----------- Commands -----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Auto-subscribe: /start bosgan foydalanuvchini DM ro'yxatga qo'shamiz
    try:
        if update.effective_chat.type == 'private':
            add_chat_to_subs(update.effective_chat)
    except Exception:
        pass
    kb = [[InlineKeyboardButton("➕ Добавить в группу", url=admin_add_link(context.bot.username))]]
    await update.effective_message.reply_text(
    "<b>ПРИВЕТ👋</b>"
"Я <b>удаляю</b> из групп любые рекламные посты, ссылки, сообщения о <b>входе/выходе</b> и рекламу от вспомогательных ботов.\n\n"
"Могу определить ваш <b>ID</b> профиля.\n\n"
"Сделаю обязательным добавление людей в группу и подписку на канал (иначе писать нельзя) ➕\n\n"
"Удаляю <b>18+</b> нецензурные слова и делаю многое другое 👨🏻‍✈\n\n"
"Справка по командам 👉 /help\n\n"
"Сам бот <b>НЕ отправляет</b> никаких рекламных объявлений или ссылок ⛔\n\n"
"Чтобы я работал, добавьте меня в группу и дайте <b>ПРАВА АДМИНА</b> 🙂\n\n"
"<b>Для связи или вопроси</b> 👉 @Devona0107",
    parse_mode="HTML",
    reply_markup=InlineKeyboardMarkup(kb))
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📌 <b>СПИСОК КОМАНД</b>\n\n"
"🔹 <b>/id</b> — Показать ваш ID.\n\n"
        "📘<b>ПОЛЕЗНЫЕ КОМАНДЫ</b>\n"
"🔹 <b>/night</b> — Ночной режим (все новые сообщения обычных пользователей будут автоматически удаляться).\n"
"🔹 <b>/nightoff</b> — Выключить ночной режим.\n"
"🔹 <b>/permit</b> — Выдать привилегию по reply.\n\n"
        "👥<b>ПРИНУДИТЕЛЬНОЕ ДОБАВЛЕНИЕ ЛЮДЕЙ В ГРУППЫ И КАНАЛЫ</b>\n"
"🔹 <b>/channel @username</b> — Включить обязательную подписку на указанный канал.\n"
"🔹 <b>/channeloff</b> — Отключить обязательную подписку.\n"
"🔹 <b>/forced [3–25]</b> — Включить обязательное добавление людей в группу.\n"
"🔹 <b>/forcedoff</b> — Отключить обязательное добавление.\n\n"
        "📈<b>Подсчёт людей, которые добавили</b>\n"
"🔹 <b>/top</b> — Топ участников по добавлениям.\n"
"🔹 <b>/cleangroup</b> — Обнулить счётчики всех пользователей.\n"
"🔹 <b>/count</b> — Сколько людей добавили вы.\n"
"🔹 <b>/replycount</b> — По reply: сколько добавил указанный пользователь.\n"
"🔹 <b>/cleanuser</b> — По reply: обнулить счётчик пользователя.\n")
    await update.effective_message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

async def id_berish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user = update.effective_user
    await update.effective_message.reply_text(f"🆔 {user.first_name}, ваш Telegram ID: {user.id}")

async def tun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TUN_REJIMI
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Только для администраторов.")
    TUN_REJIMI = True
    await update.effective_message.reply_text("🌙 Tun rejimi yoqildi. Oddiy foydalanuvchi xabarlari o‘chiriladi.")

async def tunoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TUN_REJIMI
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Только для администраторов.")
    TUN_REJIMI = False
    await update.effective_message.reply_text("🌞 Ночной режим выключен.")

async def ruxsat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Только для администраторов.")
    if not update.effective_message.reply_to_message:
        return await update.effective_message.reply_text("Iltimos, foydalanuvchi xabariga reply qiling.")
    uid = update.effective_message.reply_to_message.from_user.id
    RUXSAT_USER_IDS.add(uid)
    await update.effective_message.reply_text(f"✅ <code>{uid}</code> foydalanuvchiga ruxsat berildi.", parse_mode="HTML")

async def kanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Только для администраторов.")
    global KANAL_USERNAME
    if context.args:
        KANAL_USERNAME = context.args[0]
        await update.effective_message.reply_text(f"📢 Majburiy kanal: {KANAL_USERNAME}")
    else:
        await update.effective_message.reply_text("Namuna: /kanal @username")

async def kanaloff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Только для администраторов.")
    global KANAL_USERNAME
    KANAL_USERNAME = None
    await update.effective_message.reply_text("🚫 Majburiy kanal talabi o‘chirildi.")

def majbur_klaviatura():
    rows = [[3, 5, 7, 10, 12], [15, 18, 20, 25, 30]]
    keyboard = [[InlineKeyboardButton(str(n), callback_data=f"set_limit:{n}") for n in row] for row in rows]
    keyboard.append([InlineKeyboardButton("❌ BEKOR QILISH ❌", callback_data="set_limit:cancel")])
    return InlineKeyboardMarkup(keyboard)

async def majbur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Только для администраторов.")
    global MAJBUR_LIMIT
    if context.args:
        try:
            val = int(context.args[0])
            if not (3 <= val <= 25):
                raise ValueError
            MAJBUR_LIMIT = val
            await update.effective_message.reply_text(
                f"✅ Majburiy odam qo‘shish limiti: <b>{MAJBUR_LIMIT}</b>",
                parse_mode="HTML"
            )
        except ValueError:
            await update.effective_message.reply_text(
                "❌ Noto‘g‘ri qiymat. Ruxsat etilgan oraliq: <b>3–25</b>. Masalan: <code>/majbur 10</code>",
                parse_mode="HTML"
            )
    else:
        await update.effective_message.reply_text(
            "👥 Guruhda majburiy odam qo‘shishni nechta qilib belgilay? 👇\n"
            "Qo‘shish shart emas — /majburoff",
            reply_markup=majbur_klaviatura()
        )

async def on_set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.callback_query.answer("Faqat adminlar!", show_alert=True)
    q = update.callback_query
    await q.answer()
    data = q.data.split(":", 1)[1]
    global MAJBUR_LIMIT
    if data == "cancel":
        return await q.edit_message_text("❌ Bekor qilindi.")
    try:
        val = int(data)
        if not (3 <= val <= 25):
            raise ValueError
        MAJBUR_LIMIT = val
        await q.edit_message_text(f"✅ Majburiy limit: <b>{MAJBUR_LIMIT}</b>", parse_mode="HTML")
    except Exception:
        await q.edit_message_text("❌ Noto‘g‘ri qiymat.")

async def majburoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Только для администраторов.")
    global MAJBUR_LIMIT
    MAJBUR_LIMIT = 0
    await update.effective_message.reply_text("🚫 Majburiy odam qo‘shish o‘chirildi.")

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Только для администраторов.")
    if not FOYDALANUVCHI_HISOBI:
        return await update.effective_message.reply_text("Пока никто никого не добавил.")
    items = sorted(FOYDALANUVCHI_HISOBI.items(), key=lambda x: x[1], reverse=True)[:100]
    lines = ["🏆 <b>ТОП 100 участников по добавлениям</b> (TOP 100):"]
    for i, (uid, cnt) in enumerate(items, start=1):
        lines.append(f"{i}. <code>{uid}</code> — {cnt} ta")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")

async def cleangroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Только для администраторов.")
    FOYDALANUVCHI_HISOBI.clear()
    RUXSAT_USER_IDS.clear()
    await update.effective_message.reply_text("🗑 Счётчики и привилегии обнулены.")

async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cnt = FOYDALANUVCHI_HISOBI.get(uid, 0)
    if MAJBUR_LIMIT > 0:
        qoldi = max(MAJBUR_LIMIT - cnt, 0)
        await update.effective_message.reply_text(f"📊 Siz {cnt} ta odam qo‘shgansiz. Qolgan: {qoldi} ta.")
    else:
        await update.effective_message.reply_text(f"📊 Siz {cnt} ta odam qo‘shgansiz. (Majburiy qo‘shish faol emas)")

async def replycount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Только для администраторов.")
    msg = update.effective_message
    if not msg.reply_to_message:
        return await msg.reply_text("Iltimos, kimning hisobini ko‘rmoqchi bo‘lsangiz o‘sha xabarga reply qiling.")
    uid = msg.reply_to_message.from_user.id
    cnt = FOYDALANUVCHI_HISOBI.get(uid, 0)
    await msg.reply_text(f"👤 <code>{uid}</code> {cnt} ta odam qo‘shgan.", parse_mode="HTML")

async def cleanuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Только для администраторов.")
    msg = update.effective_message
    if not msg.reply_to_message:
        return await msg.reply_text("Iltimos, kimni 0 qilmoqchi bo‘lsangiz o‘sha foydalanuvchi xabariga reply qiling.")
    uid = msg.reply_to_message.from_user.id
    FOYDALANUVCHI_HISOBI[uid] = 0
    RUXSAT_USER_IDS.discard(uid)
    await msg.reply_text(f"🗑 <code>{uid}</code> foydalanuvchi hisobi 0 qilindi (imtiyoz o‘chirildi).", parse_mode="HTML")

async def kanal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if not KANAL_USERNAME:
        return await q.edit_message_text("⚠️ Kanal sozlanmagan.")
    try:
        member = await context.bot.get_chat_member(KANAL_USERNAME, user_id)
        if member.status in ("member", "administrator", "creator"):
            # ⬇️ To'liq ruxsat beramiz (guruh sozlamalari darajasida)
            try:
                await context.bot.restrict_chat_member(
                    chat_id=q.message.chat.id,
                    user_id=user_id,
                    permissions=FULL_PERMS,
                )
            except Exception:
                pass
            await q.edit_message_text("✅ A’zo bo‘lganingiz tasdiqlandi. Endi guruhda yozishingiz mumkin.")
        else:
            await q.edit_message_text("❌ Hali kanalga a’zo emassiz.")
    except Exception:
        await q.edit_message_text("⚠️ Tekshirishda xatolik. Kanal username noto‘g‘ri yoki bot kanalga a’zo emas.")

async def on_check_added(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id

    # faqat ogohlantirish olgan egasi bosa oladi
    data = q.data
    if ":" in data:
        try:
            owner_id = int(data.split(":", 1)[1])
        except ValueError:
            owner_id = None
        if owner_id and owner_id != uid:
            return await q.answer("Bu tugma siz uchun emas!", show_alert=True)

    cnt = FOYDALANUVCHI_HISOBI.get(uid, 0)

    # Talab bajarilgan holat: to'liq ruxsat
    if uid in RUXSAT_USER_IDS or (MAJBUR_LIMIT > 0 and cnt >= MAJBUR_LIMIT):
        try:
            await context.bot.restrict_chat_member(
                chat_id=q.message.chat.id,
                user_id=uid,
                permissions=FULL_PERMS,
            )
        except Exception:
            pass
        BLOK_VAQTLARI.pop((q.message.chat.id, uid), None)
        return await q.edit_message_text("✅ Talab bajarilgan! Endi guruhda yozishingiz mumkin.")

    # Yetarli emas holat: MODAL oynacha
    qoldi = max(MAJBUR_LIMIT - cnt, 0)
    return await q.answer(
        f"❗ Siz hozirgacha {cnt} ta foydalanuvchi qo‘shdingiz va yana {qoldi} ta foydalanuvchi qo‘shishingiz kerak",
        show_alert=True
    )
    # Xabarni o'zgartirmaymiz — tugmalar joyida qoladi
    return

async def on_grant_priv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat = q.message.chat if q.message else None
    user = q.from_user
    if not (chat and user):
        return await q.answer()
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ("administrator", "creator"):
            return await q.answer("Faqat adminlar imtiyoz bera oladi!", show_alert=True)
    except Exception:
        return await q.answer("Tekshirishda xatolik.", show_alert=True)
    await q.answer()
    try:
        target_id = int(q.data.split(":", 1)[1])
    except Exception:
        return await q.edit_message_text("❌ Noto‘g‘ri ma'lumot.")
    RUXSAT_USER_IDS.add(target_id)
    await q.edit_message_text(f"🎟 <code>{target_id}</code> foydalanuvchiga imtiyoz berildi. Endi u yozishi mumkin.", parse_mode="HTML")

# ----------- Filters -----------
async def reklama_va_soz_filtri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    # 🔒 Linked kanalning avtomatik forward postlari — teginmaymiz
    try:
        if await is_linked_channel_autoforward(msg, context.bot):
            return
    except Exception:
        pass
    if not msg or not msg.chat or not msg.from_user:
        return
    # Admin/creator/guruh nomidan xabarlar — teginmaymiz
    if await is_privileged_message(msg, context.bot):
        return
    # Oq ro'yxat
    if msg.from_user.id in WHITELIST or (msg.from_user.username and msg.from_user.username in WHITELIST):
        return
    # Tun rejimi
    if TUN_REJIMI:
        try:
            await msg.delete()
        except:
            pass
        return
    # Kanal a'zoligi
    if not await kanal_tekshir(msg.from_user.id, context.bot):
        try:
            await msg.delete()
        except:
            pass
        kb = [
            [InlineKeyboardButton("✅ Я подписался", callback_data="kanal_azo")],
            [InlineKeyboardButton("➕ Добавить в группу", url=admin_add_link(context.bot.username))]
        ]
        await context.bot.send_message(
    chat_id=msg.chat_id,
    text=f"⚠️ {msg.from_user.mention_html()}, вы не подписаны на канал {KANAL_USERNAME}!",
    reply_markup=InlineKeyboardMarkup(kb),
    parse_mode="HTML"
)
        return

    text = msg.text or msg.caption or ""
    entities = msg.entities or msg.caption_entities or []

    # Inline bot orqali kelgan xabar — ko'pincha game reklama
    if getattr(msg, "via_bot", None):
        try:
            await msg.delete()
        except:
            pass
        await context.bot.send_message(
    chat_id=msg.chat_id,
    text=f"⚠️ {msg.from_user.mention_html()}, скрытые ссылки запрещены!",
    reply_markup=add_to_group_kb(context.bot.username),
    parse_mode="HTML"
)
        return

    # Tugmalarda game/web-app/URL bo'lsa — blok
    if has_suspicious_buttons(msg):
        try:
            await msg.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=msg.chat_id,
            text="⚠️ O‘yin/veb-app tugmali reklama taqiqlangan!",
            reply_markup=add_to_group_kb(context.bot.username)
        )
        return

    # Matndan o‘yin reklamasini aniqlash
    low = text.lower()
    if any(k in low for k in SUSPECT_KEYWORDS):
        try:
            await msg.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=msg.chat_id,
            text="⚠️ O‘yin reklamalari taqiqlangan!",
            reply_markup=add_to_group_kb(context.bot.username)
        )
        return

    # Botlardan kelgan reklama/havola/game
    if getattr(msg.from_user, "is_bot", False):
        has_game = bool(getattr(msg, "game", None))
        has_url_entity = any(ent.type in ("text_link", "url", "mention") for ent in entities)
        has_url_text = any(x in low for x in ("t.me","telegram.me","http://","https://","www.","youtu.be","youtube.com"))
        if has_game or has_url_entity or has_url_text:
            try:
                await msg.delete()
            except:
                pass
            await context.bot.send_message(
    chat_id=msg.chat_id,
    text=f"⚠️ {msg.from_user.mention_html()}, reklama/ssilka yuborish taqiqlangan!",
    reply_markup=add_to_group_kb(context.bot.username),
    parse_mode="HTML"
)
            return

    # Yashirin yoki aniq ssilkalar
    for ent in entities:
        if ent.type in ("text_link", "url", "mention"):
            url = getattr(ent, "url", "") or ""
            if url and ("t.me" in url or "telegram.me" in url or "http://" in url or "https://" in url):
                try:
                    await msg.delete()
                except:
                    pass
                await context.bot.send_message(
    chat_id=msg.chat_id,
    text=f"⚠️ {msg.from_user.mention_html()}, скрытые ссылки запрещены!",
    reply_markup=add_to_group_kb(context.bot.username),
    parse_mode="HTML"
)
                return

    if any(x in low for x in ("t.me","telegram.me","@","www.","https://youtu.be","http://","https://")):
        try:
            await msg.delete()
        except:
            pass
        await context.bot.send_message(
    chat_id=msg.chat_id,
    text=f"⚠️ {msg.from_user.mention_html()}, reklama/ssilka yuborish taqiqlangan!",
    reply_markup=add_to_group_kb(context.bot.username),
    parse_mode="HTML"
)
        return

    # So'kinish
    sozlar = matndan_sozlar_olish(text)
    if any(s in UYATLI_SOZLAR for s in sozlar):
        try:
            await msg.delete()
        except:
            pass
        await context.bot.send_message(
    chat_id=msg.chat_id,
    text=f"⚠️ {msg.from_user.mention_html()}, нецензурная лексика запрещена!",
    reply_markup=add_to_group_kb(context.bot.username),
    parse_mode="HTML"
)
        return

# Yangi a'zolarni qo'shganlarni hisoblash hamda kirdi/chiqdi xabarlarni o'chirish
async def on_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    adder = msg.from_user
    members = msg.new_chat_members or []
    if not adder:
        return
    for m in members:
        if adder.id != m.id:
            FOYDALANUVCHI_HISOBI[adder.id] += 1
    try:
        await msg.delete()
    except:
        pass

# Majburiy qo'shish filtri — yetmaganlarda 5 daqiqaga blok ham qo'yiladi
async def majbur_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if MAJBUR_LIMIT <= 0:
        return
    msg = update.effective_message
    # 🔒 Linked kanalning avtomatik forward postlari — teginmaymiz
    try:
        if await is_linked_channel_autoforward(msg, context.bot):
            return
    except Exception:
        pass
    if not msg or not msg.from_user:
        return
    if await is_privileged_message(msg, context.bot):
        return

    uid = msg.from_user.id

    # Agar foydalanuvchi hanuz blokda bo'lsa — xabarini o'chirib, hech narsa yubormaymiz
    now = datetime.now(timezone.utc)
    key = (msg.chat_id, uid)
    until_old = BLOK_VAQTLARI.get(key)
    if until_old and now < until_old:
        try:
            await msg.delete()
        except:
            pass
        return
    if uid in RUXSAT_USER_IDS:
        return

    cnt = FOYDALANUVCHI_HISOBI.get(uid, 0)
    if cnt >= MAJBUR_LIMIT:
        return

    # Xabarni o'chiramiz
    try:
        await msg.delete()
    except:
        return

    # 5 daqiqaga blok (hozir 3 daqiqa)
    until = datetime.now(timezone.utc) + timedelta(minutes=3)
    BLOK_VAQTLARI[(msg.chat_id, uid)] = until
    try:
        await context.bot.restrict_chat_member(
            chat_id=msg.chat_id,
            user_id=uid,
            permissions=BLOCK_PERMS,
            until_date=until
        )
    except Exception as e:
        log.warning(f"Restrict failed: {e}")

    qoldi = max(MAJBUR_LIMIT - cnt, 0)
    until_str = until.strftime('%H:%M')
    kb = [
        [InlineKeyboardButton("✅ Odam qo‘shdim", callback_data=f"check_added:{uid}")],
        [InlineKeyboardButton("🎟 Выдать привилегию", callback_data=f"grant:{uid}")],
        [InlineKeyboardButton("➕ Добавить в группу", url=admin_add_link(context.bot.username))],
        [InlineKeyboardButton("⏳ 3 daqiqaga bloklandi", callback_data="noop")]
    ]
    await context.bot.send_message(
        chat_id=msg.chat_id,
        text=f"⚠️ Для публикации в группе нужно добавить {MAJBUR_LIMIT} человека! Осталось: {qoldi}.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ----------- Setup -----------
async def set_commands(app):
    await app.bot.set_my_commands(
        commands=[
            BotCommand("start", "О боте"),
            BotCommand("help", "Справка по командам"),
            BotCommand("id", "Показать ваш ID"),
            BotCommand("count", "Сколько людей вы добавили"),
            BotCommand("top", "ТОП 100 участников"),
            BotCommand("replycount", "(reply) сколько добавил пользователь"),
            BotCommand("forced", "Установить лимит обязательных приглашений (3–25)"),
            BotCommand("forcedoff", "Отключить обязательные приглашения"),
            BotCommand("cleangroup", "Обнулить все счётчики"),
            BotCommand("cleanuser", "(reply) обнулить счётчик пользователя"),
            BotCommand("permit", "(reply) выдать привилегию"),
            BotCommand("channel", "Настроить обязательный канал"),
            BotCommand("channeloff", "Отключить обязательный канал"),
            BotCommand("night", "Включить ночной режим"),
            BotCommand("nightoff", "Выключить ночной режим"),
],
        scope=BotCommandScopeAllPrivateChats()
    )

def main():
    start_web()
    app = ApplicationBuilder().token(TOKEN).build()
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("id", id_berish))
    app.add_handler(CommandHandler("tun", tun))
    app.add_handler(CommandHandler("night", tun))
    app.add_handler(CommandHandler("tunoff", tunoff))
    app.add_handler(CommandHandler("nightoff", tunoff))
    app.add_handler(CommandHandler("ruxsat", ruxsat))
    app.add_handler(CommandHandler("permit", ruxsat))
    app.add_handler(CommandHandler("kanal", kanal))
    app.add_handler(CommandHandler("channel", kanal))
    app.add_handler(CommandHandler("kanaloff", kanaloff))
    app.add_handler(CommandHandler("channeloff", kanaloff))
    app.add_handler(CommandHandler("majbur", majbur))
    app.add_handler(CommandHandler("forced", majbur))
    app.add_handler(CommandHandler("majburoff", majburoff))
    app.add_handler(CommandHandler("forcedoff", majburoff))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("cleangroup", cleangroup))
    app.add_handler(CommandHandler("count", count_cmd))
    app.add_handler(CommandHandler("replycount", replycount))
    app.add_handler(CommandHandler("cleanuser", cleanuser))

    # Callbacks
    app.add_handler(CallbackQueryHandler(on_set_limit, pattern=r"^set_limit:"))
    app.add_handler(CallbackQueryHandler(kanal_callback, pattern=r"^kanal_azo$"))
    app.add_handler(CallbackQueryHandler(on_check_added, pattern=r"^check_added(?::\d+)?$"))
    app.add_handler(CallbackQueryHandler(on_grant_priv, pattern=r"^grant:"))
    app.add_handler(CallbackQueryHandler(lambda u,c: u.callback_query.answer(""), pattern=r"^noop$"))

    # Events & Filters
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_members))
    media_filters = (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.ANIMATION | filters.VOICE | filters.VIDEO_NOTE | filters.GAME)
    app.add_handler(MessageHandler(media_filters & (~filters.COMMAND), majbur_filter), group=-1)
    app.add_handler(MessageHandler(media_filters & (~filters.COMMAND), reklama_va_soz_filtri))

    app.post_init = set_commands

    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("broadcastpost", broadcastpost))
    app.run_polling(allowed_updates=Update.ALL_TYPES)
async def on_my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        st = update.my_chat_member.new_chat_member.status
    except Exception:
        return
    if st in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED):
        me = await context.bot.get_me()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(
            '🔐 Botni admin qilish', url=admin_add_link(me.username)
        )]])
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    '⚠️ Bot hozircha *admin emas*.\n'
                    "Iltimos, pastdagi tugma orqali admin qiling, shunda barcha funksiyalar to'liq ishlaydi."
                ),
                reply_markup=kb,
                parse_mode='Markdown'
            )
        except Exception:
            pass



async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(OWNER & DM) Matnni barcha DM obunachilarga yuborish."""
    if update.effective_chat.type != "private":
        return await update.effective_message.reply_text("⛔ Bu buyruq faqat DM (shaxsiy chat)da ishlaydi.")
    if not is_owner(update):
        return await update.effective_message.reply_text("⛔ Bu buyruq faqat bot egasiga ruxsat etilgan.")
    text = " ".join(context.args).strip()
    if not text and update.effective_message.reply_to_message:
        text = update.effective_message.reply_to_message.text_html or update.effective_message.reply_to_message.caption_html
    if not text:
        return await update.effective_message.reply_text("Foydalanish: /broadcast Yangilanish matni")
    users = _load_ids(SUB_USERS_FILE)
    total = len(users); ok = 0; fail = 0
    await update.effective_message.reply_text(f"📣 DM jo‘natish boshlandi. Jami foydalanuvchilar: {total}")
    for cid in list(users):
        try:
            await context.bot.send_message(cid, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            ok += 1
            await asyncio.sleep(0.05)
        except (Forbidden, BadRequest):
            users.discard(cid); fail += 1
        except RetryAfter as e:
            await asyncio.sleep(int(getattr(e, "retry_after", 1)) + 1)
        except (TimedOut, NetworkError, TelegramError):
            fail += 1
    _save_ids(SUB_USERS_FILE, users)
    await update.effective_message.reply_text(f"✅ Yuborildi: {ok} ta, ❌ xatolik: {fail} ta.")

async def broadcastpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(OWNER & DM) Reply qilingan postni barcha DM obunachilarga yuborish."""
    if update.effective_chat.type != "private":
        return await update.effective_message.reply_text("⛔ Bu buyruq faqat DM (shaxsiy chat)da ishlaydi.")
    if not is_owner(update):
        return await update.effective_message.reply_text("⛔ Bu buyruq faqat bot egasiga ruxsat etilgan.")
    msg = update.effective_message.reply_to_message
    if not msg:
        return await update.effective_message.reply_text("Foydalanish: /broadcastpost — yubormoqchi bo‘lgan xabarga reply qiling.")
    users = _load_ids(SUB_USERS_FILE)
    total = len(users); ok = 0; fail = 0
    await update.effective_message.reply_text(f"📣 DM post tarqatish boshlandi. Jami foydalanuvchilar: {total}")
    for cid in list(users):
        try:
            await context.bot.copy_message(chat_id=cid, from_chat_id=msg.chat_id, message_id=msg.message_id)
            ok += 1
            await asyncio.sleep(0.05)
        except (Forbidden, BadRequest):
            users.discard(cid); fail += 1
        except RetryAfter as e:
            await asyncio.sleep(int(getattr(e, "retry_after", 1)) + 1)
        except (TimedOut, NetworkError, TelegramError):
            fail += 1
    _save_ids(SUB_USERS_FILE, users)
    await update.effective_message.reply_text(f"✅ Yuborildi: {ok} ta, ❌ xatolik: {fail} ta.")

if __name__ == "__main__":
    main()
