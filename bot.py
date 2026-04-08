#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Moliya Bot - Shaxsiy moliyaviy yordamchi
"""

import logging
import sqlite3
import os
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ── SOZLAMALAR ──────────────────────────────────────────────────────────────
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DB_PATH = "moliya.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── CONVERSATION STATES ──────────────────────────────────────────────────────
(
    MAIN, 
    ADD_EXPENSE_AMOUNT, ADD_EXPENSE_NOTE,
    ADD_INCOME_AMOUNT, ADD_INCOME_NOTE,
    ADD_DEBT_NAME, ADD_DEBT_AMOUNT, ADD_DEBT_NOTE,
    ADD_SAVING_NAME, ADD_SAVING_GOAL,
    ADD_TO_SAVING_AMOUNT,
    PAY_DEBT_AMOUNT,
) = range(12)

# ── KATEGORIYALAR ────────────────────────────────────────────────────────────
EXP_CATS = {
    "food": "🛒 Oziq-ovqat",
    "transport": "🚗 Transport",
    "utility": "💡 Kommunal",
    "clothing": "👕 Kiyim",
    "health": "💊 Sog'liq",
    "edu": "📚 Ta'lim",
    "fun": "🎮 Ko'ngil ochar",
    "cafe": "☕ Kafe",
    "other": "📦 Boshqa",
}
INC_CATS = {
    "salary": "💼 Maosh",
    "freelance": "💻 Freelance",
    "business": "🏢 Biznes",
    "gift": "🎁 Sovg'a",
    "invest": "📈 Invest",
    "other_i": "✨ Boshqa",
}

# ── VALYUTA ──────────────────────────────────────────────────────────────────
def W(n):
    return f"₩{abs(int(n or 0)):,}"

def today():
    return date.today().isoformat()

def fdate(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d.%m.%Y")
    except:
        return d

# ── DATABASE ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            note TEXT,
            date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            paid REAL DEFAULT 0,
            note TEXT,
            date TEXT NOT NULL,
            due_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS savings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            goal REAL NOT NULL,
            current REAL DEFAULT 0,
            icon TEXT DEFAULT '🎯',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS user_state (
            user_id INTEGER PRIMARY KEY,
            state_data TEXT
        );
    """)
    conn.commit()
    conn.close()

# ── KEYBOARD HELPERS ─────────────────────────────────────────────────────────
def main_menu_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💸 Chiqim", callback_data="menu_expense"),
            InlineKeyboardButton("💰 Kirim", callback_data="menu_income"),
        ],
        [
            InlineKeyboardButton("🤝 Qarzlar", callback_data="menu_debts"),
            InlineKeyboardButton("🏦 Jamg'arma", callback_data="menu_savings"),
        ],
        [
            InlineKeyboardButton("📊 Holat", callback_data="menu_status"),
        ],
    ])

def back_kb(back_to="main"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Orqaga", callback_data=f"back_{back_to}")]
    ])

def cat_kb(cats: dict, prefix: str):
    rows = []
    items = list(cats.items())
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(v, callback_data=f"{prefix}_{k}") for k, v in items[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

# ── MAIN MENU ─────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"╔══════════════════════╗\n"
        f"║   💳 MOLIYA BOT      ║\n"
        f"╚══════════════════════╝\n\n"
        f"Salom, <b>{user.first_name}</b>! 👋\n\n"
        f"Bu bot sizning shaxsiy moliyangizni boshqarishga yordam beradi.\n\n"
        f"Quyidan kerakli bo'limni tanlang:"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu_kb())
    return MAIN

async def show_main_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text=None):
    q = update.callback_query
    if q:
        await q.answer()
    msg = text or "Kerakli bo'limni tanlang:"
    if q:
        await q.edit_message_text(msg, parse_mode="HTML", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=main_menu_kb())
    return MAIN

