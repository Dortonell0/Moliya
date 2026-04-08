#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Moliya Pro Bot — Premium moliyaviy yordamchi"""

import logging, sqlite3, os, calendar
from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler)

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DB_PATH = "moliya.db"

# ─── DESIGN ───────────────────────────────────────────────────────────────────
DIV = "┄" * 20
def W(n): return f"₩{abs(int(n or 0)):,}"
def pbar(p, n=8): f=int(min(100,p)/100*n); return "▓"*f+"░"*(n-f)
def td(): return date.today().isoformat()
def fd(s):
    try: return datetime.strptime(s,"%Y-%m-%d").strftime("%d.%m")
    except: return s
def fdt(s):
    try: return datetime.strptime(s,"%Y-%m-%d").strftime("%d %B %Y")
    except: return s
def wday(d): return ["Du","Se","Ch","Pa","Ju","Sh","Ya"][d.weekday()]

# ─── STATES ───────────────────────────────────────────────────────────────────
WAIT = 0  # single universal waiting state

# ─── CATEGORIES ───────────────────────────────────────────────────────────────
EC = {"food":("🛒","Oziq-ovqat"),"transport":("🚇","Transport"),
      "utility":("💡","Kommunal"),"clothing":("👕","Kiyim"),
      "health":("💊","Sog'liq"),"edu":("📚","Ta'lim"),
      "fun":("🎮","Ko'ngil"),"cafe":("☕","Kafe"),
      "sub":("📱","Obuna"),"other":("📦","Boshqa")}
IC = {"salary":("💼","Maosh"),"freelance":("💻","Freelance"),
      "biz":("🏢","Biznes"),"gift":("🎁","Sovg'a"),
      "invest":("📈","Invest"),"other_i":("✨","Boshqa")}
ALL = {**EC,**IC}
def cname(id): c=ALL.get(id); return f"{c[0]} {c[1]}" if c else id

