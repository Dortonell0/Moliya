#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Moliya Pro — Premium Telegram moliya boti"""

import logging, sqlite3, os, calendar
from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler)

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DB_PATH = "moliya.db"

# ══════════════════════════════════════════════════════════════
# DESIGN SYSTEM — iOS Glass style
# ══════════════════════════════════════════════════════════════
LOGO = "💎"
DIV  = "┄" * 22
DIV2 = "═" * 22

def hdr(title, icon=""):
    return f"{icon} <b>{title}</b>\n{DIV}\n"

def card(lines):
    """iOS-style card block"""
    body = "\n".join(f"  {l}" for l in lines)
    return f"╭{'─'*22}╮\n{body}\n╰{'─'*22}╯"

def badge(text, style="primary"):
    styles = {"primary":"🔵","success":"🟢","danger":"🔴","warning":"🟡","info":"🟣"}
    return f"{styles.get(style,'⚪')} {text}"

def pbar(pct, n=10):
    filled = int(min(100,pct) / 100 * n)
    return "▓"*filled + "░"*(n-filled)

def W(n): return f"₩{abs(int(n or 0)):,}"
def td(): return date.today().isoformat()
def fd(s):
    try: return datetime.strptime(s,"%Y-%m-%d").strftime("%d.%m")
    except: return s
def fdt(s):
    try: return datetime.strptime(s,"%Y-%m-%d").strftime("%d %b, %Y")
    except: return s
def weekday_uz(d):
    return ["Du","Se","Ch","Pa","Ju","Sh","Ya"][d.weekday()]

# STATES
(S_MAIN, S_AMOUNT, S_NOTE, S_NAME, S_GOAL, S_DAILY,
 S_SV_ADD, S_PAY, S_BALANCE, S_CARD, S_DATE) = range(11)

# CATEGORIES
EC = {
    "food":    ("🛒","Oziq-ovqat"),
    "trans":   ("🚇","Transport"),
    "util":    ("💡","Kommunal"),
    "cloth":   ("👕","Kiyim"),
    "health":  ("💊","Sog'liq"),
    "edu":     ("📚","Ta'lim"),
    "fun":     ("🎮","Ko'ngil"),
    "cafe":    ("☕","Kafe"),
    "sub":     ("📱","Obuna"),
    "other":   ("📦","Boshqa"),
}
IC = {
    "salary":  ("💼","Maosh"),
    "free":    ("💻","Freelance"),
    "biz":     ("🏢","Biznes"),
    "gift":    ("🎁","Sovg'a"),
    "invest":  ("📈","Invest"),
    "other_i": ("✨","Boshqa"),
}
ALL_CATS = {**EC, **IC}

def cat_name(cid):
    c = ALL_CATS.get(cid)
    return f"{c[0]} {c[1]}" if c else cid