# ── STATUS ────────────────────────────────────────────────────────────────────
async def show_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    conn = get_db()
    c = conn.cursor()

    now = datetime.now()
    month_start = f"{now.year}-{now.month:02d}-01"

    # Bu oy
    c.execute("SELECT type, SUM(amount) FROM transactions WHERE user_id=? AND date>=? GROUP BY type", (uid, month_start))
    totals = {r[0]: r[1] for r in c.fetchall()}
    m_inc = totals.get("kirim", 0)
    m_exp = totals.get("chiqim", 0)

    # Jami
    c.execute("SELECT type, SUM(amount) FROM transactions WHERE user_id=? GROUP BY type", (uid,))
    all_totals = {r[0]: r[1] for r in c.fetchall()}
    a_inc = all_totals.get("kirim", 0)
    a_exp = all_totals.get("chiqim", 0)

    # Jamgarma
    c.execute("SELECT SUM(current), SUM(goal) FROM savings WHERE user_id=?", (uid,))
    sv_row = c.fetchone()
    sv_cur = sv_row[0] or 0
    sv_goal = sv_row[1] or 0

    # Qarzlar
    c.execute("SELECT type, SUM(amount-paid) FROM debts WHERE user_id=? AND paid<amount GROUP BY type", (uid,))
    debt_totals = {r[0]: r[1] for r in c.fetchall()}
    d_lent = debt_totals.get("berilgan", 0)
    d_borrowed = debt_totals.get("olingan", 0)

    # Top kategoriya bu oy
    c.execute("""
        SELECT category, SUM(amount) as s FROM transactions 
        WHERE user_id=? AND type='chiqim' AND date>=? 
        GROUP BY category ORDER BY s DESC LIMIT 1
    """, (uid, month_start))
    top_row = c.fetchone()
    conn.close()

    bal = a_inc - a_exp
    m_bal = m_inc - m_exp
    save_pct = int((m_inc - m_exp) / m_inc * 100) if m_inc > 0 else 0

    # Progress bar
    def pbar(pct, length=10):
        filled = int(pct / 100 * length)
        return "█" * filled + "░" * (length - filled)

    sv_pct = int(sv_cur / sv_goal * 100) if sv_goal > 0 else 0

    top_cat_text = ""
    if top_row:
        cat_name = EXP_CATS.get(top_row[0], top_row[0])
        top_cat_pct = int(top_row[1] / m_exp * 100) if m_exp > 0 else 0
        top_cat_text = f"\n⚠️ <b>Ko'p sarflagan:</b> {cat_name} ({top_cat_pct}%)"

    text = (
        f"📊 <b>MOLIYAVIY HOLAT</b>\n"
        f"{'─' * 24}\n\n"
        f"<b>💳 Umumiy balans</b>\n"
        f"{'▲' if bal >= 0 else '▼'} {W(bal)}\n\n"
        f"<b>📅 Bu oy ({now.strftime('%B %Y')})</b>\n"
        f"  ✅ Kirim:  <b>{W(m_inc)}</b>\n"
        f"  ❌ Chiqim: <b>{W(m_exp)}</b>\n"
        f"  💰 Balans: <b>{W(m_bal)}</b>\n"
        f"  💹 Tejash: <b>{save_pct}%</b>"
    )
    if top_cat_text:
        text += top_cat_text
    text += (
        f"\n\n<b>🏦 Jamg'arma</b>\n"
        f"  {W(sv_cur)} / {W(sv_goal)}\n"
        f"  [{pbar(sv_pct)}] {sv_pct}%\n\n"
        f"<b>🤝 Qarzlar</b>\n"
        f"  🔴 Men berdim: <b>{W(d_lent)}</b>\n"
        f"  🟢 Men oldim: <b>{W(d_borrowed)}</b>"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 Statistika", callback_data="status_stats"),
            InlineKeyboardButton("🔄 Yangilash", callback_data="menu_status"),
        ],
        [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="back_main")]
    ])
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    return MAIN

