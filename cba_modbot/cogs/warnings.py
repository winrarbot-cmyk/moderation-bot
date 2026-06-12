"""Cog: WarningsCommands: !warn, !warns"""

from future import annotations

import loggingfrom datetime import datetime, timedelta, timezone

import discordfrom discord.ext import commands

from config.settings import CONFIGfrom utils.helpers import (COLOUR_WARNING, COLOUR_ERROR, COLOUR_SUCCESS, COLOUR_INFO,staff_only, suggest_reason, categorise_reason, is_queue_related,format_duration, base_embed, warning_summary_embed,)

log = logging.getLogger("cba_bot.warnings")

────────────────────────────────────────────────────────────────────────────

Interactive views

────────────────────────────────────────────────────────────────────────────

class ConfirmReasonView(discord.ui.View):"""Shown when the entered reason doesn't match a known infraction."""

def init(self, original: str, suggested: str, author_id: int):super().init(timeout=60)self.original  = originalself.suggested = suggestedself.author_id = author_idself.choice: str | None = None   # set on interaction

async def interaction_check(self, interaction: discord.Interaction) -> bool:if interaction.user.id != self.author_id:await interaction.response.send_message("This is not your interaction.", ephemeral=True)return Falsereturn True

@discord.ui.button(label="✅ Confirm Original Reason", style=discord.ButtonStyle.success)async def keep_original(self, interaction: discord.Interaction, _: discord.ui.Button):self.choice = self.originalself.stop()await interaction.response.defer()

@discord.ui.button(label="❌ Use Suggested Reason", style=discord.ButtonStyle.danger)async def use_suggested(self, interaction: discord.Interaction, _: discord.ui.Button):self.choice = self.suggestedself.stop()await interaction.response.defer()

class ApplyPunishmentView(discord.ui.View):"""Shown when a punishment recommendation exists."""

def init(self, author_id: int):super().init(timeout=60)self.apply: bool | None = Noneself.author_id = author_id

async def interaction_check(self, interaction: discord.Interaction) -> bool:if interaction.user.id != self.author_id:await interaction.response.send_message("This is not your interaction.", ephemeral=True)return Falsereturn True

@discord.ui.button(label="✅ Apply", style=discord.ButtonStyle.success)async def do_apply(self, interaction: discord.Interaction, _: discord.ui.Button):self.apply = Trueself.stop()await interaction.response.defer()

@discord.ui.button(label="❌ Warning Only", style=discord.ButtonStyle.secondary)async def warning_only(self, interaction: discord.Interaction, _: discord.ui.Button):self.apply = Falseself.stop()await interaction.response.defer()

class EvidenceButtonView(discord.ui.View):"""Persistent view with a 'View Evidence' button on warns embeds."""

def init(self, case_id: str):super().init(timeout=None)self.case_id = case_id

@discord.ui.button(label="📎 View Evidence",style=discord.ButtonStyle.secondary,custom_id="view_evidence",)async def view_evidence(self, interaction: discord.Interaction, _: discord.ui.Button):db = interaction.client.dbitems = await db.get_evidence(self.case_id)if not items:await interaction.response.send_message("No evidence attached to this case.", ephemeral=True)return

embed = discord.Embed(
    title=f"📎 Evidence – Case #{self.case_id}",
    colour=COLOUR_INFO,
)
for i, ev in enumerate(items, 1):
    parts = []
    if ev.get("link"):
        parts.append(f"🔗 {ev['link']}")
    if ev.get("attachments"):
        for url in ev["attachments"]:
            parts.append(f"📁 {url}")
    if ev.get("notes"):
        parts.append(f"📝 {ev['notes']}")
    embed.add_field(
        name=f"Entry #{i}",
        value="\n".join(parts) or "No details.",
        inline=False,
    )
await interaction.response.send_message(embed=embed, ephemeral=True)

────────────────────────────────────────────────────────────────────────────

Cog

────────────────────────────────────────────────────────────────────────────

class Warnings(commands.Cog):def init(self, bot: commands.Bot):self.bot = bot

@propertydef db(self):return self.bot.db

── !warn ─────────────────────────────────────────────────────────────────

