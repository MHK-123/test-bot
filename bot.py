"""
Premium Discord DM Report Bot
Copyright (c) 2026 Your Name

This software is licensed for personal server use only.
Redistribution or resale of this source code is prohibited.
"""

import discord
from discord.ext import commands
import os
import logging
from typing import Optional

from db import setup, add_report, get_reports, delete_report

log = logging.getLogger("dungeonkeeper")

TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("Missing required environment variable: DISCORD_TOKEN")


class DungeonKeeper(commands.Bot):

    def __init__(self):
        # Intents: message_content is required for prefix commands like !report
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(command_prefix="!", intents=intents)

    async def on_ready(self):
        # Ensure SQLite database and tables exist
        setup()
        log.info("%s is online", self.user)



bot = DungeonKeeper()


@bot.command(name="report")
async def report_cmd(ctx: commands.Context, user: discord.User, *, reason: str):
    """
    Usage: !report <user> <reason>
    Example: !report @SomeUser Spamming in general chat
    """
    try:
        report_id = add_report(str(user.id), reason.strip())
    except Exception:
        log.exception("Failed to add report")
        await ctx.send("❌ Failed to save report (database error).")
        return

    await ctx.send(f"✅ Report saved with ID **{report_id}** for **{user}**.")


@bot.command(name="reports")
async def reports_cmd(ctx: commands.Context):
    """Usage: !reports → shows all saved reports."""
    try:
        reports = get_reports()
    except Exception:
        log.exception("Failed to load reports")
        await ctx.send("❌ Failed to load reports (database error).")
        return

    if not reports:
        await ctx.send("No reports found.")
        return

    lines: list[str] = []
    for r in reports[:25]:  # keep message readable
        lines.append(f"**{r['id']}** | user_id=`{r['user_id']}` | {r['created_at']}\n- {r['reason']}")

    msg = "\n\n".join(lines)
    await ctx.send(msg[:1900])


@bot.command(name="delreport")
async def delreport_cmd(ctx: commands.Context, report_id: str):
    """Usage: !delreport <id> → deletes one report by ID."""
    try:
        rid = int(report_id)
    except ValueError:
        await ctx.send("❌ Invalid ID. Example: `!delreport 12`")
        return

    try:
        ok = delete_report(rid)
    except Exception:
        log.exception("Failed deleting report id=%s", rid)
        await ctx.send("❌ Failed to delete report (database error).")
        return

    await ctx.send("✅ Deleted." if ok else "⚠ No report found with that ID.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    bot.run(TOKEN)