# ── EXPENSE ───────────────────────────────────────────────────────────────────
async def menu_expense(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    conn = get_db()
    c = conn.cursor()

    # So'nggi 5 ta chiqim
    c.execute("""
        SELECT category, amount, note, date FROM transactions 
        WHERE user_id=? AND type='chiqim' 
        ORDER BY id DESC LIMIT 5
    """, (uid,))
    rows = c.fetchall()
    conn.close()

    hist = ""
    if rows:
        hist = "\n<b>So'nggi chiqimlar:</b>\n"
        for r in rows:
            cat = EXP_CATS.get(r[0], r[0])
            note = f" • {r[2]}" if r[2] else ""
            hist += f"  {cat} <b>{W(r[1])}</b>{note} <i>{fdate(r[3])}</i>\n"

    text = f"💸 <b>CHIQIM QO'SHISH</b>\n{'─'*22}\n\nKategoriyani tanlang:{hist}"

    kb = cat_kb(EXP_CATS, "exp_cat")
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    return MAIN

async def exp_cat_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cat = q.data.replace("exp_cat_", "")
    ctx.user_data["exp_cat"] = cat
    cat_name = EXP_CATS.get(cat, cat)
    await q.edit_message_text(
        f"💸 <b>CHIQIM — {cat_name}</b>\n{'─'*22}\n\nSummani kiriting (₩):\n<i>Masalan: 50000</i>",
        parse_mode="HTML",
        reply_markup=back_kb("expense")
    )
    return ADD_EXPENSE_AMOUNT

async def exp_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(",", "").replace(" ", ""))
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ To'g'ri summa kiriting!\nMasalan: <b>50000</b>", parse_mode="HTML")
        return ADD_EXPENSE_AMOUNT
    ctx.user_data["exp_amount"] = amount
    cat_name = EXP_CATS.get(ctx.user_data.get("exp_cat", ""), "")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➡️ Izohsiz saqlash", callback_data="exp_no_note")]
    ])
    await update.message.reply_text(
        f"💸 <b>{W(amount)}</b> — {cat_name}\n\nIzoh qo'shing yoki o'tkazib yuboring:",
        parse_mode="HTML",
        reply_markup=kb
    )
    return ADD_EXPENSE_NOTE

async def exp_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    await save_expense(update, ctx, note)
    return MAIN

async def exp_no_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await save_expense(update, ctx, None)
    return MAIN

async def save_expense(update: Update, ctx: ContextTypes.DEFAULT_TYPE, note):
    uid = update.effective_user.id
    amount = ctx.user_data.get("exp_amount", 0)
    cat = ctx.user_data.get("exp_cat", "other")
    cat_name = EXP_CATS.get(cat, cat)
    conn = get_db()
    conn.execute(
        "INSERT INTO transactions (user_id, type, amount, category, note, date) VALUES (?,?,?,?,?,?)",
        (uid, "chiqim", amount, cat, note, today())
    )
    conn.commit()
    conn.close()
    text = (
        f"✅ <b>Chiqim saqlandi!</b>\n{'─'*20}\n\n"
        f"  {cat_name}\n"
        f"  💸 {W(amount)}\n"
        f"  📅 {fdate(today())}\n"
        + (f"  📝 {note}\n" if note else "")
    )
    q = update.callback_query
    if q:
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu_kb())