@commands.command(name="warn")@staff_only()async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str):"""Warn a user. Automatically escalates punishment if the reason matches a known infraction.Usage: !warn @user [reason]"""guild_id = ctx.guild.idfinal_reason = reason.strip()

# ── Fuzzy match check ─────────────────────────────────────────────────
suggested = suggest_reason(final_reason)
known_reasons = list(CONFIG["escalation"].keys())
reason_is_known = final_reason in known_reasons

if not reason_is_known and suggested and suggested != final_reason:
    # Ask moderator
    embed = base_embed(
        "⚠️ Unrecognised Infraction",
        f"The reason **{final_reason}** is not an official infraction.\n"
        f"Did you mean **{suggested}**?",
        colour=COLOUR_WARNING,
    )
    view = ConfirmReasonView(final_reason, suggested, ctx.author.id)
    msg = await ctx.send(embed=embed, view=view)
    await view.wait()
    await msg.edit(view=None)

    if view.choice is None:
        await ctx.send("⏰ Confirmation timed out. Warning cancelled.", delete_after=8)
        return
    final_reason = view.choice

# ── Escalation lookup ─────────────────────────────────────────────────
escalation_table = CONFIG["escalation"].get(final_reason)
category = categorise_reason(final_reason)

recommended_punishment: dict | None = None
offence_count = 0

if escalation_table:
    offence_count = await self.db.count_active_warnings_by_reason(
        member.id, guild_id, final_reason
    )
    idx = min(offence_count, len(escalation_table) - 1)
    recommended_punishment = escalation_table[idx]

# ── Determine warning type ────────────────────────────────────────────
warning_type = "queue" if is_queue_related(final_reason) else "community"

# ── Punishment recommendation ─────────────────────────────────────────
actual_punishment = {"type": "warning", "label": "Warning", "duration_minutes": None}
apply_punishment = False

if recommended_punishment and recommended_punishment["type"] != "warning":
    embed = base_embed(
        "🔔 Punishment Recommendation",
        f"**{member.display_name}** – Offence #{offence_count + 1} of **{final_reason}**\n\n"
        f"Recommended Punishment: **{recommended_punishment['label']}**",
        colour=COLOUR_WARNING,
    )
    view = ApplyPunishmentView(ctx.author.id)
    msg = await ctx.send(embed=embed, view=view)
    await view.wait()
    await msg.edit(view=None)

    if view.apply is True:
        actual_punishment = recommended_punishment
        apply_punishment = True
elif recommended_punishment:
    actual_punishment = recommended_punishment

# ── Save warning ──────────────────────────────────────────────────────
warning = await self.db.create_warning(
    user_id=member.id,
    user_name=str(member),
    mod_id=ctx.author.id,
    mod_name=str(ctx.author),
    reason=final_reason,
    category=category,
    punishment=actual_punishment,
    guild_id=guild_id,
    warning_type=warning_type,
)

# ── Set expiry ────────────────────────────────────────────────────────
no_expiry_reasons = CONFIG["expiry_days"]["no_expiry"]
if final_reason not in no_expiry_reasons:
    expiry_days = (
        CONFIG["expiry_days"]["default_queue"]
        if warning_type == "queue"
        else CONFIG["expiry_days"]["default_community"]
    )
    expires = datetime.now(timezone.utc) + timedelta(days=expiry_days)
    await self.db.set_warning_expiry(warning["case_id"], expires)

# ── Apply punishment ──────────────────────────────────────────────────
if apply_punishment:
    await self._apply_punishment(ctx, member, warning, actual_punishment)

# ── Community warning escalation ──────────────────────────────────────
if warning_type == "community":
    await self._check_community_escalation(ctx, member, guild_id)

# ── Escalation alerts ─────────────────────────────────────────────────
await self._check_escalation_alerts(ctx, member, guild_id, final_reason)