# ══════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════
def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS tx(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER, type TEXT, amount REAL,
            category TEXT, note TEXT, date TEXT,
            wallet TEXT DEFAULT 'cash',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS savings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER, name TEXT, goal REAL,
            current REAL DEFAULT 0, daily REAL DEFAULT 0,
            icon TEXT DEFAULT '🎯',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS wallets(
            uid INTEGER PRIMARY KEY,
            cash REAL DEFAULT 0, card REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS debts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER, type TEXT, name TEXT,
            amount REAL, paid REAL DEFAULT 0,
            note TEXT, date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        """)

def get_wallet(uid):
    with db() as c:
        r = c.execute("SELECT cash,card FROM wallets WHERE uid=?", (uid,)).fetchone()
        if not r:
            c.execute("INSERT INTO wallets(uid,cash,card) VALUES(?,0,0)", (uid,))
            return 0.0, 0.0
        return float(r[0] or 0), float(r[1] or 0)

def upd_wallet(uid, cash=None, card=None):
    w = get_wallet(uid)
    nc = cash if cash is not None else w[0]
    nk = card if card is not None else w[1]
    with db() as c:
        c.execute("INSERT OR REPLACE INTO wallets(uid,cash,card) VALUES(?,?,?)", (uid,nc,nk))

def add_tx(uid, typ, amount, cat, note, wallet, txdate=None):
    txdate = txdate or td()
    with db() as c:
        c.execute("INSERT INTO tx(uid,type,amount,category,note,date,wallet) VALUES(?,?,?,?,?,?,?)",
                  (uid,typ,amount,cat,note,txdate,wallet))
    cash, card = get_wallet(uid)
    delta = amount if typ=="kirim" else -amount
    if wallet=="cash": upd_wallet(uid, cash=cash+delta)
    else: upd_wallet(uid, card=card+delta)

# ══════════════════════════════════════════════════════════════
# KEYBOARD BUILDERS
# ══════════════════════════════════════════════════════════════
def mk(*rows): return InlineKeyboardMarkup(list(rows))
def kb(*rows): return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=d) for t,d in row] for row in rows])
def btn1(t,d): return [[InlineKeyboardButton(t, callback_data=d)]]
def HOME(): return [InlineKeyboardButton("🏠  Bosh menyu", callback_data="home")]
def BACK(to): return [InlineKeyboardButton("‹  Orqaga", callback_data=to)]

def main_kb(uid):
    cash, card = get_wallet(uid)
    total = cash + card
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💵  Naqd  {W(cash)}", callback_data="show_cash"),
         InlineKeyboardButton(f"💳  Karta  {W(card)}", callback_data="show_card")],
        [InlineKeyboardButton("＋  Kirim", callback_data="menu_inc"),
         InlineKeyboardButton("－  Chiqim", callback_data="menu_exp")],
        [InlineKeyboardButton("📅  Kalendar", callback_data="cal_today"),
         InlineKeyboardButton("📊  Statistika", callback_data="stats_week")],
        [InlineKeyboardButton("🤝  Qarzlar", callback_data="debts"),
         InlineKeyboardButton("🏦  Jamg'arma", callback_data="savings")],
        [InlineKeyboardButton("💡  Maslahat", callback_data="advice"),
         InlineKeyboardButton("⚙️  Sozlamalar", callback_data="settings")],
    ])

def main_text(uid):
    cash, card = get_wallet(uid)
    total = cash + card
    now = datetime.now()
    m_start = f"{now.year}-{now.month:02d}-01"
    with db() as c:
        t = {r[0]:r[1] for r in c.execute(
            "SELECT type,SUM(amount) FROM tx WHERE uid=? AND date>=? GROUP BY type",
            (uid, m_start)).fetchall()}
    inc = t.get("kirim",0); exp = t.get("chiqim",0)
    balance_icon = "📈" if total >= 0 else "📉"
    return (
        f"\n"
        f"┌─────────────────────────┐\n"
        f"│  {LOGO}  <b>MOLIYA PRO</b>           │\n"
        f"└─────────────────────────┘\n\n"
        f"  {balance_icon} <b>Umumiy balans</b>\n"
        f"  <b>{W(total)}</b>\n\n"
        f"  💵 Naqd:   <b>{W(cash)}</b>\n"
        f"  💳 Karta:  <b>{W(card)}</b>\n\n"
        f"  {DIV}\n"
        f"  📅 <b>{now.strftime('%B %Y')}</b>\n"
        f"  🟢 Kirim:   {W(inc)}\n"
        f"  🔴 Chiqim:  {W(exp)}\n"
        f"  💰 Qoldi:   {W(inc-exp)}\n"
    )

# ══════════════════════════════════════════════════════════════
# CALENDAR
# ══════════════════════════════════════════════════════════════
def build_calendar(year, month, uid=None):
    """iOS-style calendar keyboard"""
    now = date.today()
    cal = calendar.monthcalendar(year, month)
    month_name = datetime(year, month, 1).strftime("%B %Y")
    prev = date(year, month, 1) - timedelta(days=1)
    nxt_d = date(year, month, 28) + timedelta(days=4)
    nxt = date(nxt_d.year, nxt_d.month, 1)

    rows = []
    # Header
    rows.append([
        InlineKeyboardButton("◀", callback_data=f"cal_{prev.year}_{prev.month}"),
        InlineKeyboardButton(f"📅  {month_name}", callback_data="cal_ignore"),
        InlineKeyboardButton("▶", callback_data=f"cal_{nxt.year}_{nxt.month}"),
    ])
    # Day names
    rows.append([InlineKeyboardButton(d, callback_data="cal_ignore")
                 for d in ["Du","Se","Ch","Pa","Ju","Sh","Ya"]])
    # Days
    for week in cal:
        row = []
        for d in week:
            if d == 0:
                row.append(InlineKeyboardButton(" ", callback_data="cal_ignore"))
            else:
                curr_date = date(year, month, d)
                label = str(d)
                if curr_date == now: label = f"[{d}]"
                row.append(InlineKeyboardButton(label,
                    callback_data=f"cal_sel_{year}_{month}_{d}"))
        rows.append(row)
    rows.append([
        InlineKeyboardButton("📌  Bugun", callback_data=f"cal_sel_{now.year}_{now.month}_{now.day}"),
        InlineKeyboardButton("🏠  Menyu", callback_data="home"),
    ])
    return InlineKeyboardMarkup(rows)

async def show_calendar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    data = q.data
    if data == "cal_today":
        now = date.today()
        y, m = now.year, now.month
    else:
        parts = data.split("_")
        y, m = int(parts[1]), int(parts[2])
    await q.edit_message_text(
        f"📅 <b>KALENDAR</b>\n{DIV}\n\nKunni tanlang yoki statistikani ko'ring:",
        parse_mode="HTML",
        reply_markup=build_calendar(y, m, uid)
    )

async def cal_day_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    parts = q.data.split("_")
    y, m, d = int(parts[2]), int(parts[3]), int(parts[4])
    sel_date = date(y, m, d)
    ctx.user_data["sel_date"] = sel_date.isoformat()

    with db() as c:
        rows = c.execute("""SELECT type,amount,category,note,wallet FROM tx
            WHERE uid=? AND date=? ORDER BY id DESC""", (uid, sel_date.isoformat())).fetchall()

    total_in = sum(r[1] for r in rows if r[0]=="kirim")
    total_out = sum(r[1] for r in rows if r[0]=="chiqim")
    day_name = weekday_uz(sel_date)
    text = (f"📅 <b>{d} {sel_date.strftime('%B %Y')} — {day_name}</b>\n{DIV}\n\n")
    if rows:
        for r in rows:
            icon = "🟢" if r[0]=="kirim" else "🔴"
            w_ic = "💵" if r[1+3]=="cash" else "💳"
            sign = "+" if r[0]=="kirim" else "-"
            text += f"  {icon} {sign}{W(r[1])} {cat_name(r[2])} {w_ic}\n"
            if r[3]: text += f"     📝 {r[3]}\n"
        text += f"\n{DIV}\n"
        text += f"  🟢 Jami kirim:  {W(total_in)}\n"
        text += f"  🔴 Jami chiqim: {W(total_out)}\n"
        text += f"  💰 Balans:      {W(total_in-total_out)}\n"
    else:
        text += "  Bu kunda harakatlar yo'q.\n"

    kb_rows = [
        [InlineKeyboardButton(f"＋ Kirim ({d}.{m:02d})", callback_data=f"dated_inc"),
         InlineKeyboardButton(f"－ Chiqim ({d}.{m:02d})", callback_data=f"dated_exp")],
        [InlineKeyboardButton("◀ Kalendarga qaytish", callback_data=f"cal_{y}_{m}")],
        [HOME()[0]],
    ]
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))

async def dated_tx(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    direction = "kirim" if "inc" in q.data else "chiqim"
    ctx.user_data["direction"] = direction
    ctx.user_data["use_date"] = ctx.user_data.get("sel_date", td())
    cats = IC if direction=="kirim" else EC
    rows = []
    items = list(cats.items())
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(f"{items[i][1][0]} {items[i][1][1]}", callback_data=f"cat_{items[i][0]}")]
        if i+1 < len(items):
            row.append(InlineKeyboardButton(f"{items[i+1][1][0]} {items[i+1][1][1]}", callback_data=f"cat_{items[i+1][0]}"))
        rows.append(row)
    sel_date = ctx.user_data.get("sel_date", td())
    rows.append([InlineKeyboardButton("◀ Orqaga", callback_data=f"cal_sel_{'_'.join(sel_date.split('-'))}")])
    d_icon = "＋" if direction=="kirim" else "－"
    await q.edit_message_text(
        f"{d_icon} <b>{'KIRIM' if direction=='kirim' else 'CHIQIM'}</b>\n"
        f"📅 {fdt(ctx.user_data.get('sel_date', td()))}\n{DIV}\n\nKategoriya:",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows)
    )

# ══════════════════════════════════════════════════════════════
# MAIN MENU
# ══════════════════════════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    get_wallet(uid)
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"┌─────────────────────────┐\n"
        f"│  {LOGO}  <b>MOLIYA PRO</b>           │\n"
        f"│  Premium moliya boti    │\n"
        f"└─────────────────────────┘\n\n"
        f"Xush kelibsiz, <b>{name}</b>! 👋\n\n"
        f"Avval hisobingiz balansini kiriting:\n",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💵  Naqd pul balansini kiriting", callback_data="set_cash")],
            [InlineKeyboardButton("💳  Karta balansini kiriting", callback_data="set_card")],
            [InlineKeyboardButton("⏭  O'tkazib yuborish", callback_data="home")],
        ])
    )
    return S_MAIN

async def home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = (q or update).from_user.id
    if q: await q.answer()
    text = main_text(uid)
    kb = main_kb(uid)
    if q:
        try: await q.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        except: pass
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    return S_MAIN

# ══════════════════════════════════════════════════════════════
# SETTINGS / BALANCE
# ══════════════════════════════════════════════════════════════
async def settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    cash, card = get_wallet(uid)
    await q.edit_message_text(
        f"⚙️ <b>SOZLAMALAR</b>\n{DIV}\n\n"
        f"  💵 Naqd pul:   <b>{W(cash)}</b>\n"
        f"  💳 Plastik:    <b>{W(card)}</b>\n"
        f"  💰 Jami:       <b>{W(cash+card)}</b>\n",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💵  Naqd pulni yangilash", callback_data="set_cash")],
            [InlineKeyboardButton("💳  Karta balansini yangilash", callback_data="set_card")],
            [HOME()[0]],
        ])
    )

async def set_cash_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["bal_type"] = "cash"
    await q.edit_message_text(
        f"💵 <b>NAQD PUL BALANSI</b>\n{DIV}\n\n"
        f"  Hozirgi naqd pulini kiriting:\n"
        f"  <i>Masalan: 250000</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹  Orqaga", callback_data="settings")]])
    )
    return S_BALANCE

async def set_card_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["bal_type"] = "card"
    await q.edit_message_text(
        f"💳 <b>KARTA BALANSI</b>\n{DIV}\n\n"
        f"  Hozirgi karta balansini kiriting:\n"
        f"  <i>Masalan: 1500000</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹  Orqaga", callback_data="settings")]])
    )
    return S_CARD

async def bal_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(",","").replace(" ","").strip())
    except:
        await update.message.reply_text("❌ Faqat raqam kiriting!\n<i>Masalan: 250000</i>", parse_mode="HTML")
        return S_BALANCE
    uid = update.effective_user.id
    btype = ctx.user_data.get("bal_type","cash")
    if btype == "cash":
        upd_wallet(uid, cash=amount)
        icon, label = "💵", "Naqd pul"
    else:
        upd_wallet(uid, card=amount)
        icon, label = "💳", "Plastik karta"
    await update.message.reply_text(
        f"✅ <b>{label} yangilandi!</b>\n{DIV}\n\n  {icon} <b>{W(amount)}</b>",
        parse_mode="HTML"
    )
    return await home(update, ctx)

# ══════════════════════════════════════════════════════════════
# WALLETS DETAIL
# ══════════════════════════════════════════════════════════════
async def show_cash(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    cash, _ = get_wallet(uid)
    with db() as c:
        rows = c.execute("""SELECT type,amount,category,note,date FROM tx
            WHERE uid=? AND wallet='cash' ORDER BY id DESC LIMIT 8""", (uid,)).fetchall()
    text = f"💵 <b>NAQD PUL</b>\n{DIV}\n\n"
    text += f"  Balans: <b>{W(cash)}</b>\n\n"
    if rows:
        text += f"  <b>So'nggi harakatlar:</b>\n"
        for r in rows:
            icon = "🟢" if r[0]=="kirim" else "🔴"
            sign = "+" if r[0]=="kirim" else "-"
            text += f"  {icon} {sign}{W(r[1])}  {cat_name(r[2])}  <i>{fd(r[4])}</i>\n"
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("＋ Kirim", callback_data="qi_cash_inc"),
         InlineKeyboardButton("－ Chiqim", callback_data="qi_cash_exp")],
        [InlineKeyboardButton("✏️  Balansni yangilash", callback_data="set_cash")],
        [HOME()[0]],
    ]))

async def show_card(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    _, card = get_wallet(uid)
    with db() as c:
        rows = c.execute("""SELECT type,amount,category,note,date FROM tx
            WHERE uid=? AND wallet='card' ORDER BY id DESC LIMIT 8""", (uid,)).fetchall()
    text = f"💳 <b>PLASTIK KARTA</b>\n{DIV}\n\n"
    text += f"  Balans: <b>{W(card)}</b>\n\n"
    if rows:
        text += f"  <b>So'nggi harakatlar:</b>\n"
        for r in rows:
            icon = "🟢" if r[0]=="kirim" else "🔴"
            sign = "+" if r[0]=="kirim" else "-"
            text += f"  {icon} {sign}{W(r[1])}  {cat_name(r[2])}  <i>{fd(r[4])}</i>\n"
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("＋ Kirim", callback_data="qi_card_inc"),
         InlineKeyboardButton("－ Chiqim", callback_data="qi_card_exp")],
        [InlineKeyboardButton("✏️  Balansni yangilash", callback_data="set_card")],
        [HOME()[0]],
    ]))

# ══════════════════════════════════════════════════════════════
# INCOME / EXPENSE FLOW
# ══════════════════════════════════════════════════════════════
def cat_keyboard(cats, back_cb):
    items = list(cats.items())
    rows = []
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(f"{items[i][1][0]} {items[i][1][1]}", callback_data=f"cat_{items[i][0]}")]
        if i+1 < len(items):
            row.append(InlineKeyboardButton(f"{items[i+1][1][0]} {items[i+1][1][1]}", callback_data=f"cat_{items[i+1][0]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("‹  Orqaga", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)

async def menu_inc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["direction"] = "kirim"
    ctx.user_data["use_date"] = td()
    await q.edit_message_text(
        f"＋ <b>KIRIM</b>\n{DIV}\n\nKategoriyani tanlang:",
        parse_mode="HTML", reply_markup=cat_keyboard(IC, "home"))

async def menu_exp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["direction"] = "chiqim"
    ctx.user_data["use_date"] = td()
    await q.edit_message_text(
        f"－ <b>CHIQIM</b>\n{DIV}\n\nKategoriyani tanlang:",
        parse_mode="HTML", reply_markup=cat_keyboard(EC, "home"))

async def qi_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Quick income/expense from wallet detail"""
    q = update.callback_query; await q.answer()
    d = q.data
    wallet = "cash" if "cash" in d else "card"
    direction = "kirim" if "inc" in d else "chiqim"
    ctx.user_data["direction"] = direction
    ctx.user_data["wallet"] = wallet
    ctx.user_data["use_date"] = td()
    cats = IC if direction=="kirim" else EC
    back = "show_cash" if wallet=="cash" else "show_card"
    d_icon = "＋" if direction=="kirim" else "－"
    w_icon = "💵 Naqd" if wallet=="cash" else "💳 Karta"
    await q.edit_message_text(
        f"{d_icon} <b>{'KIRIM' if direction=='kirim' else 'CHIQIM'}</b>  {w_icon}\n{DIV}\n\nKategoriya:",
        parse_mode="HTML", reply_markup=cat_keyboard(cats, back))

async def cat_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cat = q.data.replace("cat_","")
    ctx.user_data["cat"] = cat
    direction = ctx.user_data.get("direction","chiqim")
    # If wallet not yet chosen
    if "wallet" not in ctx.user_data:
        uid = q.from_user.id
        cash, card = get_wallet(uid)
        d_icon = "＋" if direction=="kirim" else "－"
        await q.edit_message_text(
            f"{d_icon} <b>{cat_name(cat)}</b>\n{DIV}\n\nQaysi hisobdan?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"💵  Naqd  ({W(cash)})", callback_data="wallet_cash"),
                 InlineKeyboardButton(f"💳  Karta  ({W(card)})", callback_data="wallet_card")],
                [HOME()[0]],
            ])
        )
    else:
        await ask_amount(q, ctx)