# ─── DATABASE ─────────────────────────────────────────────────────────────────
def db():
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS tx(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER,type TEXT,amount REAL,
            category TEXT,note TEXT,date TEXT,wallet TEXT DEFAULT 'cash');
        CREATE TABLE IF NOT EXISTS savings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER,name TEXT,goal REAL,
            current REAL DEFAULT 0,daily REAL DEFAULT 0,icon TEXT DEFAULT '🎯');
        CREATE TABLE IF NOT EXISTS wallets(
            uid INTEGER PRIMARY KEY,cash REAL DEFAULT 0,card REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS debts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER,type TEXT,name TEXT,
            amount REAL,paid REAL DEFAULT 0,note TEXT,date TEXT);
        """)

def gwallet(uid):
    with db() as c:
        r = c.execute("SELECT cash,card FROM wallets WHERE uid=?", (uid,)).fetchone()
        if not r: c.execute("INSERT INTO wallets(uid,cash,card) VALUES(?,0,0)",(uid,)); return 0.0,0.0
        return float(r[0] or 0),float(r[1] or 0)

def swallet(uid,cash=None,card=None):
    w = gwallet(uid)
    nc = cash if cash is not None else w[0]
    nk = card if card is not None else w[1]
    with db() as c:
        c.execute("INSERT OR REPLACE INTO wallets(uid,cash,card) VALUES(?,?,?)",(uid,nc,nk))

def add_tx(uid,typ,amt,cat,note,wallet,txdate=None):
    with db() as c:
        c.execute("INSERT INTO tx(uid,type,amount,category,note,date,wallet) VALUES(?,?,?,?,?,?,?)",
                  (uid,typ,amt,cat,note,txdate or td(),wallet))
    ca,cd = gwallet(uid)
    d = amt if typ=="kirim" else -amt
    if wallet=="cash": swallet(uid,cash=ca+d)
    else: swallet(uid,card=cd+d)

# ─── KEYBOARDS ────────────────────────────────────────────────────────────────
def HOME(): return InlineKeyboardButton("🏠  Ana sahifa",callback_data="home")
def BACK(cb): return InlineKeyboardButton("‹  Orqaga",callback_data=cb)

def home_kb(uid):
    ca,cd = gwallet(uid)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💵  Naqd  {W(ca)}",callback_data="show_cash"),
         InlineKeyboardButton(f"💳  Karta  {W(cd)}",callback_data="show_card")],
        [InlineKeyboardButton("＋  Kirim",callback_data="inc_menu"),
         InlineKeyboardButton("－  Chiqim",callback_data="exp_menu")],
        [InlineKeyboardButton("📅  Kalendar",callback_data="cal_now"),
         InlineKeyboardButton("📊  Statistika",callback_data="stats")],
        [InlineKeyboardButton("🤝  Qarzlar",callback_data="debts"),
         InlineKeyboardButton("🏦  Jamg'arma",callback_data="savings")],
        [InlineKeyboardButton("💡  Maslahat",callback_data="advice"),
         InlineKeyboardButton("⚙️  Sozlamalar",callback_data="settings")],
    ])

def home_text(uid):
    ca,cd = gwallet(uid)
    tot = ca+cd
    now = datetime.now()
    ms = f"{now.year}-{now.month:02d}-01"
    with db() as c:
        t = {r[0]:r[1] for r in c.execute(
            "SELECT type,SUM(amount) FROM tx WHERE uid=? AND date>=? GROUP BY type",(uid,ms)).fetchall()}
    inc=t.get("kirim",0); exp=t.get("chiqim",0)
    return (
        f"\n┌──────────────────────────┐\n"
        f"│  💎  <b>MOLIYA PRO</b>           │\n"
        f"└──────────────────────────┘\n\n"
        f"  📊 <b>Umumiy balans</b>\n"
        f"  <b>{W(tot)}</b>\n\n"
        f"  💵 Naqd:   <b>{W(ca)}</b>\n"
        f"  💳 Karta:  <b>{W(cd)}</b>\n\n"
        f"  {DIV}\n"
        f"  📅 <b>{now.strftime('%B %Y')}</b>\n"
        f"  🟢 Kirim:   {W(inc)}\n"
        f"  🔴 Chiqim:  {W(exp)}\n"
        f"  💰 Qoldi:   {W(inc-exp)}\n"
    )

async def send_home(uid, update, ctx):
    text = home_text(uid)
    kb = home_kb(uid)
    q = getattr(update,"callback_query",None)
    if q:
        try: await q.edit_message_text(text,parse_mode="HTML",reply_markup=kb)
        except: await update.effective_message.reply_text(text,parse_mode="HTML",reply_markup=kb)
    else:
        await update.message.reply_text(text,parse_mode="HTML",reply_markup=kb)

# ─── START ────────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    gwallet(uid)
    name = update.effective_user.first_name
    ctx.user_data.clear()
    ctx.user_data["step"] = "idle"
    await update.message.reply_text(
        f"┌──────────────────────────┐\n"
        f"│  💎  <b>MOLIYA PRO</b>           │\n"
        f"│  Premium moliya boti     │\n"
        f"└──────────────────────────┘\n\n"
        f"Xush kelibsiz, <b>{name}</b>! 👋\n\n"
        f"Hisobingiz balansini kiriting:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💵  Naqd pul balansini kiriting",callback_data="set_cash")],
            [InlineKeyboardButton("💳  Karta balansini kiriting",callback_data="set_card")],
            [InlineKeyboardButton("⏭  O'tkazib yuborish",callback_data="home")],
        ])
    )
    return WAIT

# ─── HOME ─────────────────────────────────────────────────────────────────────
async def cb_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    ctx.user_data["step"] = "idle"
    await send_home(uid, update, ctx)
    return WAIT

# ─── SETTINGS ─────────────────────────────────────────────────────────────────
async def cb_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; ca,cd = gwallet(uid)
    await q.edit_message_text(
        f"⚙️ <b>SOZLAMALAR</b>\n{DIV}\n\n"
        f"  💵 Naqd:   <b>{W(ca)}</b>\n"
        f"  💳 Karta:  <b>{W(cd)}</b>\n"
        f"  💰 Jami:   <b>{W(ca+cd)}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💵  Naqd pulni yangilash",callback_data="set_cash")],
            [InlineKeyboardButton("💳  Karta balansini yangilash",callback_data="set_card")],
            [HOME()],
        ])
    )
    return WAIT

async def cb_set_cash(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["step"] = "set_cash"
    await q.edit_message_text(
        f"💵 <b>NAQD PUL BALANSI</b>\n{DIV}\n\n"
        f"  Hozirgi naqd pulni kiriting (₩):\n  <i>Masalan: 250000</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[BACK("settings")],[HOME()]])
    )
    return WAIT

async def cb_set_card(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["step"] = "set_card"
    await q.edit_message_text(
        f"💳 <b>KARTA BALANSI</b>\n{DIV}\n\n"
        f"  Hozirgi karta balansini kiriting (₩):\n  <i>Masalan: 1500000</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[BACK("settings")],[HOME()]])
    )
    return WAIT

# ─── WALLETS DETAIL ───────────────────────────────────────────────────────────
async def cb_show_cash(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; ca,_ = gwallet(uid)
    with db() as c:
        rows = c.execute("SELECT type,amount,category,note,date FROM tx WHERE uid=? AND wallet='cash' ORDER BY id DESC LIMIT 7",(uid,)).fetchall()
    text = f"💵 <b>NAQD PUL</b>\n{DIV}\n\n  Balans: <b>{W(ca)}</b>\n"
    if rows:
        text += "\n  <b>So'nggi harakatlar:</b>\n"
        for r in rows:
            ic = "🟢" if r[0]=="kirim" else "🔴"
            s = "+" if r[0]=="kirim" else "-"
            text += f"  {ic} {s}{W(r[1])}  {cname(r[2])}  <i>{fd(r[4])}</i>\n"
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("＋ Kirim (naqd)",callback_data="qi_cash_inc"),
         InlineKeyboardButton("－ Chiqim (naqd)",callback_data="qi_cash_exp")],
        [InlineKeyboardButton("✏️  Balansni yangilash",callback_data="set_cash")],
        [HOME()],
    ]))
    return WAIT

async def cb_show_card(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; _,cd = gwallet(uid)
    with db() as c:
        rows = c.execute("SELECT type,amount,category,note,date FROM tx WHERE uid=? AND wallet='card' ORDER BY id DESC LIMIT 7",(uid,)).fetchall()
    text = f"💳 <b>PLASTIK KARTA</b>\n{DIV}\n\n  Balans: <b>{W(cd)}</b>\n"
    if rows:
        text += "\n  <b>So'nggi harakatlar:</b>\n"
        for r in rows:
            ic = "🟢" if r[0]=="kirim" else "🔴"
            s = "+" if r[0]=="kirim" else "-"
            text += f"  {ic} {s}{W(r[1])}  {cname(r[2])}  <i>{fd(r[4])}</i>\n"
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("＋ Kirim (karta)",callback_data="qi_card_inc"),
         InlineKeyboardButton("－ Chiqim (karta)",callback_data="qi_card_exp")],
        [InlineKeyboardButton("✏️  Balansni yangilash",callback_data="set_card")],
        [HOME()],
    ]))
    return WAIT

# ─── CAT KEYBOARD ─────────────────────────────────────────────────────────────
def cat_kb(cats, back_cb):
    items = list(cats.items())
    rows = []
    for i in range(0,len(items),2):
        row = [InlineKeyboardButton(f"{items[i][1][0]} {items[i][1][1]}",callback_data=f"cat_{items[i][0]}")]
        if i+1<len(items): row.append(InlineKeyboardButton(f"{items[i+1][1][0]} {items[i+1][1][1]}",callback_data=f"cat_{items[i+1][0]}"))
        rows.append(row)
    rows.append([BACK(back_cb)])
    return InlineKeyboardMarkup(rows)

# ─── INCOME / EXPENSE ─────────────────────────────────────────────────────────
async def cb_inc_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["dir"] = "kirim"
    ctx.user_data["txdate"] = td()
    await q.edit_message_text(
        f"＋ <b>KIRIM</b>\n{DIV}\n\nKategoriyani tanlang:",
        parse_mode="HTML",reply_markup=cat_kb(IC,"home"))
    return WAIT

async def cb_exp_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["dir"] = "chiqim"
    ctx.user_data["txdate"] = td()
    await q.edit_message_text(
        f"－ <b>CHIQIM</b>\n{DIV}\n\nKategoriyani tanlang:",
        parse_mode="HTML",reply_markup=cat_kb(EC,"home"))
    return WAIT

async def cb_qi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    d = q.data  # qi_cash_inc or qi_card_exp
    wallet = "cash" if "cash" in d else "card"
    direction = "kirim" if "inc" in d else "chiqim"
    ctx.user_data["dir"] = direction
    ctx.user_data["wallet"] = wallet
    ctx.user_data["txdate"] = td()
    cats = IC if direction=="kirim" else EC
    back = "show_cash" if wallet=="cash" else "show_card"
    di = "＋" if direction=="kirim" else "－"
    wi = "💵 Naqd" if wallet=="cash" else "💳 Karta"
    await q.edit_message_text(
        f"{di} {wi}\n{DIV}\n\nKategoriya tanlang:",
        parse_mode="HTML",reply_markup=cat_kb(cats,back))
    return WAIT

async def cb_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    cat = q.data.replace("cat_","")
    ctx.user_data["cat"] = cat
    if "wallet" not in ctx.user_data:
        ca,cd = gwallet(uid)
        di = "＋" if ctx.user_data.get("dir")=="kirim" else "－"
        await q.edit_message_text(
            f"{di} <b>{cname(cat)}</b>\n{DIV}\n\nQaysi hisobdan?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"💵  Naqd  ({W(ca)})",callback_data="wallet_cash"),
                 InlineKeyboardButton(f"💳  Karta  ({W(cd)})",callback_data="wallet_card")],
                [HOME()],
            ]))
    else:
        await ask_amount_q(q, ctx)
    return WAIT

async def cb_wallet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["wallet"] = "cash" if "cash" in q.data else "card"
    await ask_amount_q(q, ctx)
    return WAIT

async def ask_amount_q(q, ctx):
    cat = ctx.user_data.get("cat","other")
    d = ctx.user_data.get("dir","chiqim")
    w = ctx.user_data.get("wallet","cash")
    wi = "💵" if w=="cash" else "💳"
    di = "＋" if d=="kirim" else "－"
    txd = ctx.user_data.get("txdate",td())
    ctx.user_data["step"] = "amount"
    await q.edit_message_text(
        f"{di} <b>{cname(cat)}</b>  {wi}\n"
        f"📅 {fdt(txd)}\n{DIV}\n\n"
        f"  Summani kiriting (₩):\n  <i>Masalan: 50000</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[HOME()]]))

async def cb_save_no_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["note"] = ""
    ctx.user_data["step"] = "idle"
    await do_save(update, ctx)
    return WAIT

async def do_save(update, ctx):
    uid = update.effective_user.id
    amt = ctx.user_data.get("amount",0)
    cat = ctx.user_data.get("cat","other")
    note = ctx.user_data.get("note","")
    d = ctx.user_data.get("dir","chiqim")
    w = ctx.user_data.get("wallet","cash")
    txd = ctx.user_data.get("txdate",td())
    add_tx(uid,d,amt,cat,note,w,txd)
    ca,cd = gwallet(uid)
    wi = "💵 Naqd" if w=="cash" else "💳 Karta"
    di = "＋" if d=="kirim" else "－"
    ri = "🟢" if d=="kirim" else "🔴"
    s = "+" if d=="kirim" else "−"
    text = (
        f"{ri} <b>Saqlandi!</b>\n{DIV}\n\n"
        f"  {di} {cname(cat)}  {wi}\n"
        f"  💰 {s}<b>{W(amt)}</b>\n"
        f"  📅 {fdt(txd)}\n"
        + (f"  📝 {note}\n" if note else "")
        + f"\n{DIV}\n"
        f"  💵 Naqd:  <b>{W(ca)}</b>\n"
        f"  💳 Karta: <b>{W(cd)}</b>\n"
        f"  💰 Jami:  <b>{W(ca+cd)}</b>"
    )
    ctx.user_data.pop("wallet",None)
    ctx.user_data["step"] = "idle"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("＋ Yana kirim",callback_data="inc_menu"),
         InlineKeyboardButton("－ Yana chiqim",callback_data="exp_menu")],
        [InlineKeyboardButton("📅 Kalendar",callback_data="cal_now")],
        [HOME()],
    ])
    q = getattr(update,"callback_query",None)
    if q: await q.edit_message_text(text,parse_mode="HTML",reply_markup=kb)
    else: await update.message.reply_text(text,parse_mode="HTML",reply_markup=kb)

# ─── CALENDAR ─────────────────────────────────────────────────────────────────
async def cb_cal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    data = q.data
    if data=="cal_now":
        now = date.today(); y,m = now.year,now.month
    else:
        parts = data.split("_"); y,m = int(parts[1]),int(parts[2])
    now = date.today()
    cal = calendar.monthcalendar(y,m)
    mn = datetime(y,m,1).strftime("%B %Y")
    pr = date(y,m,1)-timedelta(days=1)
    nx = date(y,m,28)+timedelta(days=4); nx = date(nx.year,nx.month,1)
    rows = [
        [InlineKeyboardButton("◀",callback_data=f"cal_{pr.year}_{pr.month}"),
         InlineKeyboardButton(f"📅 {mn}",callback_data="cal_ignore"),
         InlineKeyboardButton("▶",callback_data=f"cal_{nx.year}_{nx.month}")],
        [InlineKeyboardButton(d,callback_data="cal_ignore") for d in ["Du","Se","Ch","Pa","Ju","Sh","Ya"]],
    ]
    for week in cal:
        row = []
        for d in week:
            if d==0: row.append(InlineKeyboardButton(" ",callback_data="cal_ignore"))
            else:
                lbl = f"[{d}]" if date(y,m,d)==now else str(d)
                row.append(InlineKeyboardButton(lbl,callback_data=f"calday_{y}_{m}_{d}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("📌 Bugun",callback_data=f"calday_{now.year}_{now.month}_{now.day}"),HOME()])
    await q.edit_message_text(
        f"📅 <b>KALENDAR</b>\n{DIV}\n\nKunni tanlang:",
        parse_mode="HTML",reply_markup=InlineKeyboardMarkup(rows))
    return WAIT

async def cb_calday(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    parts = q.data.split("_"); y,m,d = int(parts[1]),int(parts[2]),int(parts[3])
    sel = date(y,m,d)
    ctx.user_data["txdate"] = sel.isoformat()
    with db() as c:
        rows = c.execute("SELECT type,amount,category,note,wallet FROM tx WHERE uid=? AND date=? ORDER BY id DESC",(uid,sel.isoformat())).fetchall()
    ti = sum(r[1] for r in rows if r[0]=="kirim")
    te = sum(r[1] for r in rows if r[0]=="chiqim")
    text = f"📅 <b>{d} {sel.strftime('%B %Y')} — {wday(sel)}</b>\n{DIV}\n\n"
    if rows:
        for r in rows:
            ic = "🟢" if r[0]=="kirim" else "🔴"
            s = "+" if r[0]=="kirim" else "-"
            wi = "💵" if r[4]=="cash" else "💳"
            text += f"  {ic} {s}{W(r[1])} {cname(r[2])} {wi}\n"
            if r[3]: text += f"     📝 {r[3]}\n"
        text += f"\n{DIV}\n  🟢 Kirim: {W(ti)}\n  🔴 Chiqim: {W(te)}\n  💰 Balans: {W(ti-te)}\n"
    else:
        text += "  Bu kunda harakatlar yo'q.\n"
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(f"＋ Kirim ({d}.{m:02d})",callback_data="dated_inc"),
         InlineKeyboardButton(f"－ Chiqim ({d}.{m:02d})",callback_data="dated_exp")],
        [BACK(f"cal_{y}_{m}")],
        [HOME()],
    ]))
    return WAIT

async def cb_dated(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    direction = "kirim" if "inc" in q.data else "chiqim"
    ctx.user_data["dir"] = direction
    cats = IC if direction=="kirim" else EC
    txd = ctx.user_data.get("txdate",td())
    di = "＋" if direction=="kirim" else "－"
    await q.edit_message_text(
        f"{di} <b>{'KIRIM' if direction=='kirim' else 'CHIQIM'}</b>\n📅 {fdt(txd)}\n{DIV}\n\nKategoriya:",
        parse_mode="HTML",reply_markup=cat_kb(cats,"home"))
    return WAIT

# ─── STATS ────────────────────────────────────────────────────────────────────
async def cb_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    ws = (date.today()-timedelta(days=6)).isoformat()
    with db() as c:
        rows = c.execute("SELECT date,type,SUM(amount) FROM tx WHERE uid=? AND date>=? GROUP BY date,type ORDER BY date",(uid,ws)).fetchall()
    days = {}
    for r in rows:
        if r[0] not in days: days[r[0]]={"kirim":0,"chiqim":0}
        days[r[0]][r[1]]=r[2]
    if not days:
        await q.edit_message_text(f"📊 <b>STATISTIKA</b>\n{DIV}\n\n  Ma'lumot yo'q.",
            parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[HOME()]])); return WAIT
    ti = sum(d["kirim"] for d in days.values())
    te = sum(d["chiqim"] for d in days.values())
    mx = max((max(d["kirim"],d["chiqim"]) for d in days.values()),default=1) or 1
    bi = max(days.items(),key=lambda x:x[1]["kirim"])
    bo = max(days.items(),key=lambda x:x[1]["chiqim"])
    text = f"📊 <b>HAFTALIK STATISTIKA</b>\n{DIV}\n\n"
    for d in sorted(days.keys()):
        inc=days[d]["kirim"]; exp=days[d]["chiqim"]
        dt=datetime.strptime(d,"%Y-%m-%d")
        text += f"  <b>{dt.day:02d}.{dt.month:02d} {wday(dt)}</b>\n"
        if inc>0: text += f"    🟢 {'▓'*min(8,max(1,int(inc/mx*8)))} {W(inc)}\n"
        if exp>0: text += f"    🔴 {'▓'*min(8,max(1,int(exp/mx*8)))} {W(exp)}\n"
        if not inc and not exp: text += f"    ○  Harakatlar yo'q\n"
    text += (f"\n{DIV}\n  🟢 Jami kirim:  <b>{W(ti)}</b>\n"
             f"  🔴 Jami chiqim: <b>{W(te)}</b>\n"
             f"  💰 Sof balans:  <b>{W(ti-te)}</b>\n\n"
             f"  🏆 Ko'p kirim: <b>{fd(bi[0])}</b> — {W(bi[1]['kirim'])}\n"
             f"  📉 Ko'p chiqim: <b>{fd(bo[0])}</b> — {W(bo[1]['chiqim'])}")
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 To'liq (bu oy)",callback_data="stats_full")],
        [InlineKeyboardButton("📅 Kalendar",callback_data="cal_now")],
        [HOME()],
    ]))
    return WAIT

async def cb_stats_full(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    now = datetime.now()
    ms = f"{now.year}-{now.month:02d}-01"
    with db() as c:
        ttl={r[0]:r[1] for r in c.execute("SELECT type,SUM(amount) FROM tx WHERE uid=? AND date>=? GROUP BY type",(uid,ms)).fetchall()}
        by_cat=c.execute("SELECT category,type,SUM(amount) as s FROM tx WHERE uid=? AND date>=? GROUP BY category,type ORDER BY s DESC LIMIT 10",(uid,ms)).fetchall()
    inc=ttl.get("kirim",0); exp=ttl.get("chiqim",0)
    sp=int((inc-exp)/inc*100) if inc>0 else 0
    text=(f"📈 <b>{now.strftime('%B %Y')}</b>\n{DIV}\n\n"
          f"  🟢 Kirim:   <b>{W(inc)}</b>\n"
          f"  🔴 Chiqim:  <b>{W(exp)}</b>\n"
          f"  💰 Sof:     <b>{W(inc-exp)}</b>\n"
          f"  💹 Tejash:  <b>{sp}%</b>\n"
          f"  {pbar(sp)}\n\n")
    if by_cat:
        text+="  <b>Kategoriyalar:</b>\n"
        for r in by_cat[:8]:
            base=inc if r[1]=="kirim" else exp
            pct=int(r[2]/base*100) if base>0 else 0
            ic="🟢" if r[1]=="kirim" else "🔴"
            text+=f"  {ic} {cname(r[0])}\n    {'▓'*(pct//10)+'░'*(10-pct//10)} {pct}% {W(r[2])}\n"
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Haftalik",callback_data="stats")],[HOME()]]))
    return WAIT

# ─── ADVICE ───────────────────────────────────────────────────────────────────
async def cb_advice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; ca,cd = gwallet(uid); tot=ca+cd
    now=datetime.now(); ms=f"{now.year}-{now.month:02d}-01"
    dl=(date(now.year,now.month+1 if now.month<12 else 1,1)-timedelta(1)).day-now.day+1
    with db() as c:
        ttl={r[0]:r[1] for r in c.execute("SELECT type,SUM(amount) FROM tx WHERE uid=? AND date>=? GROUP BY type",(uid,ms)).fetchall()}
        top=c.execute("SELECT category,SUM(amount) as s FROM tx WHERE uid=? AND type='chiqim' AND date>=? GROUP BY category ORDER BY s DESC LIMIT 1",(uid,ms)).fetchone()
    inc=ttl.get("kirim",0); exp=ttl.get("chiqim",0)
    rem=max(0,inc-exp); dlim=int(rem/dl) if dl>0 else 0
    sp=int((inc-exp)/inc*100) if inc>0 else 0
    text=f"💡 <b>MOLIYAVIY MASLAHAT</b>\n{DIV}\n\n"
    text+=f"  💰 Balans: <b>{W(tot)}</b>\n  📅 {dl} kun qoldi\n\n"
    if inc>0:
        text+=(f"  <b>📊 50/30/20 Qoidasi:</b>\n"
               f"  🏠 Zaruriyat (50%):  {W(int(inc*.5))}\n"
               f"  🎭 Istak (30%):      {W(int(inc*.3))}\n"
               f"  💎 Jamg'arma (20%):  {W(int(inc*.2))}\n\n"
               f"  {DIV}\n"
               f"  ⏰ Kunlik limit: <b>{W(dlim)}</b>\n"
               f"  💹 Tejash: {sp}%  {pbar(sp)}\n\n")
    if top: text+=f"  ⚠️ Ko'p sarflagan: <b>{cname(top[0])}</b> — {W(top[1])}\n\n"
    if sp<0: text+="  🔴 Chiqim kirimdan oshdi!\n"
    elif sp<10: text+="  🟡 Tejash pastroq. Jamg'arma qiling!\n"
    else: text+="  🟢 Moliyaviy holat yaxshi!\n"
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[HOME()]]))
    return WAIT

# ─── DEBTS ────────────────────────────────────────────────────────────────────
async def cb_debts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    with db() as c:
        rows = c.execute("SELECT id,type,name,amount,paid FROM debts WHERE uid=? ORDER BY id DESC",(uid,)).fetchall()
    active=[r for r in rows if r[4]<r[3]]
    lent=sum(r[3]-r[4] for r in active if r[1]=="berilgan")
    borr=sum(r[3]-r[4] for r in active if r[1]=="olingan")
    text=f"🤝 <b>QARZLAR</b>\n{DIV}\n\n  🔴 Men berdim: <b>{W(lent)}</b>\n  🟢 Men oldim: <b>{W(borr)}</b>\n"
    if active:
        text+="\n  <b>Aktiv:</b>\n"
        for r in active:
            ic="🔴" if r[1]=="berilgan" else "🟢"
            pct=int(r[4]/r[3]*100) if r[3]>0 else 0
            text+=f"  {ic} <b>{r[2]}</b> — {W(r[3]-r[4])} qoldi\n    {pbar(pct,6)} {pct}%\n"
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴  Men berdim",callback_data="debt_lent"),
         InlineKeyboardButton("🟢  Men oldim",callback_data="debt_borrow")],
        [InlineKeyboardButton("💳  To'lov kiritish",callback_data="debt_paylist")],
        [HOME()],
    ]))
    return WAIT

async def cb_debt_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dtype="berilgan" if "lent" in q.data else "olingan"
    ctx.user_data["debt_type"]=dtype; ctx.user_data["step"]="debt_name"
    label="berdim" if dtype=="berilgan" else "oldim"
    ic="🔴" if dtype=="berilgan" else "🟢"
    await q.edit_message_text(
        f"{ic} <b>Men {label}</b>\n{DIV}\n\nKimga/Kimdan? Ism kiriting:",
        parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[BACK("debts")],[HOME()]]))
    return WAIT

async def cb_debt_paylist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    with db() as c:
        rows = c.execute("SELECT id,type,name,amount,paid FROM debts WHERE uid=? AND paid<amount",(uid,)).fetchall()
    if not rows:
        await q.edit_message_text("✅ To'lanadigan qarz yo'q!",reply_markup=InlineKeyboardMarkup([[BACK("debts")]])); return WAIT
    btns=[[InlineKeyboardButton(f"{'🔴' if r[1]=='berilgan' else '🟢'} {r[2]} — {W(r[3]-r[4])}",callback_data=f"dpay_{r[0]}")] for r in rows]
    btns.append([BACK("debts")])
    await q.edit_message_text("💳 <b>Qaysi qarzga to'lov?</b>",parse_mode="HTML",reply_markup=InlineKeyboardMarkup(btns))
    return WAIT

async def cb_debt_pay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    did=int(q.data.split("_")[1]); ctx.user_data["pay_did"]=did; ctx.user_data["step"]="pay_amt"
    with db() as c:
        r=c.execute("SELECT name,amount,paid,type FROM debts WHERE id=?",(did,)).fetchone()
    ic="🔴" if r[3]=="berilgan" else "🟢"
    await q.edit_message_text(
        f"{ic} <b>{r[0]}</b>\n  Jami: {W(r[1])}\n  To'langan: {W(r[2])}\n  <b>Qoldi: {W(r[1]-r[2])}</b>\n\nTo'lov summasi:",
        parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[BACK("debt_paylist")],[HOME()]]))
    return WAIT

# ─── SAVINGS ──────────────────────────────────────────────────────────────────
async def cb_savings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    with db() as c:
        rows=c.execute("SELECT id,name,goal,current,daily,icon FROM savings WHERE uid=? ORDER BY id DESC",(uid,)).fetchall()
    if not rows:
        await q.edit_message_text(
            f"🏦 <b>JAMG'ARMA</b>\n{DIV}\n\n  Hali maqsad yo'q! 🎯",
            parse_mode="HTML",reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕  Yangi maqsad",callback_data="sv_new")],[HOME()]])); return WAIT
    text=f"🏦 <b>JAMG'ARMA MAQSADLARI</b>\n{DIV}\n\n"
    text+=f"  Jami: {W(sum(r[3] for r in rows))} / {W(sum(r[2] for r in rows))}\n\n"
    for r in rows:
        pct=int(r[3]/r[2]*100) if r[2]>0 else 0
        rem=r[2]-r[3]; days=int(rem/r[4]) if r[4]>0 and rem>0 else 0
        dd=(date.today()+timedelta(days=days)).strftime("%d.%m.%Y") if days>0 else "✅"
        text+=f"  {r[5]} <b>{r[1]}</b>\n  {pbar(pct)} {pct}%\n  {W(r[3])} / {W(r[2])}\n"
        if r[4]>0 and rem>0: text+=f"  ⏰ Kuniga {W(r[4])} → {dd}\n"
        text+="\n"
    add_btns=[[InlineKeyboardButton(f"{r[5]} {r[1]}",callback_data=f"sv_add_{r[0]}")] for r in rows if r[3]<r[2]]
    all_rows=add_btns+[[InlineKeyboardButton("➕  Yangi maqsad",callback_data="sv_new")],[HOME()]]
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(all_rows))
    return WAIT

ICONS=["🎯","🏠","✈️","🚗","💻","📱","🎓","💍","🌍","💰","🎸","⚽"]

async def cb_sv_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    rows=[]
    for i in range(0,len(ICONS),4):
        rows.append([InlineKeyboardButton(ic,callback_data=f"svi_{ic}") for ic in ICONS[i:i+4]])
    rows.append([BACK("savings")])
    await q.edit_message_text(f"🏦 <b>YANGI MAQSAD</b>\n{DIV}\n\nBelgi tanlang:",parse_mode="HTML",reply_markup=InlineKeyboardMarkup(rows))
    return WAIT

async def cb_sv_icon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["sv_icon"]=q.data.replace("svi_",""); ctx.user_data["step"]="sv_name"
    await q.edit_message_text(
        f"{ctx.user_data['sv_icon']} <b>Maqsad nomi:</b>",
        parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[BACK("sv_new")],[HOME()]]))
    return WAIT

async def cb_sv_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    sv_id=int(q.data.split("_")[2]); ctx.user_data["sv_id"]=sv_id; ctx.user_data["step"]="sv_add"
    with db() as c:
        r=c.execute("SELECT name,goal,current,daily,icon FROM savings WHERE id=?",(sv_id,)).fetchone()
    rem=r[1]-r[2]; pct=int(r[2]/r[1]*100) if r[1]>0 else 0
    days=int(rem/r[3]) if r[3]>0 and rem>0 else 0
    await q.edit_message_text(
        f"{r[4]} <b>{r[0]}</b>\n{DIV}\n  {pbar(pct)} {pct}%\n  {W(r[2])}/{W(r[1])}\n  Qoldi: {W(rem)}"+(f" (~{days} kun)" if days>0 else "")+"\n\nQo'shish summasi (₩):",
        parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[BACK("savings")],[HOME()]]))
    return WAIT

# ─── TEXT INPUT ROUTER ────────────────────────────────────────────────────────
async def text_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    step = ctx.user_data.get("step","idle")
    txt = update.message.text.strip()

    # Balance
    if step in ("set_cash","set_card"):
        try: amt=float(txt.replace(",","").replace(" ",""))
        except:
            await update.message.reply_text("❌ Faqat raqam kiriting!\n<i>Masalan: 250000</i>",parse_mode="HTML"); return WAIT
        if step=="set_cash": swallet(uid,cash=amt); icon,label="💵","Naqd pul"
        else: swallet(uid,card=amt); icon,label="💳","Plastik karta"
        ctx.user_data["step"]="idle"
        await update.message.reply_text(f"✅ {icon} <b>{label}</b> yangilandi!\n  <b>{W(amt)}</b>",parse_mode="HTML")
        await send_home(uid,update,ctx); return WAIT

    # TX amount
    if step=="amount":
        try: amt=float(txt.replace(",","").replace(" ",""))
        except:
            await update.message.reply_text("❌ To'g'ri summa kiriting!\n<i>Masalan: 50000</i>",parse_mode="HTML"); return WAIT
        if amt<=0:
            await update.message.reply_text("❌ Summa 0 dan katta bo'lishi kerak!"); return WAIT
        ctx.user_data["amount"]=amt; ctx.user_data["step"]="note"
        cat=ctx.user_data.get("cat","other"); d=ctx.user_data.get("dir","chiqim")
        w=ctx.user_data.get("wallet","cash"); wi="💵" if w=="cash" else "💳"
        di="＋" if d=="kirim" else "－"
        await update.message.reply_text(
            f"{di} <b>{cname(cat)}</b>  {wi}\n💰 <b>{W(amt)}</b>\n\nIzoh yozing:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭  Izohsiz saqlash",callback_data="save_no_note")],[HOME()]]))
        return WAIT

    # TX note
    if step=="note":
        ctx.user_data["note"]=txt; ctx.user_data["step"]="idle"
        await do_save(update,ctx); return WAIT

    # Debt name
    if step=="debt_name":
        ctx.user_data["debt_name"]=txt; ctx.user_data["step"]="debt_amount"
        dtype=ctx.user_data.get("debt_type","berilgan")
        ic="🔴" if dtype=="berilgan" else "🟢"; label="berdim" if dtype=="berilgan" else "oldim"
        await update.message.reply_text(f"{ic} Men {label}: <b>{txt}</b>\n\nSumma kiriting (₩):",parse_mode="HTML"); return WAIT

    # Debt amount
    if step=="debt_amount":
        try: amt=float(txt.replace(",",""))
        except:
            await update.message.reply_text("❌ To'g'ri summa kiriting!"); return WAIT
        dtype=ctx.user_data.get("debt_type","berilgan"); name=ctx.user_data.get("debt_name","")
        with db() as c:
            c.execute("INSERT INTO debts(uid,type,name,amount,paid,note,date) VALUES(?,?,?,?,0,'',?)",(uid,dtype,name,amt,td()))
        ic="🔴" if dtype=="berilgan" else "🟢"; label="berdim" if dtype=="berilgan" else "oldim"
        ctx.user_data["step"]="idle"
        await update.message.reply_text(
            f"✅ {ic} Men {label}: <b>{name}</b>\n{W(amt)} saqlandi!",parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤝 Qarzlar",callback_data="debts")],[HOME()]])); return WAIT

    # Pay amount
    if step=="pay_amt":
        try: amt=float(txt.replace(",",""))
        except:
            await update.message.reply_text("❌ To'g'ri summa kiriting!"); return WAIT
        did=ctx.user_data.get("pay_did")
        with db() as c:
            r=c.execute("SELECT name,amount,paid FROM debts WHERE id=?",(did,)).fetchone()
            np=min(r[2]+amt,r[1]); c.execute("UPDATE debts SET paid=? WHERE id=?",(np,did))
        done=np>=r[1]; pct=int(np/r[1]*100) if r[1]>0 else 0
        ctx.user_data["step"]="idle"
        await update.message.reply_text(
            f"✅ <b>{r[0]}</b>\n+{W(amt)} to'landi\n{pbar(pct)} {pct}%\n"
            +("🎉 <b>Qarz yopildi!</b>" if done else f"Qoldi: {W(r[1]-np)}"),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤝 Qarzlar",callback_data="debts")],[HOME()]])); return WAIT

    # Saving name
    if step=="sv_name":
        ctx.user_data["sv_name"]=txt; ctx.user_data["step"]="sv_goal"
        icon=ctx.user_data.get("sv_icon","🎯")
        await update.message.reply_text(f"{icon} <b>{txt}</b>\n\nMaqsad summasi (₩):",parse_mode="HTML"); return WAIT

    # Saving goal
    if step=="sv_goal":
        try: goal=float(txt.replace(",",""))
        except:
            await update.message.reply_text("❌ To'g'ri summa kiriting!"); return WAIT
        ctx.user_data["sv_goal"]=goal; ctx.user_data["step"]="sv_daily"
        await update.message.reply_text(
            f"📅 Kuniga qancha yig'aysiz? (₩)\n\n<i>Masalan: 10000\nQachon yetishini hisoblaymiz</i>",parse_mode="HTML"); return WAIT

    # Saving daily
    if step=="sv_daily":
        try: daily=float(txt.replace(",",""))
        except:
            await update.message.reply_text("❌ To'g'ri summa kiriting!"); return WAIT
        goal=ctx.user_data.get("sv_goal",0); name=ctx.user_data.get("sv_name","")
        icon=ctx.user_data.get("sv_icon","🎯")
        days=int(goal/daily) if daily>0 else 0
        months=days//30
        done_date=(date.today()+timedelta(days=days)).strftime("%d.%m.%Y")
        tstr=f"{months} oy {days%30} kun" if months>0 else f"{days} kun"
        with db() as c:
            c.execute("INSERT INTO savings(uid,name,goal,current,daily,icon) VALUES(?,?,?,0,?,?)",(uid,name,goal,daily,icon))
        ctx.user_data["step"]="idle"
        await update.message.reply_text(
            f"✅ <b>Maqsad qo'yildi!</b>\n{DIV}\n\n"
            f"  {icon} <b>{name}</b>\n  🎯 {W(goal)}\n  📅 Kuniga {W(daily)}\n  ⏰ {tstr} ({done_date}) da!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏦 Jamg'arma",callback_data="savings")],[HOME()]])); return WAIT

    # Saving add amount
    if step=="sv_add":
        try: amt=float(txt.replace(",",""))
        except:
            await update.message.reply_text("❌ To'g'ri summa kiriting!"); return WAIT
        sv_id=ctx.user_data.get("sv_id")
        with db() as c:
            r=c.execute("SELECT name,goal,current,daily,icon FROM savings WHERE id=?",(sv_id,)).fetchone()
            nc=min(r[2]+amt,r[1]); c.execute("UPDATE savings SET current=? WHERE id=?",(nc,sv_id))
        pct=int(nc/r[1]*100) if r[1]>0 else 0; rem=r[1]-nc
        days=int(rem/r[3]) if r[3]>0 and rem>0 else 0; done=nc>=r[1]
        ctx.user_data["step"]="idle"
        await update.message.reply_text(
            f"✅ {r[4]} <b>{r[0]}</b>\n+{W(amt)} qo'shildi!\n{pbar(pct)} {pct}%\n{W(nc)}/{W(r[1])}\n"
            +("🎉 <b>Maqsadga yetdingiz!</b>" if done else f"Qoldi: {W(rem)}"+(f" (~{days} kun)" if days>0 else "")),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏦 Jamg'arma",callback_data="savings")],[HOME()]])); return WAIT

    # Default
    await update.message.reply_text("🏠",reply_markup=InlineKeyboardMarkup([[HOME()]])); return WAIT

async def cb_ignore(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return WAIT

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start",cmd_start)],
        states={
            WAIT: [
                # Navigation
                CallbackQueryHandler(cb_home,         pattern="^home$"),
                CallbackQueryHandler(cb_settings,     pattern="^settings$"),
                CallbackQueryHandler(cb_set_cash,     pattern="^set_cash$"),
                CallbackQueryHandler(cb_set_card,     pattern="^set_card$"),
                CallbackQueryHandler(cb_show_cash,    pattern="^show_cash$"),
                CallbackQueryHandler(cb_show_card,    pattern="^show_card$"),
                # Transactions
                CallbackQueryHandler(cb_inc_menu,     pattern="^inc_menu$"),
                CallbackQueryHandler(cb_exp_menu,     pattern="^exp_menu$"),
                CallbackQueryHandler(cb_qi,           pattern="^qi_"),
                CallbackQueryHandler(cb_cat,          pattern="^cat_"),
                CallbackQueryHandler(cb_wallet,       pattern="^wallet_"),
                CallbackQueryHandler(cb_save_no_note, pattern="^save_no_note$"),
                # Calendar
                CallbackQueryHandler(cb_cal,          pattern="^cal_(now|\\d+_\\d+)$"),
                CallbackQueryHandler(cb_calday,       pattern="^calday_"),
                CallbackQueryHandler(cb_dated,        pattern="^dated_"),
                CallbackQueryHandler(cb_ignore,       pattern="^cal_ignore$"),
                # Stats
                CallbackQueryHandler(cb_stats,        pattern="^stats$"),
                CallbackQueryHandler(cb_stats_full,   pattern="^stats_full$"),
                # Advice
                CallbackQueryHandler(cb_advice,       pattern="^advice$"),
                # Debts
                CallbackQueryHandler(cb_debts,        pattern="^debts$"),
                CallbackQueryHandler(cb_debt_add,     pattern="^debt_(lent|borrow)$"),
                CallbackQueryHandler(cb_debt_paylist, pattern="^debt_paylist$"),
                CallbackQueryHandler(cb_debt_pay,     pattern="^dpay_\\d+$"),
                # Savings
                CallbackQueryHandler(cb_savings,      pattern="^savings$"),
                CallbackQueryHandler(cb_sv_new,       pattern="^sv_new$"),
                CallbackQueryHandler(cb_sv_icon,      pattern="^svi_"),
                CallbackQueryHandler(cb_sv_add,       pattern="^sv_add_\\d+$"),
                # Text
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_router),
            ],
        },
        fallbacks=[CommandHandler("start",cmd_start)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    print("✅ Moliya Pro Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
