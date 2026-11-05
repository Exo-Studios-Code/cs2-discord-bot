# CS2 Discord Bot

A personal CS2 assistant for Discord. It tracks your stats, detects new matches and sends Gemini-powered analysis straight to your DMs.

## Features

- Full CS2 statistics with interactive buttons (overview, maps, weapons)
- Automatic new-match detection every 15 minutes
- AI analysis of performance, strengths and weaknesses via Google Gemini
- DM notifications after every match
- Progress tracking with snapshots and ASCII charts
- Automatic weekly report every Sunday
- Custom goals (K/D, win rate, HS rate) with progress bars
- Estimated rank based on your stats
- Comparison with the average CS2 player

## Tech Stack

- Python 3.10+
- discord.py
- aiosqlite (SQLite)
- aiohttp
- Google Gemini (`google-genai`)
- python-dotenv

## Getting Started

### Prerequisites

- Python 3.10+
- Discord bot token
- Steam Web API key
- Optional: Google AI (Gemini), Leetify and FACEIT API keys

### Installation

```bash
git clone https://github.com/<user>/cs2-discord-bot.git
cd cs2-discord-bot
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

```env
# Required
DISCORD_TOKEN=your_discord_bot_token
STEAM_API_KEY=your_steam_api_key

# Recommended
GOOGLE_AI_KEY=your_gemini_api_key
LEETIFY_API_KEY=
FACEIT_API_KEY=
```

Enable **Message Content Intent** and **Server Members Intent** in the Discord Developer Portal.

### Run

```bash
python bot.py
```

## Commands

| Command | Description |
|---------|-------------|
| `/setup` | Link your Steam account (Steam ID, auth token, sharecode) |
| `/profile` | Show your linked profile |
| `/stats` | Full stats with interactive buttons |
| `/quickstats` | Quick overview with an AI tip |
| `/compare` | Compare yourself with the community average |
| `/match` | Match detail with AI analysis |
| `/history` | Paginated match history |
| `/analyze` | Full AI analysis |
| `/improve` | Tips for a specific area (aim, economy, utility...) |
| `/progress` | Stats development over time |
| `/snapshot` | Save a reference point |
| `/goals` | Set and track goals |
| `/weeklyreport` | Send the weekly report now |
| `/notifications` | Toggle DM notifications |
| `/unregister` | Delete all your data |
