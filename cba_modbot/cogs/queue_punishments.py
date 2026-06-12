"""
Cog: Queue Punishments
Commands: !queueban, !unqueueban, !gentimeout
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from config.settings import CONFIG
from utils.helpers import (
    COLOUR_ERROR, COLOUR_SUCCESS, COLOUR_INFO, COLOUR_WARNING,
    staff_only, base_embed, format_duration, parse_duration,
)

log = logging.getLogger("cba_bot.queue_punishments")


class QueuePunishments(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── !queueban @user [duration] [reason] ──────────────────────────────────
    @commands.command(name="queueban")
    @staff_only()
    async def queue_ban(
        self,
        ctx: commands.Context,
        member: discord.Member,
        duration: str,
        *,
        reason: str = "No reason provided.",
    ):
        """
        Restrict a user from all queue channels.
        Does NOT create roles – uses channel permission overrides.
        Usage: !queueban @user 7d Smurfing
               !queueban @user permanent Match Manipulation
        """
        guild_id = ctx.guild.id

        try:
            duration_minutes = parse_duration(duration)
        except ValueError:
            await ctx.send(
                "❌ Invalid duration. Examples: `30m`, `2h`, `7d`, `30d`, `permanent`",
                delete_after=8,
            )
            return

        # Deactivate any existing queue ban first
        await self.db.deactivate_queue_ban(member.id, guild_id)

        # Create warning / case record
        from utils.helpers import categorise_reason
        category = categorise_reason(reason)
        punishment = {
            "type":             "queue_ban",
            "label":            f"Queue Ban ({format_duration(duration_minutes)})",
            "duration_minutes": duration_minutes,
        }
        warning = await self.db.create_warning(
            user_id=member.id,
            user_name=str(member),
            mod_id=ctx.author.id,
            mod_name=str(ctx.author),
            reason=reason,
            category=category,
            punishment=punishment,
            guild_id=guild_id,
            warning_type="queue",
        )

        # Store queue ban record
        await self.db.create_queue_ban(
            user_id=member.id,
            user_name=str(member),
            mod_id=ctx.author.id,
            mod_name=str(ctx.author),
            reason=reason,
            duration_minutes=duration_minutes,
            case_id=warning["case_id"],
            guild_id=guild_id,
        )

        # Remove queue channel access
        removed = await self._remove_queue_access(ctx.guild, member)

        # Record in punishments
        await self.db.create_punishment(
            user_id=member.id,
            user_name=str(member),
            mod_id=ctx.author.id,
            mod_name=str(ctx.author),
            punishment_type="queue_ban",
            reason=reason,
            duration_minutes=duration_minutes,
            case_id=warning["case_id"],
            guild_id=guild_id,
        )

        embed = discord.Embed(
            title="🚫 Queue Ban Issued",
            colour=COLOUR_ERROR,
        )
        embed.add_field(name="User",       value=member.mention,                        inline=True)
        embed.add_field(name="Duration",   value=format_duration(duration_minutes),     inline=True)
        embed.add_field(name="Case ID",    value=f"#{warning['case_id']}",              inline=True)
        embed.add_field(name="Reason",     value=reason,                                inline=False)
        embed.add_field(name="Channels",   value=f"Removed from {removed} channel(s).", inline=False)
        embed.set_footer(text=f"Issued by {ctx.author.display_name}")
        embed.timestamp = datetime.now(timezone.utc)

        if duration_minutes:
            expires = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
            embed.add_field(
                name="Expires",
                value=discord.utils.format_dt(expires, "F"),
                inline=False,
            )

        await ctx.send(embed=embed)
        log.info("Queue ban issued: %s → %s (%s)", ctx.author, member, format_duration(duration_minutes))

    # ── !unqueueban @user ─────────────────────────────────────────────────────
    @commands.command(name="unqueueban")
    @staff_only()
    async def unqueue_ban(self, ctx: commands.Context, member: discord.Member):
        """
        Remove an active queue ban and restore access to queue channels.
        Usage: !unqueueban @user
        """
        guild_id = ctx.guild.id

        deactivated = await self.db.deactivate_queue_ban(member.id, guild_id)
        restored    = await self._restore_queue_access(ctx.guild, member)

        if not deactivated and not restored:
            await ctx.send(
                f"⚠️ No active queue ban found for {member.mention}.",
                delete_after=8,
            )
            return

        embed = base_embed(
            "✅ Queue Ban Removed",
            f"{member.mention}'s queue ban has been lifted. Access restored to {restored} channel(s).",
            colour=COLOUR_SUCCESS,
        )
        embed.set_footer(text=f"Removed by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    # ── !gentimeout @user [duration] [reason] ─────────────────────────────────
    @commands.command(name="gentimeout")
    @staff_only()
    async def general_timeout(
        self,
        ctx: commands.Context,
        member: discord.Member,
        duration: str,
        *,
        reason: str = "No reason provided.",
    ):
        """
        Apply Discord's native timeout to a user. No role creation.
        Usage: !gentimeout @user 24h Toxicity
        """
        try:
            duration_minutes = parse_duration(duration)
        except ValueError:
            await ctx.send(
                "❌ Invalid duration. Examples: `30m`, `2h`, `24h`, `7d`.",
                delete_after=8,
            )
            return

        if duration_minutes is None:
            await ctx.send(
                "❌ General timeouts cannot be permanent. Use `!queueban` for permanent bans.",
                delete_after=8,
            )
            return

        # Discord timeout max is 28 days
        if duration_minutes > 40320:
            await ctx.send(
                "❌ Maximum timeout duration is 28 days (40320 minutes).",
                delete_after=8,
            )
            return

        until = discord.utils.utcnow() + timedelta(minutes=duration_minutes)

        try:
            await member.timeout(until, reason=f"[{ctx.author}] {reason}")
        except discord.Forbidden:
            await ctx.send(
                "❌ I don't have permission to timeout this member.",
                delete_after=8,
            )
            return
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to apply timeout: {e}", delete_after=8)
            return

        # Create a record
        from utils.helpers import categorise_reason
        punishment = {
            "type":             "general_timeout",
            "label":            f"Timeout ({format_duration(duration_minutes)})",
            "duration_minutes": duration_minutes,
        }
        warning = await self.db.create_warning(
            user_id=member.id,
            user_name=str(member),
            mod_id=ctx.author.id,
            mod_name=str(ctx.author),
            reason=reason,
            category=categorise_reason(reason),
            punishment=punishment,
            guild_id=ctx.guild.id,
            warning_type="community",
        )
        await self.db.create_punishment(
            user_id=member.id,
            user_name=str(member),
            mod_id=ctx.author.id,
            mod_name=str(ctx.author),
            punishment_type="general_timeout",
            reason=reason,
            duration_minutes=duration_minutes,
            case_id=warning["case_id"],
            guild_id=ctx.guild.id,
        )

        embed = discord.Embed(
            title="⏸️ General Timeout Applied",
            colour=COLOUR_WARNING,
        )
        embed.add_field(name="User",     value=member.mention,                     inline=True)
        embed.add_field(name="Duration", value=format_duration(duration_minutes),  inline=True)
        embed.add_field(name="Case ID",  value=f"#{warning['case_id']}",           inline=True)
        embed.add_field(name="Reason",   value=reason,                             inline=False)
        embed.add_field(name="Expires",  value=discord.utils.format_dt(until, "F"), inline=False)
        embed.set_footer(text=f"Issued by {ctx.author.display_name}")
        embed.timestamp = datetime.now(timezone.utc)
        await ctx.send(embed=embed)

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _remove_queue_access(self, guild: discord.Guild, member: discord.Member) -> int:
        """Remove ViewChannel from all configured queue channels. Returns count modified."""
        count = 0
        for ch_name in CONFIG["channels"]["queue_channels"]:
            channel = discord.utils.get(guild.channels, name=ch_name)
            if channel:
                try:
                    await channel.set_permissions(member, view_channel=False)
                    count += 1
                except discord.Forbidden:
                    log.warning("Cannot set permissions in #%s", ch_name)
        return count

    async def _restore_queue_access(self, guild: discord.Guild, member: discord.Member) -> int:
        """Restore ViewChannel in all configured queue channels. Returns count modified."""
        count = 0
        for ch_name in CONFIG["channels"]["queue_channels"]:
            channel = discord.utils.get(guild.channels, name=ch_name)
            if channel:
                try:
                    await channel.set_permissions(member, view_channel=None)  # remove override
                    count += 1
                except discord.Forbidden:
                    log.warning("Cannot restore permissions in #%s", ch_name)
        return count


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(QueuePunishments(bot))
