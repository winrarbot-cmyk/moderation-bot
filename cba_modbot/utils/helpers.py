"""
Shared utilities: permission checks, embed helpers, fuzzy matching.
"""

from __future__ import annotations

import difflib
from datetime import datetime, timezone
from typing import Any

import discord
from discord.ext import commands

from config.settings import CONFIG

# ── Permission helpers ────────────────────────────────────────────────────────

def has_staff_role(member: discord.Member) -> bool:
    """Return True if the member holds any configured staff role."""
    staff = {r.lower() for r in CONFIG["staff_roles"]}
    return any(r.name.lower() in staff for r in member.roles)


def staff_only():
    """Command check – raises CheckFailure if the author isn't staff."""
    async def predicate(ctx: commands.Context) -> bool:
        if not has_staff_role(ctx.author):
            raise commands.MissingPermissions(["staff_role"])
        return True
    return commands.check(predicate)


# ── Embed helpers ─────────────────────────────────────────────────────────────

COLOUR_SUCCESS  = 0x2ECC71   # green
COLOUR_ERROR    = 0xE74C3C   # red
COLOUR_WARNING  = 0xF39C12   # amber
COLOUR_INFO     = 0x3498DB   # blue
COLOUR_CASE     = 0x1A2B4C   # CBA navy
COLOUR_REPORT   = 0xE67E22   # orange
COLOUR_APPEAL   = 0x9B59B6   # purple


def base_embed(
    title: str,
    description: str = "",
    colour: int = COLOUR_INFO,
) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, colour=colour)
    embed.timestamp = datetime.now(timezone.utc)
    return embed


def case_embed(case: dict) -> discord.Embed:
    colour = {
        "Open":         COLOUR_INFO,
        "Under Review": COLOUR_WARNING,
        "Punished":     COLOUR_ERROR,
        "Appealed":     COLOUR_APPEAL,
        "Closed":       0x95A5A6,
    }.get(case.get("status", "Open"), COLOUR_INFO)

    embed = discord.Embed(
        title=f"📁 Case #{case['case_id']}",
        colour=colour,
    )
    embed.add_field(name="User",       value=f"<@{case['user_id']}> ({case.get('user_name', '?')})", inline=True)
    embed.add_field(name="Moderator",  value=f"<@{case['mod_id']}> ({case.get('mod_name', '?')})", inline=True)
    embed.add_field(name="Status",     value=case.get("status", "Open"), inline=True)
    embed.add_field(name="Reason",     value=case.get("reason", "N/A"),  inline=False)
    punishment = case.get("punishment", {})
    embed.add_field(name="Punishment", value=punishment.get("label", "N/A"), inline=True)
    embed.add_field(name="Category",   value=case.get("category", "N/A"), inline=True)
    created = case.get("created_at")
    if created:
        embed.add_field(name="Date", value=discord.utils.format_dt(created, "F"), inline=True)
    return embed


def warning_summary_embed(user: discord.Member, warnings: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚠️ Warning History – {user.display_name}",
        colour=COLOUR_WARNING,
    )
    if not warnings:
        embed.description = "No warnings on record."
        return embed

    active   = [w for w in warnings if w.get("active")]
    expired  = [w for w in warnings if not w.get("active")]

    if active:
        lines = []
        for w in active:
            lines.append(
                f"**#{w['case_id']}** | {w['reason']} | "
                f"Mod: {w.get('mod_name','?')} | "
                f"{discord.utils.format_dt(w['created_at'], 'd')}"
            )
        embed.add_field(name="🔴 Active", value="\n".join(lines), inline=False)

    if expired:
        lines = []
        for w in expired[:5]:  # limit to last 5
            lines.append(
                f"**#{w['case_id']}** | {w['reason']} | "
                f"{discord.utils.format_dt(w['created_at'], 'd')}"
            )
        embed.add_field(name="⚫ Expired (last 5)", value="\n".join(lines), inline=False)

    return embed


# ── Fuzzy reason matching ─────────────────────────────────────────────────────

KNOWN_REASONS: list[str] = list(CONFIG["escalation"].keys())

