"""
Premium Discord DM Report Bot
"""

import discord
from discord.ext import commands
import os
import logging
import threading
from flask import Flask

from db import setup, add_report, get_reports, delete_report

# ------------------ LOGGING ------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("dungeonkeeper")

# ------------------ ENV ------------------
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN")

# ------------------ KEEP ALIVE (FLASK) ------------------
app = Flask(__name__)
_web_started = False


@app.route("/")
def home():
    return "Bot is alive"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    global _web_started
    if not _web_started:
        threading.Thread(target=run_web, daemon=True).start()
        _web_started = True


# ------------------ BOT CLASS ------------------
class DungeonKeeper(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(command_prefix="!", intents=intents)

    async def on_ready(self):
        setup()          # create DB
        keep_alive()     # start Flask
        log.info(f"{self.user} is online")


bot = DungeonKeeper()

# ------------------ COMMANDS ------------------

@bot.command(name="report")
async def report_cmd(ctx, user: discord.User, *, reason: str):
    try:
        report_id = add_report(str(user.id), reason.strip())
        await ctx.send(f"✅ Report saved (ID: {report_id}) for {user}")
    except Exception as e:
        log.exception("Error saving report")
        await ctx.send("❌ Failed to save report")


@bot.command(name="reports")
async def reports_cmd(ctx):
    try:
        data = get_reports()
    except Exception:
        log.exception("Error fetching reports")
        await ctx.send("❌ Database error")
        return

    if not data:
        await ctx.send("No reports found.")
        return

    msg = ""
    for r in data[:20]:
        msg += f"ID: {r[0]} | User: {r[1]}\nReason: {r[2]}\n\n"

    await ctx.send(msg[:1900])


@bot.command(name="delreport")
async def delreport_cmd(ctx, report_id: int):
    try:
        delete_report(report_id)
        await ctx.send("✅ Report deleted")
    except Exception:
        log.exception("Error deleting report")
        await ctx.send("❌ Failed to delete report")


# ------------------ RUN ------------------
if __name__ == "__main__":
    bot.run(TOKEN)
