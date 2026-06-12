"""
Cog: Appeals
Commands: !appeal (all users), !appealreview [appeal_id] (staff)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

from config.settings import CONFIG
from utils.helpers import (
    COLOUR_APPEAL, COLOUR_SUCCESS, COLOUR_ERROR, COLOUR_WARNING,
    staff_only, base_embed,
)

log = logging.getLogger("cba_bot.appeals")


# ── Modal ─────────────────────────────────────────────────────────────────────

class AppealModal(discord.ui.Modal, title="Submit an Appeal"):
    case_id_input = discord.ui.TextInput(
        label="Case ID",
        placeholder="5-digit case number, e.g. 51832",
        required=True,
        max_length=10,
    )
    reason = discord.ui.TextInput(
        label="Reason for Appeal",
        placeholder="Explain why you believe this punishment is unjust…",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )
    additional_info = discord.ui.TextInput(
        label="Additional Information",
        placeholder="Any extra context, witnesses, or evidence…",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        db       = interaction.client.db
        case_id  = self.case_id_input.value.strip()

        # Verify case exists
        case = await db.get_case(case_id)
        if not case:
            await interaction.response.send_message(
                f"❌ Case **#{case_id}** not found. Please check the case number.",
                ephemeral=True,
            )
            return

        # Verify the user owns the case (or is appealing a report against them)
        if case["user_id"] != interaction.user.id:
            await interaction.response.send_message(
                "❌ You can only appeal cases that were issued to you.",
                ephemeral=True,
            )
            return

        # Prevent duplicate open appeals for the same case
        existing = await db.appeals.find_one(
            {"case_id": case_id, "user_id": interaction.user.id, "status": "Pending"}
        )
        if existing:
            await interaction.response.send_message(
                f"⚠️ You already have a pending appeal for case **#{case_id}** (Appeal #{existing['appeal_id']}).",
                ephemeral=True,
            )
            return

        appeal = await db.create_appeal(
            user_id=interaction.user.id,
            user_name=str(interaction.user),
            case_id=case_id,
            reason=self.reason.value.strip(),
            additional_info=self.additional_info.value.strip(),
            guild_id=interaction.guild_id,
        )

        # Post to #appeals channel
        appeals_channel_name = CONFIG["channels"]["appeals"]
        appeals_channel = discord.utils.get(
            interaction.guild.text_channels, name=appeals_channel_name
        )
        if appeals_channel:
            embed = _build_appeal_embed(appeal, case, interaction.user)
            view  = AppealActionView(appeal["appeal_id"])
            await appeals_channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ Appeal submitted!\n"
            f"**Appeal #{appeal['appeal_id']}** for Case **#{case_id}** is now pending review.\n"
            f"You will be notified of the outcome.",
            ephemeral=True,
        )


def _build_appeal_embed(appeal: dict, case: dict, user: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title=f"📨 Appeal #{appeal['appeal_id']} – Case #{appeal['case_id']}",
        colour=COLOUR_APPEAL,
    )
    embed.add_field(name="Appellant",  value=user.mention,                    inline=True)
    embed.add_field(name="Case ID",    value=f"#{appeal['case_id']}",         inline=True)
    embed.add_field(name="Status",     value="Pending",                       inline=True)
    embed.add_field(name="Offence",    value=case.get("reason", "N/A"),       inline=True)
    embed.add_field(name="Punishment", value=case.get("punishment", {}).get("label", "N/A"), inline=True)
    embed.add_field(name="Reason for Appeal", value=appeal["reason"],         inline=False)
    if appeal.get("additional_info"):
        embed.add_field(name="Additional Info", value=appeal["additional_info"], inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"Appeal #{appeal['appeal_id']}")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


# ── Staff review view ──────────────────────────────────────────────────────────

class AppealActionView(discord.ui.View):
    def __init__(self, appeal_id: str):
        super().__init__(timeout=None)
        self.appeal_id = appeal_id

    async def _check_staff(self, interaction: discord.Interaction) -> bool:
        from utils.helpers import has_staff_role
        if not has_staff_role(interaction.user):
            await interaction.response.send_message("⛔ Staff only.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Accept Appeal", style=discord.ButtonStyle.success, custom_id="appeal_accept")
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._check_staff(interaction):
            return
        await self._update(interaction, "Accepted")

    @discord.ui.button(label="❌ Reject Appeal", style=discord.ButtonStyle.danger, custom_id="appeal_reject")
    async def reject(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._check_staff(interaction):
            return
        await self._update(interaction, "Rejected")

    @discord.ui.button(label="⬇️ Reduce Punishment", style=discord.ButtonStyle.primary, custom_id="appeal_reduce")
    async def reduce(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._check_staff(interaction):
            return
        await self._update(interaction, "Reduced")

    async def _update(self, interaction: discord.Interaction, verdict: str) -> None:
        class NoteModal(discord.ui.Modal, title=f"Appeal {verdict} – Add Note"):
            note = discord.ui.TextInput(
                label="Review Note (optional)",
                style=discord.TextStyle.paragraph,
                required=False,
                max_length=500,
            )
            async def on_submit(self_inner, inter: discord.Interaction):
                await inter.response.defer()

        modal = NoteModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        db = interaction.client.db
        appeal = await db.get_appeal(self.appeal_id)
        if not appeal:
            return

        await db.update_appeal_status(
            self.appeal_id,
            status=verdict,
            reviewer_id=interaction.user.id,
            reviewer_name=str(interaction.user),
            review_note=modal.note.value.strip() if modal.note.value else "",
        )

        # Update the embed in the appeals channel
        embed = interaction.message.embeds[0].copy() if interaction.message.embeds else discord.Embed()
        for i, field in enumerate(embed.fields):
            if field.name == "Status":
                embed.set_field_at(i, name="Status", value=verdict, inline=field.inline)
                break
        embed.colour = {
            "Accepted": COLOUR_SUCCESS,
            "Rejected": COLOUR_ERROR,
            "Reduced":  COLOUR_WARNING,
        }.get(verdict, COLOUR_APPEAL)

        try:
            await interaction.message.edit(embed=embed, view=None)
        except discord.HTTPException:
            pass

        # Notify the appellant
        guild = interaction.guild
        appellant = guild.get_member(appeal["user_id"])
        if appellant:
            try:
                dm_embed = base_embed(
                    f"📨 Appeal #{self.appeal_id} – {verdict}",
                    f"Your appeal for Case **#{appeal['case_id']}** has been **{verdict}**.",
                    colour={
                        "Accepted": COLOUR_SUCCESS,
                        "Rejected": COLOUR_ERROR,
                        "Reduced":  COLOUR_WARNING,
                    }.get(verdict, COLOUR_APPEAL),
                )
                if modal.note.value:
                    dm_embed.add_field(name="Staff Note", value=modal.note.value, inline=False)
                await appellant.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        await interaction.followup.send(
            f"Appeal **#{self.appeal_id}** marked as **{verdict}**.",
            ephemeral=True,
        )


# ── Cog ───────────────────────────────────────────────────────────────────────

class Appeals(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── !appeal ───────────────────────────────────────────────────────────────
    @commands.command(name="appeal")
    async def appeal(self, ctx: commands.Context):
        """
        Submit an appeal for a case. Opens an interactive form.
        Usage: !appeal
        """
        # Trigger modal via a button (prefix commands can't open modals directly)
        class ModalTrigger(discord.ui.View):
            def __init__(self_inner, author_id: int):
                super().__init__(timeout=120)
                self_inner.author_id = author_id

            @discord.ui.button(label="📨 Open Appeal Form", style=discord.ButtonStyle.primary)
            async def open(self_inner, interaction: discord.Interaction, _: discord.ui.Button):
                if interaction.user.id != self_inner.author_id:
                    await interaction.response.send_message("Not your interaction.", ephemeral=True)
                    return
                await interaction.response.send_modal(AppealModal())
                self_inner.stop()

        view = ModalTrigger(ctx.author.id)
        msg  = await ctx.send(
            "Click below to open the appeal form:", view=view
        )
        await view.wait()
        await msg.edit(view=None)

    # ── !appealreview [appeal_id] ─────────────────────────────────────────────
    @commands.command(name="appealreview")
    @staff_only()
    async def appeal_review(self, ctx: commands.Context, appeal_id: str):
        """
        Review a specific appeal by its ID.
        Usage: !appealreview 51832
        """
        appeal = await self.db.get_appeal(appeal_id)
        if not appeal:
            await ctx.send(f"❌ Appeal **#{appeal_id}** not found.", delete_after=8)
            return

        case = await self.db.get_case(appeal["case_id"])
        guild = ctx.guild
        user  = guild.get_member(appeal["user_id"])

        embed = discord.Embed(
            title=f"📨 Appeal #{appeal_id} – Case #{appeal['case_id']}",
            colour=COLOUR_APPEAL,
        )
        embed.add_field(name="Appellant", value=user.mention if user else str(appeal["user_id"]), inline=True)
        embed.add_field(name="Case ID",   value=f"#{appeal['case_id']}",                         inline=True)
        embed.add_field(name="Status",    value=appeal.get("status","Pending"),                  inline=True)
        if case:
            embed.add_field(name="Offence",    value=case.get("reason","N/A"),                    inline=True)
            embed.add_field(name="Punishment", value=case.get("punishment",{}).get("label","N/A"),inline=True)
        embed.add_field(name="Reason",         value=appeal["reason"],                            inline=False)
        if appeal.get("additional_info"):
            embed.add_field(name="Additional Info", value=appeal["additional_info"],              inline=False)
        embed.add_field(
            name="Submitted",
            value=discord.utils.format_dt(appeal["created_at"], "F"),
            inline=True,
        )
        if appeal.get("reviewed_by"):
            embed.add_field(name="Reviewed By", value=f"<@{appeal['reviewed_by']}>", inline=True)
            embed.add_field(name="Reviewed At",
                            value=discord.utils.format_dt(appeal["reviewed_at"], "F"), inline=True)
        if appeal.get("review_note"):
            embed.add_field(name="Review Note", value=appeal["review_note"], inline=False)

        view = AppealActionView(appeal_id)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Appeals(bot))
