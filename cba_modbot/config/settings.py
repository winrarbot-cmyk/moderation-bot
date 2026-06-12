"""
CBA Bot – Configuration
Reads from environment variables (or a .env file via python-dotenv).
All channel/role names can be overridden here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

CONFIG: dict = {
    # ── Bot core ──────────────────────────────────────────────────────────────
    "token": os.getenv("DISCORD_TOKEN", ""),
    "prefix": os.getenv("COMMAND_PREFIX", "!"),
    "guild_id": int(os.getenv("GUILD_ID", "0")),

    # ── MongoDB ───────────────────────────────────────────────────────────────
    "mongodb_uri": os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
    "mongodb_db": os.getenv("MONGODB_DB", "cba_modbot"),

    # ── Staff roles (names must match exactly in Discord) ─────────────────────
    "staff_roles": [
        "ENTER_STAFF_ROLE_1_HERE",   # e.g. your Owner role name
        "ENTER_STAFF_ROLE_2_HERE",   # e.g. your Admin role name
        "ENTER_STAFF_ROLE_3_HERE",   # e.g. your Moderator role name
    ],

    # ── Role used for @ping in escalation alerts ──────────────────────────────
    "alert_ping_role": "ENTER_ALERT_PING_ROLE_HERE",  # role name to ping in #moderation-alerts

    # ── Channels ──────────────────────────────────────────────────────────────
    "channels": {
        # Channel where /report embeds are posted
        "reports": "ENTER_REPORTS_CHANNEL_HERE",
        # Channel where !appeal embeds are posted
        "appeals": "ENTER_APPEALS_CHANNEL_HERE",
        # Channel where escalation alerts are posted
        "moderation_alerts": "ENTER_MODERATION_ALERTS_CHANNEL_HERE",
        # All queue-related channels – ViewChannel is removed when a queue ban is issued
        "queue_channels": [
            "ENTER_QUEUE_CHANNEL_1_HERE",
            "ENTER_QUEUE_CHANNEL_2_HERE",
            "ENTER_QUEUE_CHANNEL_3_HERE",
            "ENTER_QUEUE_CHANNEL_4_HERE",
        ],
    },

    # ── Punishment escalation tables ─────────────────────────────────────────
    # Each list is ordered: [offence_count_1, offence_count_2, ...], value = action dict
    # action: {"type": "warning" | "queue_lock" | "queue_ban", "duration_minutes": int | None}
    # duration_minutes = None  → permanent
    "escalation": {
        # ── Queue infractions ─────────────────────────────────────────────────
        "Queue Dodge": [
            {"type": "warning", "duration_minutes": None, "label": "Warning"},
            {"type": "queue_lock", "duration_minutes": 15,   "label": "15m Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 180,  "label": "3h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 720,  "label": "12h Queue Lock"},
        ],
        "Leaving Queue After Accepting": [
            {"type": "queue_lock", "duration_minutes": 15,   "label": "15m Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 60,   "label": "1h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 180,  "label": "3h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 720,  "label": "12h Queue Lock"},
        ],
        "Not Showing Up After Teams Chosen": [
            {"type": "queue_lock", "duration_minutes": 60,   "label": "1h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 180,  "label": "3h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 720,  "label": "12h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 1440, "label": "1d Queue Lock"},
        ],
        "Repeated AFK": [
            {"type": "warning", "duration_minutes": None, "label": "Warning"},
            {"type": "queue_lock", "duration_minutes": 60,   "label": "1h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 180,  "label": "3h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 1440, "label": "1d Queue Lock"},
        ],
        "Intentionally Delaying a Match": [
            {"type": "queue_lock", "duration_minutes": 60,   "label": "1h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 180,  "label": "3h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 720,  "label": "12h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 1440, "label": "1d Queue Lock"},
        ],
        "Refusing to Play Assigned Match": [
            {"type": "queue_lock", "duration_minutes": 180,    "label": "3h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 720,    "label": "12h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 1440,   "label": "1d Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 10080,  "label": "7d Queue Lock"},
        ],
        # ── Competitive integrity ─────────────────────────────────────────────
        "Smurfing": [
            {"type": "queue_ban", "duration_minutes": 10080,  "label": "7d Queue Ban"},
            {"type": "queue_ban", "duration_minutes": 43200,  "label": "30d Queue Ban"},
            {"type": "queue_ban", "duration_minutes": None,   "label": "Permanent Queue Ban"},
        ],
        "Account Sharing": [
            {"type": "queue_ban", "duration_minutes": 10080,  "label": "7d Queue Ban"},
            {"type": "queue_ban", "duration_minutes": 43200,  "label": "30d Queue Ban"},
            {"type": "queue_ban", "duration_minutes": None,   "label": "Permanent Queue Ban"},
        ],
        "Boosting": [
            {"type": "queue_ban", "duration_minutes": 43200,  "label": "30d Queue Ban"},
            {"type": "queue_ban", "duration_minutes": None,   "label": "Permanent Queue Ban"},
        ],
        "Queue Ban Evasion": [
            {"type": "queue_ban", "duration_minutes": 43200,  "label": "30d Queue Ban"},
            {"type": "queue_ban", "duration_minutes": None,   "label": "Permanent Queue Ban"},
        ],
        "Match Manipulation": [
            {"type": "queue_ban", "duration_minutes": None,   "label": "Permanent Queue Ban"},
        ],
        # ── In-game behaviour ─────────────────────────────────────────────────
        "Toxicity": [
            {"type": "warning", "duration_minutes": None, "label": "Warning"},
            {"type": "queue_lock", "duration_minutes": 60,   "label": "1h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 180,  "label": "3h Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 1440, "label": "1d Queue Lock"},
        ],
        "Harassment": [
            {"type": "queue_lock", "duration_minutes": 1440,  "label": "1d Queue Lock"},
            {"type": "queue_lock", "duration_minutes": 10080, "label": "7d Queue Lock"},
            {"type": "queue_ban",  "duration_minutes": 43200, "label": "30d Queue Ban"},
            {"type": "queue_ban",  "duration_minutes": None,  "label": "Permanent Queue Ban"},
        ],
        "Discriminatory Language": [
            {"type": "queue_ban", "duration_minutes": 10080,  "label": "7d Queue Ban"},
            {"type": "queue_ban", "duration_minutes": 43200,  "label": "30d Queue Ban"},
            {"type": "queue_ban", "duration_minutes": None,   "label": "Permanent Queue Ban"},
        ],
        "Threats / Doxxing": [
            {"type": "queue_ban", "duration_minutes": None,   "label": "Permanent Queue Ban"},
        ],
    },

    # ── Community warning escalation (threshold → action) ────────────────────
    # Applied when a community warning is added and total active >= threshold
    "community_escalation": [
        {"threshold": 1, "type": "warning",         "duration_minutes": None,   "label": "Warning"},
        {"threshold": 2, "type": "general_timeout",  "duration_minutes": 60,    "label": "1h Timeout"},
        {"threshold": 3, "type": "general_timeout",  "duration_minutes": 1440,  "label": "24h Timeout"},
        {"threshold": 4, "type": "general_timeout",  "duration_minutes": 10080, "label": "7d Timeout"},
        {"threshold": 5, "type": "kick",             "duration_minutes": None,  "label": "Kick"},
        {"threshold": 6, "type": "ban",              "duration_minutes": None,  "label": "Ban"},
    ],

    # ── Warning expiry (days) ─────────────────────────────────────────────────
    "expiry_days": {
        "default_queue":     60,
        "default_community": 90,
        "no_expiry": [  # These infractions never expire
            "Smurfing",
            "Account Sharing",
            "Boosting",
            "Match Manipulation",
        ],
    },

    # ── Escalation alerts ─────────────────────────────────────────────────────
    "alert_rules": [
        {
            "label": "3 reports within 7 days",
            "collection": "reports",
            "count": 3,
            "window_days": 7,
        },
        {
            "label": "2 queue dodges within 24 hours",
            "collection": "warnings",
            "reason": "Queue Dodge",
            "count": 2,
            "window_days": 1,
        },
    ],

    # ── Valid evidence link domains / patterns ────────────────────────────────
    "valid_evidence_patterns": [
        r"https?://",  # Any URL is accepted; validation is lenient
    ],
}