async def wallet_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["wallet"] = "cash" if "cash" in q.data else "card"
    await ask_amount(q, ctx)

async def ask_amount(q, ctx):
    cat = ctx.user_data.get("cat","other")
    direction = ctx.user_data.get("direction","chiqim")
    wallet = ctx.user_data.get("wallet","cash")
    w_icon = "💵" if wallet=="cash" else "💳"
    d_icon = "＋" if direction=="kirim" else "－"
    sel_date = ctx.user_data.get("use_date", td())
    await q.edit_message_text(
        f"{d_icon} <b>{cat_name(cat)}</b>  {w_icon}\n"
        f"📅 {fdt(sel_date)}\n{DIV}\n\n"
        f"  Summani kiriting (₩):\n"
        f"  <i>Masalan: 50000</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[HOME()[0]]])
    )
    return S_AMOUNT

async def amount_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(",","").replace(" ","").strip())
        if amount <= 0: raise ValueError
    except:
        await update.message.reply_text(
            "❌ <b>Noto'g'ri summa!</b>\nFaqat raqam kiriting.\n<i>Masalan: 50000</i>",
            parse_mode="HTML")
        return S_AMOUNT
    ctx.user_data["amount"] = amount
    cat = ctx.user_data.get("cat","other")
    direction = ctx.user_data.get("direction","chiqim")
    wallet = ctx.user_data.get("wallet","cash")
    w_icon = "💵" if wallet=="cash" else "💳"
    d_icon = "＋" if direction=="kirim" else "－"
    await update.message.reply_text(
        f"{d_icon} <b>{cat_name(cat)}</b>  {w_icon}\n"
        f"💰 <b>{W(amount)}</b>\n{DIV}\n\n"
        f"  Izoh yozing yoki o'tkazing:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭  Izohsiz saqlash", callback_data="save_no_note")],
            [HOME()[0]],
        ])
    )
    return S_NOTE

