"""
Cog: Escalation
Monitors for escalation patterns and posts alerts to #moderation-alerts.
This cog also provides the alert-check helper used by warnings/reports cogs.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

log = logging.getLogger("cba_bot.escalation")


class Escalation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Escalation(bot))