# ── Confirmation embed ────────────────────────────────────────────────
embed = discord.Embed(
    title="✅ Warning Issued",
    colour=COLOUR_SUCCESS,
)
embed.add_field(name="User",       value=member.mention,              inline=True)
embed.add_field(name="Case ID",    value=f"#{warning['case_id']}",    inline=True)
embed.add_field(name="Reason",     value=final_reason,                inline=True)
embed.add_field(name="Category",   value=category,                    inline=True)
embed.add_field(name="Punishment", value=actual_punishment["label"],  inline=True)
embed.set_footer(text=f"Issued by {ctx.author.display_name}")
embed.timestamp = datetime.now(timezone.utc)
await ctx.send(embed=embed)

── !unwarn [case_id] ─────────────────────────────────────────────────────

@commands.command(name="unwarn")
@staff_only()
async def unwarn(self, ctx: commands.Context, case_id: str, *, reason: str = "No reason provided."):
    """Mark a warning as inactive (closed). Logs moderator and reason.
    Usage: !unwarn 51832
           !unwarn 51832 Issued in error"""
    warning = await self.db.warnings.find_one({"case_id": case_id, "guild_id": ctx.guild.id})
    if not warning:
        await ctx.send(f"❌ Warning **#{case_id}** not found.", delete_after=8)
        return

    if not warning.get("active"):
        await ctx.send(
            f"⚠️ Warning **#{case_id}** is already inactive/closed.",
            delete_after=8,
        )
        return

    # Mark warning as inactive
    await self.db.warnings.update_one(
        {"case_id": case_id},
        {"$set": {
            "active":        False,
            "status":        "Closed",
            "unwarn_mod_id":   ctx.author.id,
            "unwarn_mod_name": str(ctx.author),
            "unwarn_reason":   reason,
            "unwarn_at":       datetime.now(timezone.utc),
        }},
    )
    # Mirror status to cases collection
    await self.db.update_case_status(case_id, "Closed")

    embed = base_embed(
        "✅ Warning Removed",
        f"Warning **#{case_id}** has been marked as inactive and the case is now **Closed**.",
        colour=COLOUR_SUCCESS,
    )
    embed.add_field(name="User",      value=f"<@{warning['user_id']}>",         inline=True)
    embed.add_field(name="Case ID",   value=f"#{case_id}",                      inline=True)
    embed.add_field(name="Original Reason", value=warning.get("reason", "N/A"), inline=False)
    embed.add_field(name="Unwarn Reason",   value=reason,                       inline=False)
    embed.set_footer(text=f"Removed by {ctx.author.display_name}")
    embed.timestamp = datetime.now(timezone.utc)
    await ctx.send(embed=embed)
    log.info("Warning #%s deactivated by %s – reason: %s", case_id, ctx.author, reason)

── Helper: apply punishment ──────────────────────────────────────────────

async def _apply_punishment(self,ctx: commands.Context,member: discord.Member,warning: dict,punishment: dict,) -> None:p_type    = punishment["type"]duration  = punishment.get("duration_minutes")guild_id  = ctx.guild.id

if p_type == "queue_lock":
    # Queue lock = queue ban for the specified duration
    await self.db.create_queue_ban(
        user_id=member.id,
        user_name=str(member),
        mod_id=ctx.author.id,
        mod_name=str(ctx.author),
        reason=warning["reason"],
        duration_minutes=duration,
        case_id=warning["case_id"],
        guild_id=guild_id,
    )
    await self._remove_queue_access(ctx.guild, member)

elif p_type == "queue_ban":
    await self.db.create_queue_ban(
        user_id=member.id,
        user_name=str(member),
        mod_id=ctx.author.id,
        mod_name=str(ctx.author),
        reason=warning["reason"],
        duration_minutes=duration,
        case_id=warning["case_id"],
        guild_id=guild_id,
    )
    await self._remove_queue_access(ctx.guild, member)

elif p_type == "general_timeout":
    if duration:
        until = discord.utils.utcnow() + timedelta(minutes=duration)
        try:
            await member.timeout(until, reason=warning["reason"])
        except discord.Forbidden:
            log.warning("Cannot timeout %s – missing permissions.", member)

elif p_type == "kick":
    try:
        await member.kick(reason=warning["reason"])
    except discord.Forbidden:
        log.warning("Cannot kick %s – missing permissions.", member)

