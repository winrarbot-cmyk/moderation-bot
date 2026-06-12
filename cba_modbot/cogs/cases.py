"""
Cog: Cases
Commands: !case [id], !case note [id] [note]
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

from utils.helpers import (
    COLOUR_CASE, COLOUR_INFO, COLOUR_ERROR, COLOUR_SUCCESS,
    staff_only, base_embed, case_embed,
)

log = logging.getLogger("cba_bot.cases")

CASE_STATUSES = ("Open", "Under Review", "Punished", "Appealed", "Closed")


class CaseStatusView(discord.ui.View):
    """Dropdown to change a case status."""

    def __init__(self, case_id: str, author_id: int):
        super().__init__(timeout=60)
        self.case_id   = case_id
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Not your interaction.", ephemeral=True)
            return False
        return True

    @discord.ui.select(
        placeholder="Change case status…",
        options=[discord.SelectOption(label=s, value=s) for s in CASE_STATUSES],
    )
    async def change_status(self, interaction: discord.Interaction, select: discord.ui.Select):
        new_status = select.values[0]
        await interaction.client.db.update_case_status(self.case_id, new_status)
        await interaction.response.send_message(
            f"✅ Case **#{self.case_id}** status updated to **{new_status}**.",
            ephemeral=True,
        )
        self.stop()


class Cases(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── !case [id] ────────────────────────────────────────────────────────────
    @commands.group(name="case", invoke_without_command=True)
    @staff_only()
    async def case_cmd(self, ctx: commands.Context, case_id: str):
        """
        Display full details of a case.
        Usage: !case 51832
        """
        case = await self.db.get_case(case_id)
        if not case:
            await ctx.send(f"❌ Case **#{case_id}** not found.", delete_after=8)
            return

        embed = case_embed(case)

        # Notes
        notes = case.get("notes", [])
        if notes:
            note_lines = [
                f"**{n.get('mod_name','?')}** ({discord.utils.format_dt(n['added_at'], 'd')}): {n['note']}"
                for n in notes
            ]
            embed.add_field(name="📝 Notes", value="\n".join(note_lines), inline=False)

        # Appeals
        appeal_ids = case.get("appeal_ids", [])
        if appeal_ids:
            embed.add_field(name="📨 Appeals", value=", ".join(f"#{a}" for a in appeal_ids), inline=False)

        # Evidence
        evidence = await self.db.get_evidence(case_id)
        if evidence:
            ev_lines = []
            for i, ev in enumerate(evidence, 1):
                parts = []
                if ev.get("link"):
                    parts.append(f"🔗 {ev['link']}")
                if ev.get("notes"):
                    parts.append(f"📝 {ev['notes']}")
                ev_lines.append(f"**#{i}** {' | '.join(parts)}")
            embed.add_field(name="📎 Evidence", value="\n".join(ev_lines), inline=False)
        else:
            embed.add_field(name="📎 Evidence", value="None attached.", inline=False)

        view = CaseStatusView(case_id, ctx.author.id)
        await ctx.send(embed=embed, view=view)

    # ── !case note [id] [note] ────────────────────────────────────────────────
    @case_cmd.command(name="note")
    @staff_only()
    async def case_note(self, ctx: commands.Context, case_id: str, *, note: str):
        """
        Add an internal note to a case.
        Usage: !case note 51832 User was warned verbally beforehand.
        """
        case = await self.db.get_case(case_id)
        if not case:
            await ctx.send(f"❌ Case **#{case_id}** not found.", delete_after=8)
            return

        await self.db.add_case_note(
            case_id,
            mod_id=ctx.author.id,
            mod_name=str(ctx.author),
            note=note,
        )

        embed = base_embed(
            "📝 Note Added",
            f"Note added to case **#{case_id}**.",
            colour=COLOUR_SUCCESS,
        )
        embed.add_field(name="Note", value=note, inline=False)
        embed.set_footer(text=f"By {ctx.author.display_name}")
        await ctx.send(embed=embed)

    # ── !history @user ────────────────────────────────────────────────────────
    @commands.command(name="history")
    @staff_only()
    async def history(self, ctx: commands.Context, member: discord.Member):
        """
        Show all cases for a user (staff view).
        Usage: !history @user
        """
        guild_id = ctx.guild.id
        from motor.motor_asyncio import AsyncIOMotorCursor

        cursor = self.db.cases.find(
            {"user_id": member.id, "guild_id": guild_id}
        ).sort("created_at", -1)
        cases = await cursor.to_list(length=None)

        if not cases:
            await ctx.send(f"No cases found for **{member.display_name}**.", delete_after=8)
            return

        embed = discord.Embed(
            title=f"📁 Case History – {member.display_name}",
            colour=COLOUR_CASE,
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        for c in cases[:20]:  # Discord 25-field limit
            punishment = c.get("punishment", {})
            status     = c.get("status", "Open")
            status_icon = {
                "Open":         "🔵",
                "Under Review": "🟡",
                "Punished":     "🔴",
                "Appealed":     "🟣",
                "Closed":       "⚫",
            }.get(status, "⚪")

            embed.add_field(
                name=f"{status_icon} #{c['case_id']} – {c.get('reason','N/A')}",
                value=(
                    f"Punishment: **{punishment.get('label','N/A')}** | "
                    f"Mod: {c.get('mod_name','?')} | "
                    f"{discord.utils.format_dt(c['created_at'], 'd')}"
                ),
                inline=False,
            )

        embed.set_footer(text=f"Total cases: {len(cases)} | Requested by {ctx.author.display_name}")
        embed.timestamp = datetime.now(timezone.utc)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Cases(bot))