async def note_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["note"] = update.message.text.strip()
    return await do_save_tx(update, ctx)

async def save_no_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["note"] = ""
    return await do_save_tx(update, ctx)

async def do_save_tx(update, ctx):
    uid = update.effective_user.id
    amount = ctx.user_data.get("amount",0)
    cat = ctx.user_data.get("cat","other")
    note = ctx.user_data.get("note","")
    direction = ctx.user_data.get("direction","chiqim")
    wallet = ctx.user_data.get("wallet","cash")
    txdate = ctx.user_data.get("use_date", td())
    add_tx(uid, direction, amount, cat, note, wallet, txdate)
    cash, card = get_wallet(uid)
    w_icon = "💵 Naqd" if wallet=="cash" else "💳 Karta"
    d_icon = "＋" if direction=="kirim" else "－"
    sign = "+" if direction=="kirim" else "−"
    result_icon = "🟢" if direction=="kirim" else "🔴"
    text = (
        f"{result_icon} <b>Saqlandi!</b>\n{DIV}\n\n"
        f"  {d_icon} {cat_name(cat)}\n"
        f"  {w_icon}\n"
        f"  💰 {sign}<b>{W(amount)}</b>\n"
        f"  📅 {fdt(txdate)}\n"
        + (f"  📝 {note}\n" if note else "")
        + f"\n{DIV}\n"
        f"  💵 Naqd:  <b>{W(cash)}</b>\n"
        f"  💳 Karta: <b>{W(card)}</b>\n"
        f"  💰 Jami:  <b>{W(cash+card)}</b>"
    )
    kb_rows = [
        [InlineKeyboardButton("＋  Yana kirim", callback_data="menu_inc"),
         InlineKeyboardButton("－  Yana chiqim", callback_data="menu_exp")],
        [InlineKeyboardButton("📅  Kalendar", callback_data="cal_today")],
        [HOME()[0]],
    ]
    ctx.user_data.pop("wallet", None)
    q = update.callback_query if hasattr(update,"callback_query") else None
    if q:
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))
    return S_MAIN

