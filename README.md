# CBA Moderation Bot

A Discord.py 2.x moderation bot for competitive league servers. Handles warnings, queue bans, Discord timeouts, server bans, reports, appeals, evidence, and automated escalation — all backed by MongoDB.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Project Structure](#project-structure)
- [Fresh Setup](#fresh-setup)
- [Adding to an Existing Bot](#adding-to-an-existing-bot)
- [Configuration](#configuration)
- [Getting IDs from Discord](#getting-ids-from-discord)
- [Environment Variables](#environment-variables)
- [Commands Reference](#commands-reference)
- [MongoDB Collections](#mongodb-collections)

---

## Features

| Category | Commands |
|---|---|
| Warnings | `!warn`, `!unwarn`, `!warns` |
| Queue Punishments | `!queueban`, `!unqueueban` |
| Timeouts | `!gentimeout`, `!untimeout` |
| Server Bans | `!unban` |
| Cases | `!case`, `!case note`, `!history` |
| Evidence | `!evidence add`, `!evidence delete` |
| Reports | `/report` (slash), `!reportreview` |
| Appeals | `!appeal`, `!appealreview` |

All staff commands are **role-gated by ID** — no name matching.

---

## Requirements

- Python **3.11+**
- MongoDB **6.0+** (local or Atlas)
- A Discord bot application with the following **Privileged Gateway Intents** enabled:
  - `SERVER MEMBERS INTENT`
  - `MESSAGE CONTENT INTENT`

### Python packages

```
discord.py>=2.3.0
motor>=3.3.0
python-dotenv>=1.0.0
```

Install with:

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install "discord.py>=2.3.0" "motor>=3.3.0" "python-dotenv>=1.0.0"
```

---

## Project Structure

```
your_bot/
├── bot.py                  ← Main entry point
├── .env                    ← Secrets (token, MongoDB URI)
├── requirements.txt
├── config/
│   ├── __init__.py
│   └── settings.py         ← All IDs and configuration
├── cogs/
│   ├── __init__.py
│   ├── appeals.py
│   ├── cases.py
│   ├── escalation.py
│   ├── evidence.py
│   ├── moderation.py
│   ├── queue_punishments.py
│   ├── report.py
│   └── warnings.py
└── utils/
    ├── __init__.py
    ├── database.py
    └── helpers.py
```

---

## Fresh Setup

### 1. Clone / copy the files

Place the files according to the structure above. Create any missing `__init__.py` files (they can be empty):

```bash
touch config/__init__.py cogs/__init__.py utils/__init__.py
```

### 2. Create your `.env` file

```env
DISCORD_TOKEN=your_bot_token_here
COMMAND_PREFIX=!
GUILD_ID=your_guild_id_here
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=cba_modbot
```

### 3. Enable Developer Mode in Discord

You need Developer Mode on to copy IDs.

`Discord Settings` → `Advanced` → **Developer Mode** → toggle ON

### 4. Fill in `config/settings.py`

Open `settings.py` and replace every `000000000000000000` placeholder with the real ID. See the [Configuration](#configuration) section below for a full walkthrough.

### 5. Create the required Discord channels and roles

The bot expects these channels to exist (you configure their IDs):

| Config key | Purpose |
|---|---|
| `reports` | Where `/report` embeds are posted |
| `appeals` | Where `!appeal` embeds are posted |
| `moderation_alerts` | Where escalation alerts and pings are sent |
| `queue_channels` | All queue lobby channels (permissions are toggled on queue ban) |

### 6. Enable Privileged Intents on your bot application

Go to [discord.com/developers/applications](https://discord.com/developers/applications), select your bot → **Bot** tab:

- ✅ **Server Members Intent**
- ✅ **Message Content Intent**

### 7. Invite the bot

Generate an invite URL with these permissions:

- Manage Roles
- Kick Members
- Ban Members
- Manage Channels
- Timeout Members
- Send Messages
- Embed Links
- Read Message History
- View Channels

Or use the OAuth2 URL generator in the Developer Portal with the `bot` + `applications.commands` scopes.

### 8. Run the bot

```bash
python bot.py
```

On first start the bot will:
1. Connect to MongoDB and create all indexes automatically
2. Load all cogs
3. Sync slash commands to Discord

---

## Adding to an Existing Bot

If you already have a running discord.py 2.x bot and want to add this moderation system to it, follow these steps.

### Step 1 — Copy the files

Copy these into your project, keeping the folder structure:

```
config/settings.py      ← merge with your existing config if you have one
cogs/appeals.py
cogs/cases.py
cogs/escalation.py
cogs/evidence.py
cogs/moderation.py
cogs/queue_punishments.py
cogs/report.py
cogs/warnings.py
utils/database.py
utils/helpers.py
```

If you already have a `config/` or `utils/` folder, **do not overwrite** — instead merge the contents manually (see Step 3).

### Step 2 — Install dependencies

```bash
pip install "motor>=3.3.0" "python-dotenv>=1.0.0"
```

`discord.py>=2.3.0` is assumed to already be installed.

### Step 3 — Merge settings

If you already have a settings/config file, add the following keys to it. If not, use `config/settings.py` directly.

```python
# ── CBA Moderation settings ───────────────────────────────────────────────

"staff_role_ids": [
    123456789012345678,   # Owner
    123456789012345679,   # Admin
    123456789012345680,   # Moderator
],

"alert_ping_role_id": 123456789012345681,

"channels": {
    "reports":           123456789012345682,
    "appeals":           123456789012345683,
    "moderation_alerts": 123456789012345684,
    "queue_channels": [
        123456789012345685,  # premier-queue
        123456789012345686,  # division-1-queue
        # ... add all queue channels
    ],
},

"escalation": { ... },        # copy from settings.py
"community_escalation": [ ... ],
"expiry_days": { ... },
"alert_rules": [ ... ],
"valid_evidence_patterns": [ ... ],
```

### Step 4 — Connect the database in your bot class

In your existing bot's `setup_hook` (or equivalent), add:

```python
from motor.motor_asyncio import AsyncIOMotorClient
from utils.database import Database

async def setup_hook(self) -> None:
    # ... your existing setup code ...

    # Add this:
    self._motor_client = AsyncIOMotorClient(CONFIG["mongodb_uri"])
    self.db = Database(self._motor_client[CONFIG["mongodb_db"]])
    await self.db.create_indexes()
```

And in your `close()` method:

```python
async def close(self) -> None:
    if hasattr(self, "_motor_client") and self._motor_client:
        self._motor_client.close()
    await super().close()
```

### Step 5 — Load the cogs

Add these to wherever your bot loads extensions:

```python
cogs_to_add = [
    "cogs.moderation",
    "cogs.warnings",
    "cogs.cases",
    "cogs.evidence",
    "cogs.queue_punishments",
    "cogs.reports",
    "cogs.appeals",
    "cogs.escalation",
]
for cog in cogs_to_add:
    await bot.load_extension(cog)
```

### Step 6 — Sync slash commands

If your bot doesn't already sync slash commands, add this to `setup_hook`:

```python
await self.tree.sync()
```

> **Note:** `/report` is a global slash command. If you want it guild-only during testing, change `@app_commands.command(...)` in `report.py` to `@app_commands.guilds(discord.Object(id=YOUR_GUILD_ID))`.

### Step 7 — Make sure `self.db` is accessible

The cogs access the database via `interaction.client.db` and `self.bot.db`. Your bot instance must expose the `db` attribute (set in Step 4). If your bot class is named differently, this will work automatically as long as `self.db` is set before cogs try to use it.

---

## Configuration

All IDs live in `config/settings.py`. Open the file and replace the placeholder values.

### Staff Role IDs

```python
"staff_role_ids": [
    987654321098765432,   # Owner
    987654321098765433,   # Admin
    987654321098765434,   # Moderator
],
```

Any member holding **at least one** of these roles can use staff commands.

### Alert Ping Role ID

```python
"alert_ping_role_id": 987654321098765435,
```

This role gets `@mentioned` in `#moderation-alerts` when an escalation threshold is hit.

### Channel IDs

```python
"channels": {
    "reports":           987654321098765436,
    "appeals":           987654321098765437,
    "moderation_alerts": 987654321098765438,
    "queue_channels": [
        987654321098765440,  # premier-queue
        987654321098765441,  # division-1-queue
        987654321098765442,  # academy-queue
        987654321098765443,  # division-2-queue
        987654321098765444,  # division-3-queue
        987654321098765445,  # open-queue
        987654321098765446,  # 2v2-queue
    ],
},
```

---

## Getting IDs from Discord

> Developer Mode must be enabled: `Settings → Advanced → Developer Mode → ON`

| What you need | How to get it |
|---|---|
| **Channel ID** | Right-click the channel → **Copy Channel ID** |
| **Role ID** | Server Settings → Roles → right-click a role → **Copy Role ID** |
| **Guild (Server) ID** | Right-click the server icon → **Copy Server ID** |
| **User ID** | Right-click a user → **Copy User ID** |

---

## Environment Variables

These go in your `.env` file in the project root:

| Variable | Description | Example |
|---|---|---|
| `DISCORD_TOKEN` | Your bot token from the Developer Portal | `MTIz...` |
| `COMMAND_PREFIX` | Prefix for text commands | `!` |
| `GUILD_ID` | Your server's ID | `987654321098765432` |
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGODB_DB` | Database name | `cba_modbot` |

For MongoDB Atlas, the URI looks like:

```
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
```

---

## Commands Reference

All commands prefixed with `!` are text commands (staff only unless noted). `/report` is a slash command available to all members.

### Warnings

| Command | Description |
|---|---|
| `!warn @user [reason]` | Issue a warning. Auto-suggests canonical reason and applies escalation punishment if configured. |
| `!unwarn [case_id] [reason]` | Mark a warning as inactive. Sets case status to Closed and logs the moderator + reason. |
| `!warns @user` | Display full warning, queue ban, timeout, and appeal history for a user. |

### Queue Punishments

| Command | Description |
|---|---|
| `!queueban @user [duration] [reason]` | Remove access to all queue channels. Duration: `30m`, `2h`, `7d`, `permanent`. |
| `!unqueueban @user` | Lift an active queue ban and restore channel access. |

### Timeouts & Bans

| Command | Description |
|---|---|
| `!gentimeout @user [duration] [reason]` | Apply a Discord native timeout. Max 28 days. |
| `!untimeout @user [reason]` | Immediately remove a Discord timeout and update the DB record. |
| `!unban @user [reason]` | Unban a user from the server. Accepts a mention or raw user ID. |

### Cases

| Command | Description |
|---|---|
| `!case [case_id]` | View full case details including notes, appeals, and evidence. |
| `!case note [case_id] [note]` | Add an internal staff note to a case. |
| `!history @user` | View all cases for a user (up to 20 most recent). |

### Evidence

| Command | Description |
|---|---|
| `!evidence add [case_id]` | Opens a form to attach a link + notes, then waits 5 minutes for file uploads. |
| `!evidence delete [case_id]` | Shows a dropdown to select and delete an evidence entry. |

### Reports

| Command | Description |
|---|---|
| `/report @user` | Opens a report form (slash command, available to all members). Posts to `#reports`. |
| `!reportreview [case_id]` | Pull up a report embed with Accept / Reject / Punish buttons. |

### Appeals

| Command | Description |
|---|---|
| `!appeal` | Opens an appeal form (available to all members). Posts to `#appeals`. |
| `!appealreview [appeal_id]` | Pull up an appeal embed with Accept / Reject / Reduce buttons. |

---

## MongoDB Collections

The bot creates and manages these collections automatically:

| Collection | Contents |
|---|---|
| `warnings` | All issued warnings with active/expired status |
| `cases` | Mirror of warnings + reports, used for cross-referencing |
| `evidence` | Evidence entries linked to case IDs |
| `reports` | Player reports submitted via `/report` |
| `appeals` | Appeals submitted via `!appeal` |
| `queue_bans` | Active and historical queue bans |
| `punishments` | General timeouts and queue locks |

Indexes are created automatically on first start via `db.create_indexes()`.

---

## Troubleshooting

**Bot starts but commands don't respond**
- Check that `MESSAGE CONTENT INTENT` is enabled in the Developer Portal.
- Make sure the bot has `Send Messages` and `Embed Links` permissions in the channel.

**`!warn` / `!queueban` say "no permission"**
- Verify the role IDs in `staff_role_ids` are correct. Copy them fresh from Discord with Developer Mode on.

**Queue ban doesn't remove channel access**
- Check that the channel IDs in `queue_channels` are correct.
- The bot needs `Manage Channels` permission (or a specific channel override allowing it to manage permissions).

**Slash command `/report` doesn't appear**
- Run `await bot.tree.sync()` once after adding the cog. It can take up to an hour for global slash commands to propagate — use a guild-scoped command during testing.

**MongoDB connection fails**
- Confirm `MONGODB_URI` in `.env` is correct and the MongoDB service is running.
- For Atlas, whitelist your server's IP in the Atlas Network Access settings.
