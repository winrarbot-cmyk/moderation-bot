"""
Cog: Reports
Commands: /report (slash), !reportreview [case_id]
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import CONFIG
from utils.helpers import (
    COLOUR_REPORT, COLOUR_SUCCESS, COLOUR_ERROR, COLOUR_INFO,
    COLOUR_WARNING, staff_only, base_embed,
)

log = logging.getLogger("cba_bot.reports")


# ── Modal ─────────────────────────────────────────────────────────────────────

class ReportModal(discord.ui.Modal, title="Submit a Report"):
    match_id = discord.ui.TextInput(
        label="Match ID",
        placeholder="e.g. CBA-2026-0042",
        required=True,
        max_length=64,
    )
    description = discord.ui.TextInput(
        label="Description",
        placeholder="Describe what happened in detail…",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1500,
    )
    evidence_link = discord.ui.TextInput(
        label="Evidence Link (optional)",
        placeholder="YouTube, Medal, Twitch, Streamable, or any URL",
        required=False,
        max_length=500,
    )

    def __init__(self, reported_member: discord.Member):
        super().__init__()
        self.reported_member = reported_member
        self.submitted        = False
        self.result_case_id: str | None = None

    async def on_submit(self, interaction: discord.Interaction):
        self.submitted = True
        db = interaction.client.db

        # Save report
        report = await db.create_report(
            reporter_id=interaction.user.id,
            reporter_name=str(interaction.user),
            reported_id=self.reported_member.id,
            reported_name=str(self.reported_member),
            match_id=self.match_id.value.strip(),
            description=self.description.value.strip(),
            evidence_link=self.evidence_link.value.strip(),
            guild_id=interaction.guild_id,
        )
        self.result_case_id = report["case_id"]

        # Post to #support-reports
        reports_channel_name = CONFIG["channels"]["reports"]
        reports_channel = discord.utils.get(
            interaction.guild.text_channels, name=reports_channel_name
        )
        if reports_channel:
            embed = _build_report_embed(report, interaction.user, self.reported_member)
            view  = ReportActionView(report["case_id"])
            await reports_channel.send(embed=embed, view=view)

        # Confirm to submitter
        await interaction.response.send_message(
            f"✅ Report submitted!\n"
            f"**Case #{report['case_id']}** has been created.\n\n"
            f"You can attach additional evidence using:\n"
            f"`!evidence add {report['case_id']}`",
            ephemeral=True,
        )

        # Check escalation alerts
        alert_channel_name = CONFIG["channels"]["moderation_alerts"]
        alert_channel = discord.utils.get(interaction.guild.text_channels, name=alert_channel_name)
        if alert_channel:
            for rule in CONFIG["alert_rules"]:
                if rule.get("collection") != "reports":
                    continue
                count = await db.count_recent_reports(
                    self.reported_member.id, interaction.guild_id, rule["window_days"]
                )
                if count >= rule["count"]:
                    mod_role = discord.utils.get(interaction.guild.roles, name=CONFIG["alert_ping_role"])
                    ping = mod_role.mention if mod_role else f"@{CONFIG['alert_ping_role']}"
                    alert_embed = base_embed(
                        "🚨 Escalation Alert",
                        f"{ping}\n"
                        f"**{self.reported_member.display_name}** has received "
                        f"**{count}** reports within {rule['window_days']} day(s).\n"
                        f"Latest: Case #{report['case_id']}",
                        colour=COLOUR_ERROR,
                    )
                    await alert_channel.send(embed=alert_embed)


def _build_report_embed(
    report: dict,
    reporter: discord.Member,
    reported: discord.Member,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"📢 Report – Case #{report['case_id']}",
        colour=COLOUR_REPORT,
    )
    embed.add_field(name="Reporter",      value=reporter.mention,              inline=True)
    embed.add_field(name="Reported User", value=reported.mention,              inline=True)
    embed.add_field(name="Match ID",      value=report.get("match_id", "N/A"), inline=True)
    embed.add_field(name="Status",        value="Open",                        inline=True)
    embed.add_field(name="Description",   value=report["description"],         inline=False)
    if report.get("evidence_link"):
        embed.add_field(name="Evidence",  value=report["evidence_link"],       inline=False)
    embed.set_thumbnail(url=reported.display_avatar.url)
    embed.set_footer(text=f"Case #{report['case_id']}")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


# ── Report action view (staff buttons on the report embed) ────────────────────

class ReportActionView(discord.ui.View):
    def __init__(self, case_id: str):
        super().__init__(timeout=None)
        self.case_id = case_id

    async def _is_staff(self, interaction: discord.Interaction) -> bool:
        from utils.helpers import has_staff_role
        if not has_staff_role(interaction.user):
            await interaction.response.send_message("⛔ Staff only.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success, custom_id="report_accept")
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._is_staff(interaction):
            return
        await interaction.client.db.update_report_status(self.case_id, "Under Review")
        await interaction.response.send_message(
            f"✅ Case **#{self.case_id}** accepted and is now **Under Review**.",
            ephemeral=True,
        )
        await interaction.message.edit(
            embed=_update_embed_status(interaction.message.embeds[0], "Under Review"),
        )

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.danger, custom_id="report_reject")
    async def reject(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._is_staff(interaction):
            return
        await interaction.client.db.update_report_status(self.case_id, "Closed")
        await interaction.response.send_message(
            f"Case **#{self.case_id}** has been **Rejected / Closed**.",
            ephemeral=True,
        )
        await interaction.message.edit(
            embed=_update_embed_status(interaction.message.embeds[0], "Closed"),
        )

    @discord.ui.button(label="⚖️ Punish", style=discord.ButtonStyle.primary, custom_id="report_punish")
    async def punish(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._is_staff(interaction):
            return
        await interaction.client.db.update_report_status(self.case_id, "Punished")
        await interaction.response.send_message(
            f"Case **#{self.case_id}** marked as **Punished**. "
            f"Apply the punishment manually with `!warn` or `!queueban`.",
            ephemeral=True,
        )
        await interaction.message.edit(
            embed=_update_embed_status(interaction.message.embeds[0], "Punished"),
        )

    @discord.ui.button(label="📋 User History", style=discord.ButtonStyle.secondary, custom_id="report_history")
    async def view_history(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._is_staff(interaction):
            return
        db   = interaction.client.db
        case = await db.get_case(self.case_id)
        if not case:
            await interaction.response.send_message("Case not found.", ephemeral=True)
            return

        reported_id = case.get("reported_id") or case.get("user_id")
        warnings    = await db.get_warnings(reported_id, interaction.guild_id)
        queue_bans  = await db.queue_bans.find(
            {"user_id": reported_id, "guild_id": interaction.guild_id}
        ).sort("created_at", -1).to_list(length=None)

        embed = discord.Embed(
            title=f"📋 History – {case.get('reported_name', str(reported_id))}",
            colour=COLOUR_INFO,
        )
        if warnings:
            lines = [
                f"**#{w['case_id']}** {w['reason']} | {'🟢' if w.get('active') else '⚫'}"
                for w in warnings[:10]
            ]
            embed.add_field(name="Warnings", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Warnings", value="None on record.", inline=False)

        if queue_bans:
            lines = [
                f"**#{qb['case_id']}** | {'Active' if qb.get('active') else 'Ended'}"
                for qb in queue_bans[:5]
            ]
            embed.add_field(name="Queue Bans", value="\n".join(lines), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


def _update_embed_status(embed: discord.Embed, new_status: str) -> discord.Embed:
    """Return a copy of the embed with the Status field updated."""
    new_embed = embed.copy()
    for i, field in enumerate(new_embed.fields):
        if field.name == "Status":
            new_embed.set_field_at(i, name="Status", value=new_status, inline=field.inline)
            break
    return new_embed


# ── Cog ───────────────────────────────────────────────────────────────────────

class Reports(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /report ───────────────────────────────────────────────────────────────
    @app_commands.command(name="report", description="Report a player for a rule violation.")
    @app_commands.describe(user="The player you are reporting")
    async def report(self, interaction: discord.Interaction, user: discord.Member):
        """
        Open the report modal to submit a report against a user.
        """
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You cannot report yourself.", ephemeral=True
            )
            return

        modal = ReportModal(user)
        await interaction.response.send_modal(modal)

    # ── !reportreview [case_id] ───────────────────────────────────────────────
    @commands.command(name="reportreview")
    @staff_only()
    async def report_review(self, ctx: commands.Context, case_id: str):
        """
        Pull up a report for review by its case ID.
        Usage: !reportreview 51832
        """
        report = await self.db.reports.find_one({"case_id": case_id})
        if not report:
            await ctx.send(f"❌ Report **#{case_id}** not found.", delete_after=8)
            return

        guild = ctx.guild
        reporter  = guild.get_member(report["reporter_id"])
        reported  = guild.get_member(report["reported_id"])

        embed = discord.Embed(
            title=f"📢 Report Review – Case #{case_id}",
            colour=COLOUR_REPORT,
        )
        embed.add_field(name="Reporter",    value=reporter.mention if reporter else str(report["reporter_id"]),   inline=True)
        embed.add_field(name="Reported",    value=reported.mention if reported else str(report["reported_id"]),   inline=True)
        embed.add_field(name="Status",      value=report.get("status", "Open"),                                   inline=True)
        embed.add_field(name="Match ID",    value=report.get("match_id", "N/A"),                                  inline=True)
        embed.add_field(name="Submitted",   value=discord.utils.format_dt(report["created_at"], "F"),             inline=True)
        embed.add_field(name="Description", value=report.get("description", "N/A"),                               inline=False)
        if report.get("evidence_link"):
            embed.add_field(name="Evidence", value=report["evidence_link"], inline=False)

        evidence = await self.db.get_evidence(case_id)
        if evidence:
            ev_lines = [
                f"**#{i+1}** {ev.get('link','')} {ev.get('notes','')} "
                f"({len(ev.get('attachments',[]))} file(s))"
                for i, ev in enumerate(evidence)
            ]
            embed.add_field(name="Attached Evidence", value="\n".join(ev_lines), inline=False)

        view = ReportActionView(case_id)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Reports(bot))
