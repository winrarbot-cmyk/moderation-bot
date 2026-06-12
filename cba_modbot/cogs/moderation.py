"""
Cog: Moderation
Handles automatic expiry systems for punishments
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from config.settings import CONFIG

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

    # ── Background task ────────────────────────────────────────────────
    @tasks.loop(minutes=5)
    async def expiry_loop(self):
        now = datetime.now(timezone.utc)

        # ─────────────────────────────────────────────
        # 1. EXPIRE QUEUE BANS
        # ─────────────────────────────────────────────
        cursor = self.db.queue_bans.find({
            "active": True,
            "expires_at": {"$ne": None, "$lte": now},
        })

        expired_bans = await cursor.to_list(length=None)

        for ban in expired_bans:
            guild = self.bot.get_guild(ban["guild_id"])
            if not guild:
                continue

            member = guild.get_member(ban["user_id"])

            if member:
                await self._restore_queue_access(guild, member)
                log.info(
                    "Queue ban expired → restored access: %s in %s",
                    member,
                    guild.name
                )

            await self.db.queue_bans.update_one(
                {"case_id": ban["case_id"]},   # FIXED: use case_id instead of _id
                {"$set": {
                    "active": False,
                    "expired_at": now
                }},
            )

        # ─────────────────────────────────────────────
        # 2. EXPIRE WARNINGS
        # ─────────────────────────────────────────────
        expired_count = await self.db.expire_old_warnings()
        if expired_count:
            log.info("Expired %d warning(s).", expired_count)

    @expiry_loop.before_loop
    async def before_expiry(self):
        await self.bot.wait_until_ready()

    # ── Helpers ─────────────────────────────────────────────────────────
    async def _restore_queue_access(self, guild: discord.Guild, member: discord.Member):
        for ch_name in CONFIG["channels"]["queue_channels"]:
            channel = discord.utils.get(guild.channels, name=ch_name)
            if not channel:
                continue

            try:
                # CLEAN reset instead of overwrite None
                await channel.set_permissions(member, overwrite=None)
            except discord.Forbidden:
                log.warning("Missing permission in #%s", ch_name)