# ══════════════════════════════════════════════════════════════
# STATISTICS
# ══════════════════════════════════════════════════════════════
async def stats_week(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    week_start = (date.today() - timedelta(days=6)).isoformat()
    with db() as c:
        rows = c.execute("""SELECT date,type,SUM(amount) FROM tx
            WHERE uid=? AND date>=? GROUP BY date,type ORDER BY date""",
            (uid, week_start)).fetchall()
    days = {}
    for r in rows:
        if r[0] not in days: days[r[0]] = {"kirim":0,"chiqim":0}
        days[r[0]][r[1]] = r[2]
    if not days:
        await q.edit_message_text(
            f"📊 <b>HAFTALIK STATISTIKA</b>\n{DIV}\n\n  Ma'lumot yo'q.",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[HOME()[0]]]))
        return
    total_in = sum(d["kirim"] for d in days.values())
    total_out = sum(d["chiqim"] for d in days.values())
    best_in = max(days.items(), key=lambda x: x[1]["kirim"], default=None)
    worst_out = max(days.items(), key=lambda x: x[1]["chiqim"], default=None)
    text = f"📊 <b>HAFTALIK STATISTIKA</b>\n{DIV}\n\n"
    mx = max((max(d["kirim"],d["chiqim"]) for d in days.values()), default=1) or 1
    for d in sorted(days.keys()):
        inc = days[d]["kirim"]
        exp = days[d]["chiqim"]
        dt = datetime.strptime(d,"%Y-%m-%d")
        day_label = f"{dt.day:02d}.{dt.month:02d} {weekday_uz(dt)}"
        text += f"  <b>{day_label}</b>\n"
        if inc > 0:
            bar = "▓" * min(8, max(1, int(inc/mx*8)))
            text += f"    🟢 {bar} {W(inc)}\n"
        if exp > 0:
            bar = "▓" * min(8, max(1, int(exp/mx*8)))
            text += f"    🔴 {bar} {W(exp)}\n"
        if inc==0 and exp==0:
            text += f"    ○ Harakatlar yo'q\n"
    text += f"\n{DIV}\n"
    text += f"  🟢 Jami kirim:  <b>{W(total_in)}</b>\n"
    text += f"  🔴 Jami chiqim: <b>{W(total_out)}</b>\n"
    text += f"  💰 Sof balans:  <b>{W(total_in-total_out)}</b>\n\n"
    if best_in: text += f"  🏆 Eng ko'p kirim: <b>{fd(best_in[0])}</b> — {W(best_in[1]['kirim'])}\n"
    if worst_out: text += f"  📉 Eng ko'p chiqim: <b>{fd(worst_out[0])}</b> — {W(worst_out[1]['chiqim'])}\n"
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📈  To'liq statistika", callback_data="stats_full")],
        [InlineKeyboardButton("📅  Kalendar", callback_data="cal_today")],
        [HOME()[0]],
    ]))

async def stats_full(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    now = datetime.now()
    m_start = f"{now.year}-{now.month:02d}-01"
    with db() as c:
        ttl = {r[0]:r[1] for r in c.execute(
            "SELECT type,SUM(amount) FROM tx WHERE uid=? AND date>=? GROUP BY type",
            (uid, m_start)).fetchall()}
        by_cat = c.execute("""SELECT category,type,SUM(amount) as s FROM tx
            WHERE uid=? AND date>=? GROUP BY category,type ORDER BY s DESC LIMIT 10""",
            (uid, m_start)).fetchall()
    inc = ttl.get("kirim",0); exp = ttl.get("chiqim",0)
    save_pct = int((inc-exp)/inc*100) if inc>0 else 0
    text = f"📈 <b>{now.strftime('%B %Y')} — STATISTIKA</b>\n{DIV}\n\n"
    text += f"  🟢 Kirim:   <b>{W(inc)}</b>\n"
    text += f"  🔴 Chiqim:  <b>{W(exp)}</b>\n"
    text += f"  💰 Sof:     <b>{W(inc-exp)}</b>\n"
    text += f"  💹 Tejash:  <b>{save_pct}%</b>\n"
    text += f"  {pbar(save_pct)}\n\n"
    if by_cat:
        text += f"  <b>Kategoriyalar:</b>\n"
        for r in by_cat[:8]:
            total_base = inc if r[1]=="kirim" else exp
            pct = int(r[2]/total_base*100) if total_base>0 else 0
            bar = "▓"*(pct//10) + "░"*(10-pct//10)
            icon = "🟢" if r[1]=="kirim" else "🔴"
            text += f"  {icon} {cat_name(r[0])}\n"
            text += f"    [{bar}] {pct}%  {W(r[2])}\n"
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📊  Haftalik", callback_data="stats_week")],
        [HOME()[0]],
    ]))

# ══════════════════════════════════════════════════════════════
# ADVICE
# ══════════════════════════════════════════════════════════════
async def show_advice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    cash, card = get_wallet(uid)
    total = cash + card
    now = datetime.now()
    m_start = f"{now.year}-{now.month:02d}-01"
    days_left = (date(now.year,now.month+1 if now.month<12 else 1,1)-timedelta(1)).day - now.day + 1
    with db() as c:
        ttl = {r[0]:r[1] for r in c.execute(
            "SELECT type,SUM(amount) FROM tx WHERE uid=? AND date>=? GROUP BY type",
            (uid,m_start)).fetchall()}
        top_exp = c.execute("""SELECT category,SUM(amount) as s FROM tx
            WHERE uid=? AND type='chiqim' AND date>=? GROUP BY category ORDER BY s DESC LIMIT 1""",
            (uid,m_start)).fetchone()
    inc=ttl.get("kirim",0); exp=ttl.get("chiqim",0)
    remain = max(0, inc-exp)
    daily_limit = int(remain/days_left) if days_left>0 else 0
    save_pct = int((inc-exp)/inc*100) if inc>0 else 0
    text = f"💡 <b>MOLIYAVIY MASLAHAT</b>\n{DIV}\n\n"
    text += f"  💰 Umumiy balans: <b>{W(total)}</b>\n"
    text += f"  📅 {now.strftime('%B')} da qoldi: <b>{days_left} kun</b>\n\n"
    if inc > 0:
        text += f"  <b>📊 50/30/20 Qoidasi:</b>\n"
        text += f"  🏠 Zaruriyat (50%):  {W(int(inc*.5))}\n"
        text += f"  🎭 Istak (30%):      {W(int(inc*.3))}\n"
        text += f"  💎 Jamg'arma (20%):  {W(int(inc*.2))}\n\n"
        text += f"  {DIV}\n"
        text += f"  ⏰ Kunlik limit: <b>{W(daily_limit)}</b>\n"
        text += f"  💹 Tejash: <b>{save_pct}%</b>  {pbar(save_pct)}\n\n"
    if top_exp:
        text += f"  ⚠️ Eng ko'p sarflagan: <b>{cat_name(top_exp[0])}</b>\n"
        text += f"     {W(top_exp[1])}\n\n"
    # Condition-based advice
    if save_pct < 0:
        text += f"  🔴 <b>Chiqim kirimdan oshdi!</b>\n  Xarajatlarni kamaytiring.\n"
    elif save_pct < 10:
        text += f"  🟡 Tejash pastroq. Maqsad qo'ying!\n"
    elif save_pct >= 20:
        text += f"  🟢 Ajoyib! Tejash yaxshi darajada.\n"
    if total > 0:
        cash_pct = int(cash/total*100)
        text += f"\n  <b>💳 Hisob taqsimoti:</b>\n"
        text += f"  💵 Naqd:  {W(cash)} ({cash_pct}%)\n"
        text += f"  💳 Karta: {W(card)} ({100-cash_pct}%)\n"
    await q.edit_message_text(text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[HOME()[0]]]))

