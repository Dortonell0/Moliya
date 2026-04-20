# MOLIYA PRO

Shaxsiy moliya dasturi — vanilla HTML/CSS/JS, backend kerak emas.

## Xususiyatlari

- 3 qatlam ma'lumot saqlash (localStorage + backup + IndexedDB)
- Kirim/chiqim, hamyonlar (Naqd, Karta), jamg'armalar, qarzlar
- Kunlik va oylik HTML hisobotlar
- Kategoriya boshqaruvi
- Qidiruv va filtr
- JSON eksport/import
- Telegram WebApp qo'llab-quvvatlovi
- To'liq qorong'u mavzu (dark theme)
- Tilda: O'zbek, valyuta: ₩ (KRW)

## GitHub Pages ga deploy qilish

1. GitHub da yangi repo yarating (masalan `Moliya`)
2. `index.html` faylini repo ichiga yuklang
3. Repo **Settings → Pages** ga kiring
4. **Source**: `Deploy from a branch` → `main` → `/ (root)` → **Save**
5. 1-2 daqiqadan so'ng havola tayyor bo'ladi:
   `https://SIZNING-USERNAME.github.io/Moliya/`

## Telegram WebApp sifatida

1. [@BotFather](https://t.me/BotFather) dan bot yarating
2. `/newapp` buyrug'i bilan Mini App qo'shing
3. URL sifatida GitHub Pages havolangizni kiriting

## Fayl tuzilishi

```
Moliya/
└── index.html    # Butun dastur bitta faylda
```

Boshqa bog'liqliklar yo'q — build kerak emas.
