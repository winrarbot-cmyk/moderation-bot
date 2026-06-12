"""Cog: EvidenceCommands: !evidence add [case_id], !evidence delete [case_id]"""

from future import annotations

import asyncioimport loggingfrom datetime import datetime, timezone

import discordfrom discord.ext import commands

from utils.helpers import (COLOUR_INFO, COLOUR_SUCCESS, COLOUR_ERROR, COLOUR_WARNING,staff_only, base_embed,)

log = logging.getLogger("cba_bot.evidence")

VALID_VIDEO_DOMAINS = ("youtube.com", "youtu.be","medal.tv","twitch.tv","streamable.com","clips.twitch.tv",)

class EvidenceModal(discord.ui.Modal, title="Add Evidence"):link = discord.ui.TextInput(label="Evidence Link",placeholder="YouTube / Medal / Twitch / Streamable / any URL",required=False,max_length=500,)notes = discord.ui.TextInput(label="Notes",placeholder="Describe the evidence…",style=discord.TextStyle.paragraph,required=False,max_length=1000,)

def init(self, case_id: str):super().init()self.case_id    = case_idself.ev_link    = ""self.ev_notes   = ""self.submitted  = False

async def on_submit(self, interaction: discord.Interaction):self.ev_link   = self.link.value.strip()self.ev_notes  = self.notes.value.strip()self.submitted = Trueawait interaction.response.send_message("📎 Modal received. You have 5 minutes to upload additional files (images, videos, attachments) ""by sending them as messages in this channel. Type done or wait for the timer to finish.",ephemeral=False,)

class EvidenceDeleteView(discord.ui.View):"""Shows a select menu to choose which evidence entry to delete."""

def init(self, evidence_items: list[dict], author_id: int):super().init(timeout=60)self.evidence_items = evidence_itemsself.author_id      = author_idself.to_delete: str | None = None

options = []
for i, ev in enumerate(evidence_items):
    label = f"#{i+1}"
    desc_parts = []
    if ev.get("link"):
        desc_parts.append(ev["link"][:50])
    if ev.get("notes"):
        desc_parts.append(ev["notes"][:40])
    options.append(
        discord.SelectOption(
            label=label,
            value=str(ev["_id"]),
            description=(" | ".join(desc_parts))[:100] or "No details",
        )
    )
self.select_menu.options = options

async def interaction_check(self, interaction: discord.Interaction) -> bool:if interaction.user.id != self.author_id:await interaction.response.send_message("Not your interaction.", ephemeral=True)return Falsereturn True

@discord.ui.select(placeholder="Select evidence to delete…")async def select_menu(self, interaction: discord.Interaction, select: discord.ui.Select):self.to_delete = select.values[0]self.stop()await interaction.response.defer()

class Evidence(commands.Cog):def init(self, bot: commands.Bot):self.bot = bot

@propertydef db(self):return self.bot.db

── !evidence add [case_id] ───────────────────────────────────────────────

@commands.group(name="evidence", invoke_without_command=False)@staff_only()async def evidence_group(self, ctx: commands.Context):"""Evidence management commands."""pass

@evidence_group.command(name="add")@staff_only()async def evidence_add(self, ctx: commands.Context, case_id: str):"""Open a modal to add evidence to a case, then collect file uploads for 5 minutes.Usage: !evidence add 51832"""# Verify case existscase = await self.db.get_case(case_id)if not case:await ctx.send(f"❌ Case #{case_id} not found.", delete_after=8)return

