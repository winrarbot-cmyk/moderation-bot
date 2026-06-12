"""Cog: ModerationHandles automatic expiry systems for punishments"""

from future import annotations

import loggingfrom datetime import datetime, timezone

import discordfrom discord.ext import commands, tasks

from config.settings import CONFIG

log = logging.getLogger("cba_bot.moderation")

class Moderation(commands.Cog):def init(self, bot: commands.Bot):self.bot = botself.expiry_loop.start()

def cog_unload(self):self.expiry_loop.cancel()

@propertydef db(self):return self.bot.db

── Background task ────────────────────────────────────────────────

@tasks.loop(minutes=5)async def expiry_loop(self):now = datetime.now(timezone.utc)

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

@expiry_loop.before_loopasync def before_expiry(self):await self.bot.wait_until_ready()

── Helpers ─────────────────────────────────────────────────────────

async def _restore_queue_access(self, guild: discord.Guild, member: discord.Member):
    for ch_id in CONFIG["channels"]["queue_channels"]:
        channel = guild.get_channel(ch_id)
        if not channel:
            continue

        try:
            # CLEAN reset instead of overwrite None
            await channel.set_permissions(member, overwrite=None)
        except discord.Forbidden:
            log.warning("Missing permission in channel ID %s", ch_id)