# ══════════════════════════════════════════════════════════════
# DEBTS
# ══════════════════════════════════════════════════════════════
async def menu_debts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    with db() as c:
        rows = c.execute("SELECT id,type,name,amount,paid FROM debts WHERE uid=? ORDER BY id DESC", (uid,)).fetchall()
    active = [r for r in rows if r[4] < r[3]]
    done = [r for r in rows if r[4] >= r[3]]
    lent = sum(r[3]-r[4] for r in active if r[1]=="berilgan")
    borr = sum(r[3]-r[4] for r in active if r[1]=="olingan")
    text = f"🤝 <b>QARZLAR</b>\n{DIV}\n\n"
    text += f"  🔴 Men berdim (qoldi): <b>{W(lent)}</b>\n"
    text += f"  🟢 Men oldim (qoldi):  <b>{W(borr)}</b>\n"
    if active:
        text += f"\n  <b>Aktiv ({len(active)}):</b>\n"
        for r in active:
            icon = "🔴" if r[1]=="berilgan" else "🟢"
            pct = int(r[4]/r[3]*100) if r[3]>0 else 0
            text += f"  {icon} <b>{r[2]}</b>\n"
            text += f"    {W(r[4])}/{W(r[3])}  {pbar(pct,6)}  {pct}%\n"
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴  Men berdim", callback_data="debt_lent"),
         InlineKeyboardButton("🟢  Men oldim", callback_data="debt_borrow")],
        [InlineKeyboardButton("💳  To'lov kiritish", callback_data="debt_paylist")],
        [HOME()[0]],
    ]))

async def debt_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["debt_type"] = "berilgan" if "lent" in q.data else "olingan"
    label = "berdim" if "lent" in q.data else "oldim"
    icon = "🔴" if "lent" in q.data else "🟢"
    await q.edit_message_text(
        f"{icon} <b>Men {label}</b>\n{DIV}\n\nKimga/Kimdan? Ism kiriting:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹  Orqaga", callback_data="debts")]])
    )
    return S_NAME

async def debt_name_in(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["debt_name"] = update.message.text.strip()
    dtype = ctx.user_data.get("debt_type","berilgan")
    icon = "🔴" if dtype=="berilgan" else "🟢"
    label = "berdim" if dtype=="berilgan" else "oldim"
    await update.message.reply_text(
        f"{icon} Men {label}: <b>{ctx.user_data['debt_name']}</b>\n\nSumma kiriting (₩):",
        parse_mode="HTML")
    return S_AMOUNT

async def debt_amount_in(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(",","").strip())
        if amount <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ To'g'ri summa kiriting!")
        return S_AMOUNT
    uid = update.effective_user.id
    dtype = ctx.user_data.get("debt_type","berilgan")
    name = ctx.user_data.get("debt_name","")
    with db() as c:
        c.execute("INSERT INTO debts(uid,type,name,amount,paid,note,date) VALUES(?,?,?,?,0,'',?)",
                  (uid,dtype,name,amount,td()))
    icon = "🔴" if dtype=="berilgan" else "🟢"
    label = "berdim" if dtype=="berilgan" else "oldim"
    await update.message.reply_text(
        f"✅ <b>Saqlandi!</b>\n{DIV}\n\n  {icon} Men {label}: <b>{name}</b>\n  💰 {W(amount)}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🤝  Qarzlar", callback_data="debts")],
            [HOME()[0]],
        ])
    )
    return S_MAIN

async def debt_paylist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    with db() as c:
        rows = c.execute("SELECT id,type,name,amount,paid FROM debts WHERE uid=? AND paid<amount", (uid,)).fetchall()
    if not rows:
        await q.edit_message_text(
            f"✅ <b>To'lanadigan qarz yo'q!</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹  Orqaga", callback_data="debts")]])
        )
        return
    rows_kb = [[InlineKeyboardButton(
        f"{'🔴' if r[1]=='berilgan' else '🟢'} {r[2]} — {W(r[3]-r[4])} qoldi",
        callback_data=f"dpay_{r[0]}")] for r in rows]
    rows_kb.append([InlineKeyboardButton("‹  Orqaga", callback_data="debts")])
    await q.edit_message_text(
        f"💳 <b>TO'LOV KIRITISH</b>\n{DIV}\n\nQaysi qarz?",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows_kb))

async def debt_pay_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    did = int(q.data.split("_")[1])
    ctx.user_data["pay_did"] = did
    with db() as c:
        r = c.execute("SELECT name,amount,paid,type FROM debts WHERE id=?", (did,)).fetchone()
    icon = "🔴" if r[3]=="berilgan" else "🟢"
    await q.edit_message_text(
        f"{icon} <b>{r[0]}</b>\n"
        f"  Jami: {W(r[1])}\n"
        f"  To'langan: {W(r[2])}\n"
        f"  <b>Qoldi: {W(r[1]-r[2])}</b>\n\n"
        f"To'lov summasi:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹  Orqaga", callback_data="debt_paylist")]])
    )
    return S_PAY

async def debt_pay_in(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(",","").strip())
        if amount <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ To'g'ri summa kiriting!")
        return S_PAY
    did = ctx.user_data.get("pay_did")
    with db() as c:
        r = c.execute("SELECT name,amount,paid FROM debts WHERE id=?", (did,)).fetchone()
        new_paid = min(r[2]+amount, r[1])
        c.execute("UPDATE debts SET paid=? WHERE id=?", (new_paid, did))
    done = new_paid >= r[1]
    pct = int(new_paid/r[1]*100) if r[1]>0 else 0
    await update.message.reply_text(
        f"✅ <b>To'lov kiritildi!</b>\n{DIV}\n\n"
        f"  <b>{r[0]}</b>\n"
        f"  +{W(amount)} to'landi\n"
        f"  {pbar(pct)}  {pct}%\n"
        + (f"  🎉 <b>Qarz to'liq yopildi!</b>" if done else f"  Qoldi: {W(r[1]-new_paid)}"),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🤝  Qarzlar", callback_data="debts")],
            [HOME()[0]],
        ])
    )
    return S_MAIN

