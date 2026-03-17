## DungeonKeeper – Discord Report Bot (SQLite)

A Discord bot that stores moderation reports in a local **SQLite** database (`bot.db`) using simple commands.

## Features

- **Create reports** with a command and store them in SQLite
- **View reports** in Discord
- **Delete reports** by ID

## Requirements

- Python **3.10+** (3.11+ recommended)
- `discord.py` **2.x**

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create environment variables:

- **`DISCORD_TOKEN`**: your bot token

### Example (PowerShell)

```powershell
$env:DISCORD_TOKEN="YOUR_TOKEN_HERE"
python .\bot.py
```

## Discord configuration

### Privileged intents (Developer Portal)

This bot enables:

- **Message Content Intent** (needed to read DM content)

Enable them in the Discord Developer Portal for your bot.

### Bot permissions (recommended)

- **Read Messages / View Channels**
- **Send Messages**
- **Embed Links**
- **Attach Files**

## Commands

- **`!report <user> <reason>`**: Save a report in SQLite.
- **`!reports`**: List saved reports (shows newest first).
- **`!delreport <id>`**: Delete a report by ID.

## Notes / limitations

- **SQLite file**: `bot.db` is created automatically on first start.
- **Render warning**: on free/ephemeral instances, `bot.db` may be lost after redeploy/restart unless you attach a persistent disk.

## Troubleshooting

- **Bot doesn’t respond in DMs**: ensure message content intent is enabled and the bot is online.
- **Commands don’t work**: ensure Message Content Intent is enabled and you’re using the correct prefix `!`.

## License

See the header in `bot.py` for licensing/usage terms.