# Send modal via a button (required for prefix commands – we send a button that opens modal)
class ModalButton(discord.ui.View):
    def __init__(self_inner, case_id_: str, author_id: int):
        super().__init__(timeout=120)
        self_inner.case_id_  = case_id_
        self_inner.author_id = author_id
        self_inner.modal: EvidenceModal | None = None

    @discord.ui.button(label="📎 Open Evidence Form", style=discord.ButtonStyle.primary)
    async def open_modal(self_inner, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self_inner.author_id:
            await interaction.response.send_message("Not your interaction.", ephemeral=True)
            return
        modal = EvidenceModal(self_inner.case_id_)
        self_inner.modal = modal
        await interaction.response.send_modal(modal)
        self_inner.stop()

view = ModalButton(case_id, ctx.author.id)
prompt_msg = await ctx.send(
    f"Click below to add evidence to case **#{case_id}**:",
    view=view,
)
await view.wait()
await prompt_msg.edit(view=None)

modal = view.modal
if not modal or not modal.submitted:
    await ctx.send("⏰ Timed out waiting for evidence form.", delete_after=8)
    return

ev_link  = modal.ev_link
ev_notes = modal.ev_notes

# ── Collect attachments for 5 minutes ─────────────────────────────────
collected_attachments: list[str] = []
deadline_msg = await ctx.send(
    f"⏳ Waiting for file uploads for case **#{case_id}** (5 minutes). "
    "Send images/videos as messages or type `done` to finish early."
)

def check(m: discord.Message) -> bool:
    return (
        m.author.id == ctx.author.id
        and m.channel.id == ctx.channel.id
    )

deadline = asyncio.get_event_loop().time() + 300  # 5 minutes

while asyncio.get_event_loop().time() < deadline:
    remaining = deadline - asyncio.get_event_loop().time()
    try:
        msg: discord.Message = await self.bot.wait_for("message", check=check, timeout=remaining)
    except asyncio.TimeoutError:
        break

    if msg.content.strip().lower() == "done":
        await msg.delete()
        break

    # Collect attachment URLs
    for att in msg.attachments:
        collected_attachments.append(att.url)
        log.info("Collected attachment: %s", att.url)

    # Collect any URLs from message text
    words = msg.content.split()
    for word in words:
        if word.startswith("http://") or word.startswith("https://"):
            collected_attachments.append(word)

await deadline_msg.delete()

# ── Save to database ──────────────────────────────────────────────────
ev_doc = await self.db.add_evidence(
    case_id=case_id,
    mod_id=ctx.author.id,
    mod_name=str(ctx.author),
    link=ev_link,
    notes=ev_notes,
    attachments=collected_attachments,
)

embed = base_embed(
    "✅ Evidence Added",
    f"Evidence successfully attached to case **#{case_id}**.",
    colour=COLOUR_SUCCESS,
)
if ev_link:
    embed.add_field(name="Link",  value=ev_link, inline=False)
if ev_notes:
    embed.add_field(name="Notes", value=ev_notes, inline=False)
if collected_attachments:
    embed.add_field(
        name=f"Attachments ({len(collected_attachments)})",
        value="\n".join(collected_attachments[:10]),
        inline=False,
    )
embed.set_footer(text=f"Added by {ctx.author.display_name}")
await ctx.send(embed=embed)

── !evidence delete [case_id] ────────────────────────────────────────────

@evidence_group.command(name="delete")@staff_only()async def evidence_delete(self, ctx: commands.Context, case_id: str):"""Remove an evidence entry from a case via a selection menu.Usage: !evidence delete 51832"""items = await self.db.get_evidence(case_id)if not items:await ctx.send(f"❌ No evidence found for case #{case_id}.", delete_after=8)return

view = EvidenceDeleteView(items, ctx.author.id)
embed = base_embed(
    f"🗑️ Delete Evidence – Case #{case_id}",
    "Select the evidence entry you want to remove:",
    colour=COLOUR_WARNING,
)

# Preview entries
for i, ev in enumerate(items, 1):
    parts = []
    if ev.get("link"):
        parts.append(f"🔗 {ev['link'][:60]}")
    if ev.get("notes"):
        parts.append(f"📝 {ev['notes'][:60]}")
    if ev.get("attachments"):
        parts.append(f"📁 {len(ev['attachments'])} file(s)")
    embed.add_field(
        name=f"Entry #{i}",
        value="\n".join(parts) or "No details.",
        inline=False,
    )

msg = await ctx.send(embed=embed, view=view)
await view.wait()
await msg.edit(view=None)

if not view.to_delete:
    await ctx.send("⏰ Deletion timed out.", delete_after=8)
    return

deleted = await self.db.delete_evidence(view.to_delete)
if deleted:
    await ctx.send(
        f"✅ Evidence entry deleted from case **#{case_id}**.",
        delete_after=10,
    )
else:
    await ctx.send("❌ Could not delete that evidence entry.", delete_after=8)

async def setup(bot: commands.Bot) -> None:await bot.add_cog(Evidence(bot))