# ══════════════════════════════════════════════════════════════
# SAVINGS
# ══════════════════════════════════════════════════════════════
async def menu_savings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    with db() as c:
        rows = c.execute("SELECT id,name,goal,current,daily,icon FROM savings WHERE uid=? ORDER BY id DESC", (uid,)).fetchall()
    if not rows:
        await q.edit_message_text(
            f"🏦 <b>JAMG'ARMA MAQSADLARI</b>\n{DIV}\n\n"
            f"  Hali maqsad yo'q.\n  Birinchi maqsadingizni qo'ying! 🎯",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕  Yangi maqsad", callback_data="sv_new")],
                [HOME()[0]],
            ])
        )
        return
    text = f"🏦 <b>JAMG'ARMA MAQSADLARI</b>\n{DIV}\n\n"
    total_cur = sum(r[3] for r in rows)
    total_goal = sum(r[2] for r in rows)
    text += f"  Jami: {W(total_cur)} / {W(total_goal)}\n\n"
    for r in rows:
        pct = int(r[3]/r[2]*100) if r[2]>0 else 0
        rem = r[2]-r[3]
        days_need = int(rem/r[4]) if r[4]>0 and rem>0 else 0
        done_date = (date.today()+timedelta(days=days_need)).strftime("%d.%m.%Y") if days_need>0 else "✅"
        text += f"  {r[5]} <b>{r[1]}</b>\n"
        text += f"  {pbar(pct)}  {pct}%\n"
        text += f"  {W(r[3])} / {W(r[2])}\n"
        if r[4]>0 and rem>0:
            text += f"  ⏰ Kuniga {W(r[4])} → {done_date}\n"
        text += "\n"
    sv_add_btns = [[InlineKeyboardButton(f"{r[5]} {r[1]}", callback_data=f"sv_add_{r[0]}")] for r in rows if r[3]<r[2]]
    all_rows = sv_add_btns + [
        [InlineKeyboardButton("➕  Yangi maqsad", callback_data="sv_new")],
        [HOME()[0]],
    ]
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(all_rows))

SAVE_ICONS = ["🎯","🏠","✈️","🚗","💻","📱","🎓","💍","🌍","💰","🎸","⚽"]

async def sv_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    rows = []
    for i in range(0, len(SAVE_ICONS), 4):
        rows.append([InlineKeyboardButton(ic, callback_data=f"svi_{ic}") for ic in SAVE_ICONS[i:i+4]])
    rows.append([InlineKeyboardButton("‹  Orqaga", callback_data="savings")])
    await q.edit_message_text(
        f"🏦 <b>YANGI MAQSAD</b>\n{DIV}\n\nBelgi tanlang:",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))

async def sv_icon_sel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["sv_icon"] = q.data.replace("svi_","")
    await q.edit_message_text(
        f"{ctx.user_data['sv_icon']} <b>Maqsad nomi:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹  Orqaga", callback_data="sv_new")]]))
    return S_NAME

async def sv_name_in(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["sv_name"] = update.message.text.strip()
    icon = ctx.user_data.get("sv_icon","🎯")
    await update.message.reply_text(
        f"{icon} <b>{ctx.user_data['sv_name']}</b>\n\nMaqsad summasi (₩):",
        parse_mode="HTML")
    return S_GOAL

async def sv_goal_in(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        goal = float(update.message.text.replace(",","").strip())
        if goal <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ To'g'ri summa kiriting!"); return S_GOAL
    ctx.user_data["sv_goal"] = goal
    await update.message.reply_text(
        f"📅 Kuniga qancha yig'aysiz? (₩)\n\n"
        f"<i>Masalan: 10000 → qachon yetishini hisoblaymiz</i>",
        parse_mode="HTML")
    return S_DAILY

async def sv_daily_in(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        daily = float(update.message.text.replace(",","").strip())
        if daily <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ To'g'ri summa kiriting!"); return S_DAILY
    uid = update.effective_user.id
    goal = ctx.user_data.get("sv_goal",0)
    name = ctx.user_data.get("sv_name","Maqsad")
    icon = ctx.user_data.get("sv_icon","🎯")
    days = int(goal/daily) if daily>0 else 0
    months = days // 30
    done_date = (date.today()+timedelta(days=days)).strftime("%d.%m.%Y")
    with db() as c:
        c.execute("INSERT INTO savings(uid,name,goal,current,daily,icon) VALUES(?,?,?,0,?,?)",
                  (uid,name,goal,daily,icon))
    time_str = f"{months} oy {days%30} kun" if months>0 else f"{days} kun"
    await update.message.reply_text(
        f"✅ <b>Maqsad qo'yildi!</b>\n{DIV}\n\n"
        f"  {icon} <b>{name}</b>\n"
        f"  🎯 Maqsad:  {W(goal)}\n"
        f"  📅 Kuniga:  {W(daily)}\n"
        f"  ⏰ {time_str} ({done_date}) da yig'iladi!\n",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏦  Jamg'arma", callback_data="savings")],
            [HOME()[0]],
        ])
    )
    return S_MAIN

async def sv_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    sv_id = int(q.data.split("_")[2])
    ctx.user_data["sv_id"] = sv_id
    with db() as c:
        r = c.execute("SELECT name,goal,current,daily,icon FROM savings WHERE id=?", (sv_id,)).fetchone()
    rem = r[1]-r[2]; pct = int(r[2]/r[1]*100) if r[1]>0 else 0
    days = int(rem/r[3]) if r[3]>0 and rem>0 else 0
    await q.edit_message_text(
        f"{r[4]} <b>{r[0]}</b>\n{DIV}\n\n"
        f"  {pbar(pct)}  {pct}%\n"
        f"  {W(r[2])} / {W(r[1])}\n"
        f"  Qoldi: {W(rem)}"
        + (f"  (~{days} kun)" if days>0 else "")
        + f"\n\nQo'shish summasi (₩):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹  Orqaga", callback_data="savings")]]))
    return S_SV_ADD

