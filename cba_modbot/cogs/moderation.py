"""
Cog: Moderation
General moderation helpers and background tasks:
- Automatic expiry of queue bans (restores channel access)
- Automatic expiry of warnings
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from config.settings import CONFIG
from utils.helpers import (
    COLOUR_INFO, COLOUR_SUCCESS, COLOUR_ERROR,
    staff_only, base_embed,
)

log = logging.getLogger("cba_bot.moderation")


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.expiry_loop.start()

    def cog_unload(self):
        self.expiry_loop.cancel()

    @property
    def db(self):
        return self.bot.db

    # ── Background: expire queue bans & restore access ────────────────────────
    @tasks.loop(minutes=5)
    async def expiry_loop(self):
        """Every 5 minutes, check for expired queue bans and restore access."""
        now = datetime.now(timezone.utc)

        # Fetch all active bans across all guilds
        cursor = self.db.queue_bans.find({
            "active": True,
            "expires_at": {"$lte": now, "$ne": None},
        })
        expired_bans = await cursor.to_list(length=None)

        for ban in expired_bans:
            guild = self.bot.get_guild(ban["guild_id"])
            if not guild:
                continue
            member = guild.get_member(ban["user_id"])
            if member:
                for ch_name in CONFIG["channels"]["queue_channels"]:
                    channel = discord.utils.get(guild.channels, name=ch_name)
                    if channel:
                        try:
                            await channel.set_permissions(member, view_channel=None)
                        except discord.Forbidden:
                            pass
                log.info("Queue ban expired – restored access for %s in %s", member, guild.name)

            # Mark as inactive
            await self.db.queue_bans.update_one(
                {"_id": ban["_id"]},
                {"$set": {"active": False, "expired_at": now}},
            )

        # Expire old warnings
        expired_count = await self.db.expire_old_warnings()
        if expired_count:
            log.info("Expired %d warning(s).", expired_count)

    @expiry_loop.before_loop
    async def before_expiry(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