REASON_ALIASES: dict[str, str] = {
    "rage quitting":           "Queue Dodge",
    "rage quit":               "Queue Dodge",
    "dodge":                   "Queue Dodge",
    "no show":                 "Not Showing Up After Teams Chosen",
    "no-show":                 "Not Showing Up After Teams Chosen",
    "afk":                     "Repeated AFK",
    "delay":                   "Intentionally Delaying a Match",
    "refuse":                  "Refusing to Play Assigned Match",
    "smurf":                   "Smurfing",
    "smurfing":                "Smurfing",
    "account share":           "Account Sharing",
    "account sharing":         "Account Sharing",
    "boost":                   "Boosting",
    "boosting":                "Boosting",
    "evasion":                 "Queue Ban Evasion",
    "ban evasion":             "Queue Ban Evasion",
    "manipulation":            "Match Manipulation",
    "match fixing":            "Match Manipulation",
    "toxic":                   "Toxicity",
    "toxicity":                "Toxicity",
    "harass":                  "Harassment",
    "harassment":              "Harassment",
    "slur":                    "Discriminatory Language",
    "discriminatory":          "Discriminatory Language",
    "racist":                  "Discriminatory Language",
    "threat":                  "Threats / Doxxing",
    "doxx":                    "Threats / Doxxing",
    "leave":                   "Leaving Queue After Accepting",
    "leaving":                 "Leaving Queue After Accepting",
}


def suggest_reason(raw: str) -> str | None:
    """
    Given a free-text reason, try to map it to a known infraction.
    Returns the canonical name if a match is found, else None.
    """
    normalized = raw.strip().lower()

    # Exact alias match
    if normalized in REASON_ALIASES:
        return REASON_ALIASES[normalized]

    # Check if known reason name contains the input
    for known in KNOWN_REASONS:
        if normalized in known.lower() or known.lower() in normalized:
            return known

    # Fuzzy match
    matches = difflib.get_close_matches(
        normalized,
        [r.lower() for r in KNOWN_REASONS] + list(REASON_ALIASES.keys()),
        n=1,
        cutoff=0.55,
    )
    if matches:
        candidate = matches[0]
        if candidate in REASON_ALIASES:
            return REASON_ALIASES[candidate]
        # find original case
        for r in KNOWN_REASONS:
            if r.lower() == candidate:
                return r

    return None


def categorise_reason(reason: str) -> str:
    """Return the broad category for a given reason."""
    queue_infraction = {
        "Queue Dodge",
        "Leaving Queue After Accepting",
        "Not Showing Up After Teams Chosen",
        "Repeated AFK",
        "Intentionally Delaying a Match",
        "Refusing to Play Assigned Match",
    }
    competitive = {"Smurfing", "Account Sharing", "Boosting", "Queue Ban Evasion", "Match Manipulation"}
    behaviour   = {"Toxicity", "Harassment", "Discriminatory Language", "Threats / Doxxing"}

    if reason in queue_infraction:
        return "Queue Infraction"
    if reason in competitive:
        return "Competitive Integrity"
    if reason in behaviour:
        return "In-Game Behaviour"
    return "Community"


def is_queue_related(reason: str) -> bool:
    return categorise_reason(reason) in ("Queue Infraction", "Competitive Integrity", "In-Game Behaviour")


# ── Duration helpers ──────────────────────────────────────────────────────────

def format_duration(minutes: int | None) -> str:
    if minutes is None:
        return "Permanent"
    if minutes < 60:
        return f"{minutes}m"
    if minutes < 1440:
        h = minutes // 60
        m = minutes % 60
        return f"{h}h{' ' + str(m) + 'm' if m else ''}"
    d = minutes // 1440
    h = (minutes % 1440) // 60
    return f"{d}d{' ' + str(h) + 'h' if h else ''}"


def parse_duration(text: str) -> int | None:
    """
    Parse a duration string like '30m', '2h', '7d', 'permanent' → minutes.
    Returns None for permanent.
    """
    text = text.strip().lower()
    if text in ("permanent", "perm", "inf", "forever"):
        return None
    if text.endswith("m"):
        return int(text[:-1])
    if text.endswith("h"):
        return int(text[:-1]) * 60
    if text.endswith("d"):
        return int(text[:-1]) * 1440
    if text.endswith("w"):
        return int(text[:-1]) * 10080
    # Plain integer → minutes
    return int(text)
