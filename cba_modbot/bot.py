"""
CBA Moderation Bot - Main Entry Point
Discord.py 2.x + Motor (async MongoDB)
"""

import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient

from config.settings import CONFIG
from utils.database import Database

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("cba_bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("cba_bot")

# ── Intents ───────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True


# ── Bot class ─────────────────────────────────────────────────────────────────
class CBABot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=CONFIG["prefix"],
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )
        self.db: Database | None = None
        self._motor_client: AsyncIOMotorClient | None = None

    # ── Setup hook (runs before login) ───────────────────────────────────────
    async def setup_hook(self) -> None:
        # Connect to MongoDB
        self._motor_client = AsyncIOMotorClient(CONFIG["mongodb_uri"])
        self.db = Database(self._motor_client[CONFIG["mongodb_db"]])
        await self.db.create_indexes()
        log.info("MongoDB connected – database: %s", CONFIG["mongodb_db"])

        # Load all cogs
        cogs = [
            "cogs.moderation",
            "cogs.warnings",
            "cogs.cases",
            "cogs.evidence",
            "cogs.queue_punishments",
            "cogs.reports",
            "cogs.appeals",
            "cogs.escalation",
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                log.info("Loaded cog: %s", cog)
            except Exception as exc:
                log.error("Failed to load cog %s: %s", cog, exc, exc_info=True)

        # Sync slash commands
        try:
            synced = await self.tree.sync()
            log.info("Synced %d slash command(s)", len(synced))
        except Exception as exc:
            log.error("Slash command sync failed: %s", exc)

    async def on_ready(self) -> None:
        log.info("Bot ready – logged in as %s (ID %s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="CBA | !help",
            )
        )

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You do not have permission to use this command.", delete_after=8)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.", delete_after=8)
        elif isinstance(error, commands.CommandNotFound):
            pass  # Silently ignore unknown commands
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: `{error.param.name}`", delete_after=8)
        else:
            log.error("Unhandled command error in %s: %s", ctx.command, error, exc_info=error)

    async def close(self) -> None:
        if self._motor_client:
            self._motor_client.close()
        await super().close()


# ── Run ───────────────────────────────────────────────────────────────────────
async def main() -> None:
    token = CONFIG.get("token") or os.environ.get("DISCORD_TOKEN")
    if not token:
        log.critical("No Discord token found. Set DISCORD_TOKEN in .env or config.")
        sys.exit(1)

    bot = CBABot()
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
