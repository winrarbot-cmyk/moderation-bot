# CBA Moderation Bot

A production-ready, cog-based Discord moderation bot for the Curveball Association.  
Built with **discord.py 2.x**, **Motor** (async MongoDB), and **Python 3.12+**.

---

## Features

- **Warning system** with fuzzy reason matching, automatic punishment escalation, and expiry
- **Case management** with notes, status tracking, and evidence attachment
- **Evidence system** – links, file uploads, YouTube / Medal / Twitch / Streamable
- **Queue ban system** – channel permission overrides (no role creation)
- **General timeout** – Discord's native timeout system (no role creation)
- **Player reports** via slash command `/report` with staff review buttons
- **Appeals** with staff verdict and DM notifications
- **Escalation alerts** to `#moderation-alerts`
- **Background task** – automatic ban expiry and permission restoration every 5 minutes

---

## Project Structure

```
cba_modbot/
├── bot.py                  # Entry point
├── requirements.txt
├── .env.example
├── COMMANDS.md             # Full command reference
├── config/
│   ├── __init__.py
│   └── settings.py         # All configuration
├── utils/
│   ├── __init__.py
│   ├── database.py         # Motor/MongoDB layer
│   └── helpers.py          # Permissions, embeds, fuzzy matching, duration parsing
└── cogs/
    ├── __init__.py
    ├── moderation.py       # Background expiry task
    ├── warnings.py         # !warn, !warns
    ├── cases.py            # !case, !case note, !history
    ├── evidence.py         # !evidence add/delete
    ├── queue_punishments.py # !queueban, !unqueueban, !gentimeout
    ├── reports.py          # /report, !reportreview
    ├── appeals.py          # !appeal, !appealreview
    └── escalation.py       # Escalation alert helpers
```

---

## Setup

### 1. Requirements

```bash
python --version   # 3.12+
pip install -r requirements.txt
```

### 2. MongoDB

Start a local MongoDB instance, or use [MongoDB Atlas](https://www.mongodb.com/atlas).

```bash
# Local (Docker)
docker run -d -p 27017:27017 --name mongo mongo:7
```

### 3. Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```env
DISCORD_TOKEN=your_bot_token_here
COMMAND_PREFIX=!
GUILD_ID=your_guild_id_here
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=cba_modbot
```

### 4. Discord Bot Setup

In the [Discord Developer Portal](https://discord.com/developers/applications):

1. Create a new application → Bot
2. Enable **Privileged Intents**: `Server Members` and `Message Content`
3. Copy the token to `.env`
4. Invite with scopes: `bot` + `applications.commands`
5. Required permissions:
   - Manage Channels (for queue permission overrides)
   - Moderate Members (for timeouts)
   - Kick Members / Ban Members
   - Send Messages, Embed Links, Attach Files
   - Read Message History

### 5. Discord Channel Setup

Create the following channels in your server (names are configurable in `config/settings.py`):

| Channel              | Purpose                              |
|----------------------|--------------------------------------|
| `#support-reports`   | Report embeds posted here            |
| `#appeals`           | Appeal embeds posted here            |
| `#moderation-alerts` | Escalation pings posted here         |
| `#queue`             | Queue channel (access removed on ban)|
| `#matchmaking`       | Queue channel                        |
| `#find-team`         | Queue channel                        |
| `#scrims`            | Queue channel                        |

### 6. Run

```bash
python bot.py
```

---

## Configuration

All settings are in `config/settings.py`. Key sections:

- `staff_roles` – Role names with staff access
- `channels` – Channel names for reports, appeals, alerts, queue
- `escalation` – Full punishment escalation tables
- `community_escalation` – Community warning threshold actions
- `expiry_days` – Warning expiry periods
- `alert_rules` – Escalation alert triggers

---

## See Also

- [`COMMANDS.md`](COMMANDS.md) – Full command reference with examples
