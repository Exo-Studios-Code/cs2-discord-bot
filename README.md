# 🎮 CS2 Discord Bot

Osobní CS2 asistent pro Discord. Sleduje tvoje statistiky, analyzuje zápasy pomocí **Google Gemini AI** a posílá reporty přímo do DM.

---

## ✨ Funkce

| Funkce | Popis |
|--------|-------|
| 📊 **Statistiky** | Kompletní CS2 stats s interaktivními tlačítky (mapy, zbraně, přehled) |
| 🎮 **Sledování zápasů** | Automatická detekce nových zápasů každých 15 minut |
| 🤖 **AI Analýza** | Google Gemini analyzuje výkon, silné/slabé stránky, dává tipy |
| 📬 **DM Notifikace** | Po každém zápase dostaneš zprávu s analýzou přímo do DM |
| 📈 **Pokrok** | Sledování vývoje statistik v čase, ASCII grafy |
| 📅 **Týdenní report** | Každou neděli automatický souhrn do DM |
| 🎯 **Cíle** | Nastav si K/D, win rate nebo HS rate cíle s progress barem |
| 🏆 **Odhadovaný rank** | Výpočet ratingu a odhad ranku na základě dat |

---

## 🚀 Instalace

### 1. Požadavky
- Python 3.10+
- Discord Bot Token
- Steam Web API Key
- Google AI API Key *(volitelné, pro AI funkce)*

### 2. Klonuj / stáhni projekt
```bash
git clone https://github.com/tvuj-repo/cs2-discord-bot
cd cs2-discord-bot
```

### 3. Nainstaluj závislosti
```bash
pip install -r requirements.txt
```

### 4. Nakonfiguruj .env
```bash
cp .env.example .env
```
Otevři `.env` a vyplň:
```env
DISCORD_TOKEN=tvuj_token
STEAM_API_KEY=tvuj_steam_klic
GOOGLE_AI_KEY=tvuj_gemini_klic   # volitelné
```

### 5. Spusť bota
```bash
python bot.py
```

---

## 🔑 Jak získat klíče

### Discord Bot Token
1. Jdi na https://discord.com/developers/applications
2. Vytvoř novou aplikaci → Bot → Reset Token
3. Povol: **Message Content Intent**, **Server Members Intent**, **DM intents**
4. Pozvánka: `https://discord.com/oauth2/authorize?client_id=TVOJE_ID&scope=bot+applications.commands&permissions=2147485696`

### Steam Web API Key
1. Přihlás se na https://steamcommunity.com/dev/apikey
2. Vyplň doménové jméno (např. `localhost`)
3. Zkopíruj vygenerovaný klíč

### Google AI (Gemini) Key — ZDARMA
1. Jdi na https://aistudio.google.com/app/apikey
2. Klikni "Create API Key"
3. Zkopíruj klíč

### Steam Match Auth Token (pro každého uživatele)
1. Otevři CS2
2. Hlavní menu → Nastavení (ozubené kolo) → Sdílení zápasů
3. Zkopíruj **Authentication Token**

---

## 📋 Příkazy

### ⚙️ Nastavení
| Příkaz | Popis |
|--------|-------|
| `/setup` | Zaregistruj Steam účet (Steam ID + auth token + sharecode) |
| `/profile` | Zobraz propojený profil |
| `/notifications` | Zapni/vypni DM notifikace |
| `/updatecode` | Aktualizuj poslední sharecode |
| `/unregister` | Smaž všechna data |

### 📊 Statistiky
| Příkaz | Popis |
|--------|-------|
| `/stats` | Kompletní stats s interaktivními tlačítky |
| `/quickstats` | Rychlý přehled + AI tip |
| `/compare` | Porovnání s průměrem CS2 komunity |

### 🎮 Zápasy
| Příkaz | Popis |
|--------|-------|
| `/match [sharecode]` | Detail zápasu + AI analýza |
| `/history [count]` | Historie zápasů se stránkováním |
| `/forcepoll` | Ručně zkontroluj nové zápasy |

### 🤖 AI Analýza
| Příkaz | Popis |
|--------|-------|
| `/analyze` | Kompletní AI analýza statistik |
| `/improve <oblast>` | Tipy pro konkrétní oblast (aim, mapy, economy...) |

### 📈 Pokrok
| Příkaz | Popis |
|--------|-------|
| `/progress` | Vývoj statistik v čase |
| `/snapshot` | Ulož aktuální stats jako referenční bod |
| `/weeklyreport` | Pošli si týdenní report okamžitě |
| `/goals` | Nastav a sleduj herní cíle |

### 🔧 Ostatní
| Příkaz | Popis |
|--------|-------|
| `/help` | Interaktivní nápověda |
| `/ping` | Odezva bota |
| `/status` | Stav a statistiky bota |

---

## 📁 Struktura projektu

```
cs2-discord-bot/
├── bot.py                  # Hlavní soubor, spouštění bota
├── requirements.txt        # Python závislosti
├── .env.example            # Šablona konfigurace
├── cs2bot.db               # SQLite databáze (auto-vytvořena)
├── bot.log                 # Log soubor (auto-vytvořen)
├── cogs/
│   ├── setup.py            # Registrace, profil, notifikace
│   ├── stats.py            # Statistiky, mapy, zbraně
│   ├── matches.py          # Zápasy, polling, DM notifikace
│   ├── ai_analysis.py      # AI analýza, tipy, zlepšení
│   ├── progress.py         # Pokrok, týdenní report, cíle
│   └── help.py             # Nápověda, ping, status
└── utils/
    ├── database.py         # SQLite databáze (aiosqlite)
    ├── cs2_api.py          # Steam API + sharecode decoder
    ├── ai_analyzer.py      # Google Gemini integrace
    └── embeds.py           # Discord embed builder
```

---

## 🗄️ Databáze

Bot používá **SQLite** (soubor `cs2bot.db`). Ukládá:
- Uživatelské profily (Steam ID, tokeny, preference)
- Historii zápasů (stats, sharecodes, AI analýzy)
- Snímky statistik pro sledování pokroku
- Log odeslaných notifikací

---

## ⚠️ Důležité poznámky

- Steam profil musí být **veřejný** (profil + herní detaily)
- Match Auth Token je **citlivý** — neposkytuj ho nikomu
- Bot kontroluje nové zápasy **každých 15 minut**
- Google AI (Gemini) má **bezplatný tier** — stačí pro osobní použití
- Sharecode tracking funguje přes **Steam Web API** — závisí na Valve serverech

---

## 🤝 Přispění & Podpora

Našel jsi chybu nebo chceš novou funkci? Otevři Issue nebo Pull Request!

---

*Vytvořeno s ❤️ pro českou CS2 komunitu*