elif p_type == "ban":
    try:
        await member.ban(reason=warning["reason"])
    except discord.Forbidden:
        log.warning("Cannot ban %s – missing permissions.", member)

# Record in punishments DB
await self.db.create_punishment(
    user_id=member.id,
    user_name=str(member),
    mod_id=ctx.author.id,
    mod_name=str(ctx.author),
    punishment_type=p_type,
    reason=warning["reason"],
    duration_minutes=duration,
    case_id=warning["case_id"],
    guild_id=guild_id,
)

async def _remove_queue_access(self, guild: discord.Guild, member: discord.Member) -> None:queue_channel_names = CONFIG["channels"]["queue_channels"]for ch_name in queue_channel_names:channel = discord.utils.get(guild.channels, name=ch_name)if channel:try:await channel.set_permissions(member, view_channel=False)except discord.Forbidden:log.warning("Cannot set permissions in %s", channel.name)

── Helper: community warning escalation ──────────────────────────────────

async def _check_community_escalation(self, ctx: commands.Context, member: discord.Member, guild_id: int) -> None:count = await self.db.count_active_community_warnings(member.id, guild_id)escalation = CONFIG["community_escalation"]action = Nonefor rule in reversed(escalation):if count >= rule["threshold"]:action = rulebreak

if not action or action["type"] == "warning":
    return

p_type   = action["type"]
duration = action.get("duration_minutes")
label    = action["label"]

if p_type == "general_timeout" and duration:
    until = discord.utils.utcnow() + timedelta(minutes=duration)
    try:
        await member.timeout(until, reason=f"Automatic escalation: {count} community warnings")
        await ctx.send(
            f"⚠️ {member.mention} has been automatically timed out ({label}) "
            f"for reaching **{count}** active community warnings.",
            delete_after=30,
        )
    except discord.Forbidden:
        pass

elif p_type == "kick":
    try:
        await member.kick(reason=f"Automatic escalation: {count} community warnings")
        await ctx.send(f"⚠️ {member.mention} was kicked after {count} community warnings.")
    except discord.Forbidden:
        pass

elif p_type == "ban":
    try:
        await member.ban(reason=f"Automatic escalation: {count} community warnings")
        await ctx.send(f"⚠️ {member.mention} was banned after {count} community warnings.")
    except discord.Forbidden:
        pass

── Helper: escalation alerts ─────────────────────────────────────────────

async def _check_escalation_alerts(self,ctx: commands.Context,member: discord.Member,guild_id: int,reason: str,) -> None:alert_channel_name = CONFIG["channels"]["moderation_alerts"]alert_channel = discord.utils.get(ctx.guild.text_channels, name=alert_channel_name)if not alert_channel:return

for rule in CONFIG["alert_rules"]:
    if rule.get("reason") and rule["reason"] != reason:
        continue
    if rule.get("collection") == "warnings":
        count = await self.db.count_recent_warnings_by_reason(
            member.id, guild_id, reason, rule["window_days"]
        )
    else:
        count = await self.db.count_recent_reports(member.id, guild_id, rule["window_days"])

    if count >= rule["count"]:
        # Find @Moderator role
        mod_role = discord.utils.get(ctx.guild.roles, name=CONFIG["alert_ping_role"])
        ping = mod_role.mention if mod_role else f"@{CONFIG['alert_ping_role']}"
        embed = base_embed(
            "🚨 Escalation Alert",
            f"{ping}\n"
            f"**{member.display_name}** ({member.mention}) has triggered an alert:\n"
            f"**{rule['label']}**",
            colour=COLOUR_ERROR,
        )
        await alert_channel.send(embed=embed)

── !warns ────────────────────────────────────────────────────────────────

@commands.command(name="warns")@staff_only()async def warns(self, ctx: commands.Context, member: discord.Member):"""Display full warning history for a user.Usage: !warns @user"""guild_id = ctx.guild.idwarnings    = await self.db.get_warnings(member.id, guild_id)punishments = await self.db.get_all_punishments(member.id, guild_id)queue_bans  = await self.db.queue_bans.find({"user_id": member.id, "guild_id": guild_id}).sort("created_at", -1).to_list(length=None)appeals = await self.db.appeals.find({"user_id": member.id, "guild_id": guild_id}).sort("created_at", -1).to_list(length=None)

