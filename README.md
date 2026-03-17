## DungeonKeeper – Discord DM Report / ModMail Bot

A Discord bot that lets users privately report rule violations via DM, then forwards the report (and attachments) to a staff channel with a case thread and staff action buttons.

## Features

- **DM-based reporting**: users DM the bot, tap **Proceed**, then send their report message (with optional attachments).
- **Case creation**: bot posts an embed to a configured staff channel, pings staff roles, and opens a **thread per case**.
- **Staff controls (buttons/modals)**:
  - **Reply** to the reporter (DM)
  - **Warn** a user (DM them a warning)
  - **Mute** (timeout) a member for N minutes
  - **Ban** a user
  - **Close Case** (DM reporter with action taken)
  - **Blacklist Reporter** (blocks future reports from that reporter)

## Requirements

- Python **3.10+** (3.11+ recommended)
- `discord.py` **2.x**
- Supabase project (Postgres) + API keys

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create the Supabase tables:

- Open **Supabase → SQL Editor**
- Paste/run `schema.sql`

3. Create environment variables:

- **`DISCORD_TOKEN`**: your bot token
- **`STAFF_CHANNEL_ID`**: the channel ID where cases are posted (e.g., `1234567890`)
- **`STAFF_ROLE_IDS`**: comma-separated role IDs to ping + treat as staff (e.g., `111,222,333`)
- **`SUPABASE_URL`**: Supabase Project URL
- **`SUPABASE_SERVICE_ROLE_KEY`**: Supabase service role key (keep secret; server-only)

### Example (PowerShell)

```powershell
$env:DISCORD_TOKEN="YOUR_TOKEN_HERE"
$env:STAFF_CHANNEL_ID="123456789012345678"
$env:STAFF_ROLE_IDS="111111111111111111,222222222222222222"
$env:SUPABASE_URL="https://YOUR_PROJECT.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY="YOUR_SERVICE_ROLE_KEY"
python .\bot.py
```

## Discord configuration

### Privileged intents (Developer Portal)

This bot enables:

- **Message Content Intent** (needed to read DM content)
- **Server Members Intent** (used for role checks and timeouts)

Enable them in the Discord Developer Portal for your bot.

### Bot permissions (recommended)

- **Read Messages / View Channels**
- **Send Messages**
- **Embed Links**
- **Attach Files**
- **Create Public Threads** (or the thread type you use)
- **Send Messages in Threads**
- **Moderate Members** (timeout/mute)
- **Ban Members** (if you want the Ban modal to work)

## How it works (user flow)

1. A user DMs the bot.
2. The bot responds with an embed + buttons: **Proceed** / **Cancel**.
3. If the user taps **Proceed**, the next DM they send becomes the report.
4. The bot posts the case to the staff channel, creates a thread, and pings staff roles.

## Staff actions

Staff can use the buttons on the case message:

- **Reply**: sends a DM to the reporter with a case reply embed.
- **Warn**: DMs a specified user with a warning embed.
- **Mute**: applies a Discord timeout to the member for the given minutes.
- **Ban**: bans the specified user.
- **Close Case**: DMs the reporter the action taken.
- **Blacklist Reporter**: blocks the reporter from submitting new cases.

## Notes / limitations

- **Buttons after restart**: buttons are persistent and load cases by staff message ID from Supabase.
- **Thread permissions**: thread creation requires permissions in the staff channel.

## Troubleshooting

- **Bot doesn’t respond in DMs**: ensure message content intent is enabled and the bot is online.
- **No staff ping / no message in channel**: check `STAFF_CHANNEL_ID`, role IDs, and bot permissions.
- **Mute fails**: the bot needs **Moderate Members** and the target must be a member in the guild.
- **Ban fails**: the bot needs **Ban Members** and role hierarchy must allow it.

## License

See the header in `bot.py` for licensing/usage terms.
