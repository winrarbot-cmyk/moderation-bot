"""Cog: EscalationMonitors for escalation patterns and posts alerts to #moderation-alerts.This cog also provides the alert-check helper used by warnings/reports cogs."""

from future import annotations

import logging

import discordfrom discord.ext import commands

log = logging.getLogger("cba_bot.escalation")

class Escalation(commands.Cog):def init(self, bot: commands.Bot):self.bot = bot

@propertydef db(self):return self.bot.db

async def setup(bot: commands.Bot) -> None:await bot.add_cog(Escalation(bot))