# ── Build embed ───────────────────────────────────────────────────────
embed = discord.Embed(
    title=f"📋 Record – {member.display_name}",
    colour=COLOUR_WARNING,
)
embed.set_thumbnail(url=member.display_avatar.url)

# Queue Warnings
queue_warns = [w for w in warnings if w.get("warning_type") == "queue"]
if queue_warns:
    lines = [
        f"**#{w['case_id']}** | {w['reason']} | Mod: {w.get('mod_name','?')} | "
        f"{discord.utils.format_dt(w['created_at'], 'd')} | "
        f"{'🟢 Active' if w.get('active') else '⚫ Expired'}"
        for w in queue_warns
    ]
    embed.add_field(name="⚠️ Queue Warnings", value="\n".join(lines), inline=False)

# Community Warnings
comm_warns = [w for w in warnings if w.get("warning_type") == "community"]
if comm_warns:
    lines = [
        f"**#{w['case_id']}** | {w['reason']} | Mod: {w.get('mod_name','?')} | "
        f"{discord.utils.format_dt(w['created_at'], 'd')} | "
        f"{'🟢 Active' if w.get('active') else '⚫ Expired'}"
        for w in comm_warns
    ]
    embed.add_field(name="💬 Community Warnings", value="\n".join(lines), inline=False)

# Queue Bans
if queue_bans:
    lines = [
        f"**#{qb['case_id']}** | {qb['reason']} | "
        f"{format_duration(qb.get('duration_minutes'))} | "
        f"{'🔴 Active' if qb.get('active') else '✅ Ended'}"
        for qb in queue_bans
    ]
    embed.add_field(name="🚫 Queue Bans", value="\n".join(lines), inline=False)

# Queue Timeouts / Locks (from punishments)
qlocks = [p for p in punishments if p.get("type") in ("queue_lock",)]
if qlocks:
    lines = [
        f"**#{p['case_id']}** | {format_duration(p.get('duration_minutes'))} | "
        f"{discord.utils.format_dt(p['created_at'], 'd')} | "
        f"{'🔴 Active' if p.get('active') else '✅ Ended'}"
        for p in qlocks
    ]
    embed.add_field(name="⏱️ Queue Locks", value="\n".join(lines), inline=False)

# General Timeouts
gtimeouts = [p for p in punishments if p.get("type") == "general_timeout"]
if gtimeouts:
    lines = [
        f"**#{p['case_id']}** | {format_duration(p.get('duration_minutes'))} | "
        f"{discord.utils.format_dt(p['created_at'], 'd')}"
        for p in gtimeouts
    ]
    embed.add_field(name="⏸️ General Timeouts", value="\n".join(lines), inline=False)

# Appeals
if appeals:
    lines = [
        f"Appeal #{a['appeal_id']} → Case #{a['case_id']} | {a['status']}"
        for a in appeals
    ]
    embed.add_field(name="📨 Appeals", value="\n".join(lines), inline=False)

if not warnings and not queue_bans and not punishments:
    embed.description = "No records found for this user."

embed.set_footer(text=f"Requested by {ctx.author.display_name}")
embed.timestamp = datetime.now(timezone.utc)

# ── Button view for evidence ───────────────────────────────────────────
# Add evidence buttons for each case that has evidence
case_ids_with_evidence = set()
for w in warnings:
    items = await self.db.get_evidence(w["case_id"])
    if items:
        case_ids_with_evidence.add(w["case_id"])

if case_ids_with_evidence:
    # We'll send one embed per page; for simplicity, one embed + one button for the first case with evidence
    first_case = next(iter(case_ids_with_evidence))
    view = EvidenceButtonView(first_case)
    await ctx.send(
        embed=embed,
        view=view,
        content=f"ℹ️ Evidence available for case(s): {', '.join('#' + c for c in case_ids_with_evidence)}",
    )
else:
    await ctx.send(embed=embed)

async def setup(bot: commands.Bot) -> None:await bot.add_cog(Warnings(bot))