# ── INCOME ────────────────────────────────────────────────────────────────────
async def menu_income(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT category, amount, note, date FROM transactions 
        WHERE user_id=? AND type='kirim' 
        ORDER BY id DESC LIMIT 3
    """, (uid,))
    rows = c.fetchall()
    conn.close()
    hist = ""
    if rows:
        hist = "\n<b>So'nggi kirimlar:</b>\n"
        for r in rows:
            cat = INC_CATS.get(r[0], r[0])
            hist += f"  {cat} <b>{W(r[1])}</b> <i>{fdate(r[3])}</i>\n"
    await q.edit_message_text(
        f"💰 <b>KIRIM QO'SHISH</b>\n{'─'*22}\n\nKategoriyani tanlang:{hist}",
        parse_mode="HTML",
        reply_markup=cat_kb(INC_CATS, "inc_cat")
    )
    return MAIN

async def inc_cat_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cat = q.data.replace("inc_cat_", "")
    ctx.user_data["inc_cat"] = cat
    cat_name = INC_CATS.get(cat, cat)
    await q.edit_message_text(
        f"💰 <b>KIRIM — {cat_name}</b>\n{'─'*22}\n\nSummani kiriting (₩):",
        parse_mode="HTML",
        reply_markup=back_kb("income")
    )
    return ADD_INCOME_AMOUNT

async def inc_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(",", "").replace(" ", ""))
        if amount <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ To'g'ri summa kiriting!")
        return ADD_INCOME_AMOUNT
    ctx.user_data["inc_amount"] = amount
    cat_name = INC_CATS.get(ctx.user_data.get("inc_cat", ""), "")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("➡️ Izohsiz saqlash", callback_data="inc_no_note")]])
    await update.message.reply_text(
        f"💰 <b>{W(amount)}</b> — {cat_name}\n\nIzoh qo'shing:",
        parse_mode="HTML", reply_markup=kb
    )
    return ADD_INCOME_NOTE

async def inc_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    await save_income(update, ctx, note)
    return MAIN

async def inc_no_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await save_income(update, ctx, None)
    return MAIN

async def save_income(update: Update, ctx: ContextTypes.DEFAULT_TYPE, note):
    uid = update.effective_user.id
    amount = ctx.user_data.get("inc_amount", 0)
    cat = ctx.user_data.get("inc_cat", "other_i")
    cat_name = INC_CATS.get(cat, cat)
    conn = get_db()
    conn.execute(
        "INSERT INTO transactions (user_id, type, amount, category, note, date) VALUES (?,?,?,?,?,?)",
        (uid, "kirim", amount, cat, note, today())
    )
    conn.commit()
    conn.close()
    text = (
        f"✅ <b>Kirim saqlandi!</b>\n{'─'*20}\n\n"
        f"  {cat_name}\n"
        f"  💰 {W(amount)}\n"
        f"  📅 {fdate(today())}\n"
        + (f"  📝 {note}\n" if note else "")
    )
    q = update.callback_query
    if q:
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu_kb())

# ── DEBTS ─────────────────────────────────────────────────────────────────────
async def menu_debts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, type, name, amount, paid, note, date FROM debts WHERE user_id=? AND paid<amount ORDER BY id DESC", (uid,))
    rows = c.fetchall()
    conn.close()

    lent_total = sum(r[3]-r[4] for r in rows if r[1]=="berilgan")
    borrow_total = sum(r[3]-r[4] for r in rows if r[1]=="olingan")

    text = (
        f"🤝 <b>QARZLAR</b>\n{'─'*22}\n\n"
        f"🔴 Men berdim (qoldi): <b>{W(lent_total)}</b>\n"
        f"🟢 Men oldim (qoldi): <b>{W(borrow_total)}</b>\n\n"
    )
    if rows:
        text += "<b>Aktiv qarzlar:</b>\n"
        for r in rows:
            icon = "🔴" if r[1]=="berilgan" else "🟢"
            remaining = r[3] - r[4]
            pct = int(r[4]/r[3]*100)
            text += f"{icon} <b>{r[2]}</b> — {W(remaining)} qoldi ({pct}% to'landi)\n"
    else:
        text += "Hozir aktiv qarz yo'q ✨"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Berdim", callback_data="debt_add_berilgan"),
            InlineKeyboardButton("➕ Oldim", callback_data="debt_add_olingan"),
        ],
        [InlineKeyboardButton("💳 To'lov kiritish", callback_data="debt_pay_list")],
        [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="back_main")],
    ])
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    return MAIN

async def debt_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    dtype = q.data.replace("debt_add_", "")
    ctx.user_data["debt_type"] = dtype
    label = "berdim" if dtype == "berilgan" else "oldim"
    await q.edit_message_text(
        f"🤝 <b>QARZ — Men {label}</b>\n{'─'*22}\n\nKimga/Kimdan? (ism kiriting):",
        parse_mode="HTML",
        reply_markup=back_kb("debts")
    )
    return ADD_DEBT_NAME

async def debt_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["debt_name"] = update.message.text.strip()
    dtype = ctx.user_data.get("debt_type", "berilgan")
    label = "berdim" if dtype == "berilgan" else "oldim"
    await update.message.reply_text(
        f"🤝 Men {label}: <b>{ctx.user_data['debt_name']}</b>\n\nSummani kiriting (₩):",
        parse_mode="HTML"
    )
    return ADD_DEBT_AMOUNT

async def debt_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(",", "").replace(" ", ""))
        if amount <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ To'g'ri summa kiriting!")
        return ADD_DEBT_AMOUNT
    ctx.user_data["debt_amount"] = amount
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("➡️ Izohsiz saqlash", callback_data="debt_no_note")]])
    await update.message.reply_text(
        f"💰 {W(amount)}\n\nIzoh qo'shing yoki o'tkazib yuboring:",
        parse_mode="HTML", reply_markup=kb
    )
    return ADD_DEBT_NOTE

async def debt_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    await save_debt(update, ctx, note)
    return MAIN

async def debt_no_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await save_debt(update, ctx, None)
    return MAIN

async def save_debt(update, ctx, note):
    uid = update.effective_user.id
    dtype = ctx.user_data.get("debt_type", "berilgan")
    name = ctx.user_data.get("debt_name", "")
    amount = ctx.user_data.get("debt_amount", 0)
    label = "berdim" if dtype == "berilgan" else "oldim"
    conn = get_db()
    conn.execute(
        "INSERT INTO debts (user_id, type, name, amount, paid, note, date) VALUES (?,?,?,?,?,?,?)",
        (uid, dtype, name, amount, 0, note, today())
    )
    conn.commit()
    conn.close()
    icon = "🔴" if dtype == "berilgan" else "🟢"
    text = (
        f"✅ <b>Qarz saqlandi!</b>\n{'─'*20}\n\n"
        f"  {icon} Men {label}: <b>{name}</b>\n"
        f"  💰 {W(amount)}\n"
        f"  📅 {fdate(today())}\n"
        + (f"  📝 {note}\n" if note else "")
    )
    q = update.callback_query
    if q:
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu_kb())

async def debt_pay_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, type, name, amount, paid FROM debts WHERE user_id=? AND paid<amount ORDER BY id DESC", (uid,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await q.edit_message_text(
            "✨ Aktiv qarzlar yo'q!",
            reply_markup=back_kb("debts")
        )
        return MAIN
    buttons = []
    for r in rows:
        icon = "🔴" if r[1]=="berilgan" else "🟢"
        remaining = r[2] - r[3]
        buttons.append([InlineKeyboardButton(
            f"{icon} {r[2]} — {W(remaining)} qoldi",
            callback_data=f"pay_debt_{r[0]}"
        )])
    buttons.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_debts")])
    await q.edit_message_text(
        "💳 <b>Qaysi qarzga to'lov kiritasiz?</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return MAIN

async def pay_debt_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    debt_id = int(q.data.replace("pay_debt_", ""))
    ctx.user_data["pay_debt_id"] = debt_id
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, amount, paid FROM debts WHERE id=?", (debt_id,))
    r = c.fetchone()
    conn.close()
    remaining = r[1] - r[2]
    await q.edit_message_text(
        f"💳 <b>{r[0]}</b> uchun to'lov\n\nQoldi: <b>{W(remaining)}</b>\n\nTo'lov summasi (₩):",
        parse_mode="HTML",
        reply_markup=back_kb("debts")
    )
    return PAY_DEBT_AMOUNT

async def pay_debt_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(",", "").replace(" ", ""))
        if amount <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ To'g'ri summa kiriting!")
        return PAY_DEBT_AMOUNT
    debt_id = ctx.user_data.get("pay_debt_id")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, amount, paid FROM debts WHERE id=?", (debt_id,))
    r = c.fetchone()
    new_paid = min(r[2] + amount, r[1])
    conn.execute("UPDATE debts SET paid=? WHERE id=?", (new_paid, debt_id))
    conn.commit()
    conn.close()
    done = new_paid >= r[1]
    text = (
        f"✅ <b>To'lov saqlandi!</b>\n{'─'*20}\n\n"
        f"  👤 {r[0]}\n"
        f"  💰 To'landi: {W(amount)}\n"
        f"  📊 Jami: {W(new_paid)} / {W(r[1])}\n"
    )
    if done:
        text += "  🎉 <b>Qarz to'liq yopildi!</b>"
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu_kb())
    return MAIN

# ── SAVINGS ───────────────────────────────────────────────────────────────────
async def menu_savings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, goal, current, icon FROM savings WHERE user_id=? ORDER BY id DESC", (uid,))
    rows = c.fetchall()
    conn.close()

    def pbar(pct, ln=8):
        f = int(pct/100*ln)
        return "█"*f + "░"*(ln-f)

    text = f"🏦 <b>JAMG'ARMA MAQSADLARI</b>\n{'─'*24}\n\n"
    if rows:
        total_cur = sum(r[3] for r in rows)
        total_goal = sum(r[2] for r in rows)
        text += f"📦 Jami: <b>{W(total_cur)}</b> / {W(total_goal)}\n\n"
        for r in rows:
            pct = int(r[3]/r[2]*100) if r[2] > 0 else 0
            remaining = r[2] - r[3]
            text += (
                f"{r[4]} <b>{r[1]}</b>\n"
                f"   [{pbar(pct)}] {pct}%\n"
                f"   {W(r[3])} / {W(r[2])} (qoldi: {W(remaining)})\n\n"
            )
    else:
        text += "Hali maqsad qo'yilmagan.\nBirinchi maqsadingizni qo'ying! 🎯\n"

    buttons = [[
        InlineKeyboardButton("➕ Yangi maqsad", callback_data="saving_new"),
    ]]
    if rows:
        buttons.append([InlineKeyboardButton("💰 Pul qo'shish", callback_data="saving_add_list")])
    buttons.append([InlineKeyboardButton("⬅️ Bosh menyu", callback_data="back_main")])

    await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
    return MAIN

async def saving_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    icons = ["🎯","🏠","✈️","🚗","💻","📱","🎓","💍","💪","🌍","💰","🎸"]
    kb_rows = []
    for i in range(0, len(icons), 4):
        kb_rows.append([InlineKeyboardButton(ic, callback_data=f"sv_icon_{ic}") for ic in icons[i:i+4]])
    kb_rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_savings")])
    await q.edit_message_text(
        "🏦 <b>YANGI MAQSAD</b>\n{'─'*20}\n\nAvvalo belgi (emoji) tanlang:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb_rows)
    )
    return MAIN

async def sv_icon_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    icon = q.data.replace("sv_icon_", "")
    ctx.user_data["sv_icon"] = icon
    await q.edit_message_text(
        f"🏦 Maqsad: {icon}\n\nMaqsad nomini kiriting:\n<i>Masalan: Yangi telefon, Ta'til</i>",
        parse_mode="HTML",
        reply_markup=back_kb("savings")
    )
    return ADD_SAVING_NAME

async def saving_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["sv_name"] = update.message.text.strip()
    icon = ctx.user_data.get("sv_icon", "🎯")
    await update.message.reply_text(
        f"{icon} <b>{ctx.user_data['sv_name']}</b>\n\nMaqsad summasi (₩):",
        parse_mode="HTML"
    )
    return ADD_SAVING_GOAL

async def saving_goal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        goal = float(update.message.text.replace(",", "").replace(" ", ""))
        if goal <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ To'g'ri summa kiriting!")
        return ADD_SAVING_GOAL
    uid = update.effective_user.id
    name = ctx.user_data.get("sv_name", "Maqsad")
    icon = ctx.user_data.get("sv_icon", "🎯")
    conn = get_db()
    conn.execute("INSERT INTO savings (user_id, name, goal, current, icon) VALUES (?,?,?,?,?)", (uid, name, goal, 0, icon))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ <b>Maqsad qo'yildi!</b>\n{'─'*20}\n\n  {icon} <b>{name}</b>\n  🎯 Maqsad: {W(goal)}\n  💪 Boshlaylik!",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )
    return MAIN

async def saving_add_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, goal, current, icon FROM savings WHERE user_id=? AND current<goal", (uid,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await q.edit_message_text("✨ Barcha maqsadlar bajarildi!", reply_markup=back_kb("savings"))
        return MAIN
    buttons = [[InlineKeyboardButton(f"{r[4]} {r[1]} — {W(r[3])}/{W(r[2])}", callback_data=f"sv_add_{r[0]}")] for r in rows]
    buttons.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_savings")])
    await q.edit_message_text(
        "💰 <b>Qaysi maqsadga pul qo'shasiz?</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return MAIN

async def sv_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    sv_id = int(q.data.replace("sv_add_", ""))
    ctx.user_data["sv_add_id"] = sv_id
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, goal, current, icon FROM savings WHERE id=?", (sv_id,))
    r = c.fetchone()
    conn.close()
    remaining = r[1] - r[2]
    await q.edit_message_text(
        f"{r[3]} <b>{r[0]}</b>\nQoldi: <b>{W(remaining)}</b>\n\nQo'shish summasi (₩):",
        parse_mode="HTML",
        reply_markup=back_kb("savings")
    )
    return ADD_TO_SAVING_AMOUNT

async def sv_add_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(",", "").replace(" ", ""))
        if amount <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ To'g'ri summa kiriting!")
        return ADD_TO_SAVING_AMOUNT
    sv_id = ctx.user_data.get("sv_add_id")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, goal, current, icon FROM savings WHERE id=?", (sv_id,))
    r = c.fetchone()
    new_cur = min(r[2] + amount, r[1])
    conn.execute("UPDATE savings SET current=? WHERE id=?", (new_cur, sv_id))
    conn.commit()
    conn.close()
    pct = int(new_cur/r[1]*100)
    done = new_cur >= r[1]

    def pbar(p, ln=10):
        f = int(p/100*ln)
        return "█"*f + "░"*(ln-f)

    text = (
        f"✅ <b>Qo'shildi!</b>\n{'─'*20}\n\n"
        f"  {r[3]} <b>{r[0]}</b>\n"
        f"  +{W(amount)}\n"
        f"  [{pbar(pct)}] {pct}%\n"
        f"  {W(new_cur)} / {W(r[1])}\n"
    )
    if done:
        text += "  🎉 <b>Maqsadga yetdingiz!</b> Tabriklayman!"
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu_kb())
    return MAIN

# ── STATISTICS ────────────────────────────────────────────────────────────────
async def show_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    conn = get_db()
    c = conn.cursor()
    now = datetime.now()
    m_start = f"{now.year}-{now.month:02d}-01"

    c.execute("""
        SELECT category, SUM(amount) as s FROM transactions 
        WHERE user_id=? AND type='chiqim' AND date>=?
        GROUP BY category ORDER BY s DESC LIMIT 5
    """, (uid, m_start))
    exp_cats = c.fetchall()

    c.execute("""
        SELECT SUM(amount) FROM transactions 
        WHERE user_id=? AND type='chiqim' AND date>=?
    """, (uid, m_start))
    total_exp = (c.fetchone()[0] or 0)

    c.execute("""
        SELECT date, SUM(amount) FROM transactions 
        WHERE user_id=? AND type='chiqim' AND date>=?
        GROUP BY date ORDER BY date DESC LIMIT 7
    """, (uid, m_start))
    daily = c.fetchall()
    conn.close()

    text = f"📈 <b>STATISTIKA — {now.strftime('%B %Y')}</b>\n{'─'*24}\n\n"
    if exp_cats:
        text += "<b>Top xarajatlar:</b>\n"
        for r in exp_cats:
            cat_name = EXP_CATS.get(r[0], r[0])
            pct = int(r[1]/total_exp*100) if total_exp > 0 else 0
            bar_len = int(pct/100*8)
            bar = "█"*bar_len + "░"*(8-bar_len)
            warn = " ⚠️" if pct > 40 else ""
            text += f"  {cat_name}\n  [{bar}] {pct}% — {W(r[1])}{warn}\n"
    if daily:
        text += "\n<b>Kunlik chiqim (so'nggi 7 kun):</b>\n"
        for d in daily:
            text += f"  📅 {fdate(d[0])}: <b>{W(d[1])}</b>\n"

    await q.edit_message_text(text, parse_mode="HTML", reply_markup=back_kb("status"))
    return MAIN

# ── BACK HANDLER ──────────────────────────────────────────────────────────────
async def back_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    dest = q.data.replace("back_", "")
    if dest == "main":
        await q.edit_message_text("Kerakli bo'limni tanlang:", reply_markup=main_menu_kb())
        return MAIN
    elif dest == "expense":
        return await menu_expense(update, ctx)
    elif dest == "income":
        return await menu_income(update, ctx)
    elif dest == "debts":
        return await menu_debts(update, ctx)
    elif dest == "savings":
        return await menu_savings(update, ctx)
    elif dest == "status":
        return await show_status(update, ctx)
    return MAIN

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=main_menu_kb())
    return MAIN

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN: [
                CallbackQueryHandler(menu_expense,      pattern="^menu_expense$"),
                CallbackQueryHandler(menu_income,       pattern="^menu_income$"),
                CallbackQueryHandler(menu_debts,        pattern="^menu_debts$"),
                CallbackQueryHandler(menu_savings,      pattern="^menu_savings$"),
                CallbackQueryHandler(show_status,       pattern="^menu_status$"),
                CallbackQueryHandler(show_stats,        pattern="^status_stats$"),
                CallbackQueryHandler(exp_cat_selected,  pattern="^exp_cat_"),
                CallbackQueryHandler(exp_no_note,       pattern="^exp_no_note$"),
                CallbackQueryHandler(inc_cat_selected,  pattern="^inc_cat_"),
                CallbackQueryHandler(inc_no_note,       pattern="^inc_no_note$"),
                CallbackQueryHandler(debt_add_start,    pattern="^debt_add_"),
                CallbackQueryHandler(debt_no_note,      pattern="^debt_no_note$"),
                CallbackQueryHandler(debt_pay_list,     pattern="^debt_pay_list$"),
                CallbackQueryHandler(pay_debt_start,    pattern="^pay_debt_"),
                CallbackQueryHandler(saving_new,        pattern="^saving_new$"),
                CallbackQueryHandler(sv_icon_selected,  pattern="^sv_icon_"),
                CallbackQueryHandler(saving_add_list,   pattern="^saving_add_list$"),
                CallbackQueryHandler(sv_add_start,      pattern="^sv_add_"),
                CallbackQueryHandler(back_handler,      pattern="^back_"),
            ],
            ADD_EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, exp_amount)],
            ADD_EXPENSE_NOTE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, exp_note),
                                 CallbackQueryHandler(exp_no_note, pattern="^exp_no_note$")],
            ADD_INCOME_AMOUNT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, inc_amount)],
            ADD_INCOME_NOTE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, inc_note),
                                 CallbackQueryHandler(inc_no_note, pattern="^inc_no_note$")],
            ADD_DEBT_NAME:      [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_name)],
            ADD_DEBT_AMOUNT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_amount)],
            ADD_DEBT_NOTE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_note),
                                 CallbackQueryHandler(debt_no_note, pattern="^debt_no_note$")],
            ADD_SAVING_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, saving_name)],
            ADD_SAVING_GOAL:    [MessageHandler(filters.TEXT & ~filters.COMMAND, saving_goal)],
            ADD_TO_SAVING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sv_add_amount)],
            PAY_DEBT_AMOUNT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_debt_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    print("✅ Moliya Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