async def sv_add_in(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(",","").strip())
        if amount <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ To'g'ri summa kiriting!"); return S_SV_ADD
    sv_id = ctx.user_data.get("sv_id")
    uid = update.effective_user.id
    with db() as c:
        r = c.execute("SELECT name,goal,current,daily,icon FROM savings WHERE id=?", (sv_id,)).fetchone()
        new_cur = min(r[2]+amount, r[1])
        c.execute("UPDATE savings SET current=? WHERE id=?", (new_cur, sv_id))
    pct = int(new_cur/r[1]*100) if r[1]>0 else 0
    rem = r[1]-new_cur
    days = int(rem/r[3]) if r[3]>0 and rem>0 else 0
    done = new_cur >= r[1]
    await update.message.reply_text(
        f"✅ {r[4]} <b>{r[0]}</b>\n{DIV}\n\n"
        f"  +{W(amount)} qo'shildi!\n"
        f"  {pbar(pct)}  {pct}%\n"
        f"  {W(new_cur)} / {W(r[1])}\n"
        + ("  🎉 <b>Maqsadga yetdingiz!</b>" if done else f"  Qoldi: {W(rem)}" + (f" (~{days} kun)" if days>0 else "")),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏦  Jamg'arma", callback_data="savings")],
            [HOME()[0]],
        ])
    )
    return S_MAIN

# ══════════════════════════════════════════════════════════════
# FALLBACK
# ══════════════════════════════════════════════════════════════
async def unknown_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        "🏠 Bosh menyuga:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠  Bosh menyu", callback_data="home")]]))
    return S_MAIN

async def cal_ignore(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

# ══════════════════════════════════════════════════════════════
# APP
# ══════════════════════════════════════════════════════════════
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    # All callback patterns
    ALL_CBS = {
        "home": home,
        "show_cash": show_cash,
        "show_card": show_card,
        "menu_inc": menu_inc,
        "menu_exp": menu_exp,
        "settings": settings,
        "set_cash": set_cash_start,
        "set_card": set_card_start,
        "stats_week": stats_week,
        "stats_full": stats_full,
        "cal_today": show_calendar,
        "advice": show_advice,
        "debts": menu_debts,
        "debt_lent": debt_add_start,
        "debt_borrow": debt_add_start,
        "debt_paylist": debt_paylist,
        "savings": menu_savings,
        "sv_new": sv_new,
        "save_no_note": save_no_note,
        "wallet_cash": wallet_selected,
        "wallet_card": wallet_selected,
    }

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            S_MAIN: [
                CallbackQueryHandler(home, pattern="^home$"),
                CallbackQueryHandler(show_cash, pattern="^show_cash$"),
                CallbackQueryHandler(show_card, pattern="^show_card$"),
                CallbackQueryHandler(menu_inc, pattern="^menu_inc$"),
                CallbackQueryHandler(menu_exp, pattern="^menu_exp$"),
                CallbackQueryHandler(settings, pattern="^settings$"),
                CallbackQueryHandler(set_cash_start, pattern="^set_cash$"),
                CallbackQueryHandler(set_card_start, pattern="^set_card$"),
                CallbackQueryHandler(stats_week, pattern="^stats_week$"),
                CallbackQueryHandler(stats_full, pattern="^stats_full$"),
                CallbackQueryHandler(show_calendar, pattern="^cal_(today|\\d+_\\d+)$"),
                CallbackQueryHandler(cal_day_selected, pattern="^cal_sel_"),
                CallbackQueryHandler(dated_tx, pattern="^dated_(inc|exp)$"),
                CallbackQueryHandler(cal_ignore, pattern="^cal_ignore$"),
                CallbackQueryHandler(show_advice, pattern="^advice$"),
                CallbackQueryHandler(menu_debts, pattern="^debts$"),
                CallbackQueryHandler(debt_add_start, pattern="^debt_(lent|borrow)$"),
                CallbackQueryHandler(debt_paylist, pattern="^debt_paylist$"),
                CallbackQueryHandler(debt_pay_start, pattern="^dpay_\\d+$"),
                CallbackQueryHandler(menu_savings, pattern="^savings$"),
                CallbackQueryHandler(sv_new, pattern="^sv_new$"),
                CallbackQueryHandler(sv_icon_sel, pattern="^svi_"),
                CallbackQueryHandler(sv_add, pattern="^sv_add_\\d+$"),
                CallbackQueryHandler(qi_start, pattern="^qi_"),
                CallbackQueryHandler(cat_selected, pattern="^cat_"),
                CallbackQueryHandler(wallet_selected, pattern="^wallet_"),
                CallbackQueryHandler(save_no_note, pattern="^save_no_note$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_msg),
            ],
            S_BALANCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bal_input),
                CallbackQueryHandler(settings, pattern="^settings$"),
                CallbackQueryHandler(home, pattern="^home$"),
            ],
            S_CARD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bal_input),
                CallbackQueryHandler(settings, pattern="^settings$"),
                CallbackQueryHandler(home, pattern="^home$"),
            ],
            S_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, amount_input),
                CallbackQueryHandler(home, pattern="^home$"),
                CallbackQueryHandler(cat_selected, pattern="^cat_"),
                CallbackQueryHandler(wallet_selected, pattern="^wallet_"),
                CallbackQueryHandler(debt_amount_in, pattern="^debt_amt$"),
            ],
            S_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, note_input),
                CallbackQueryHandler(save_no_note, pattern="^save_no_note$"),
                CallbackQueryHandler(home, pattern="^home$"),
            ],
            S_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_name_in),
                CallbackQueryHandler(home, pattern="^home$"),
                CallbackQueryHandler(menu_debts, pattern="^debts$"),
                CallbackQueryHandler(menu_savings, pattern="^savings$"),
            ],
            S_GOAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sv_goal_in),
                CallbackQueryHandler(home, pattern="^home$"),
            ],
            S_DAILY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sv_daily_in),
                CallbackQueryHandler(home, pattern="^home$"),
            ],
            S_SV_ADD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sv_add_in),
                CallbackQueryHandler(menu_savings, pattern="^savings$"),
                CallbackQueryHandler(home, pattern="^home$"),
            ],
            S_PAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_pay_in),
                CallbackQueryHandler(debt_paylist, pattern="^debt_paylist$"),
                CallbackQueryHandler(home, pattern="^home$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(home, pattern="^home$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(conv)

    # Savings name routing
    async def sv_name_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        action = ctx.user_data.get("current_action","")
        if action == "sv_name":
            return await sv_name_in(update, ctx)
        elif action == "debt_name":
            return await debt_name_in(update, ctx)
        return await unknown_msg(update, ctx)

    print("✅ Moliya Pro Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
