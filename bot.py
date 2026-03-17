"""
Premium Discord DM Report Bot
Copyright (c) 2026 Your Name

This software is licensed for personal server use only.
Redistribution or resale of this source code is prohibited.
"""

import discord
from discord.ext import commands
import os
from datetime import datetime, timedelta
import logging
from typing import Any, Optional

from db import SupabaseStore, parse_user_id, require_env

log = logging.getLogger("dungeonkeeper")

TOKEN = require_env("DISCORD_TOKEN")
STAFF_CHANNEL_ID = int(require_env("STAFF_CHANNEL_ID"))
STAFF_ROLE_IDS = [int(x.strip()) for x in require_env("STAFF_ROLE_IDS").split(",") if x.strip()]

SUPABASE_URL = require_env("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = require_env("SUPABASE_SERVICE_ROLE_KEY")

DM_MENU_COOLDOWN_SECONDS = int(os.environ.get("DM_MENU_COOLDOWN_SECONDS", "30"))
PROCEED_SESSION_TTL_SECONDS = int(os.environ.get("PROCEED_SESSION_TTL_SECONDS", "300"))


class DungeonKeeper(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(command_prefix="!", intents=intents)

        self.store = SupabaseStore(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        self._dm_menu_last_sent: dict[int, datetime] = {}

    async def setup_hook(self) -> None:
        # Register persistent view so staff buttons work after restarts.
        self.add_view(StaffPersistentView(self))

    async def on_ready(self):
        log.info("%s is online", self.user)

    def is_staff(self, member):
        return any(role.id in STAFF_ROLE_IDS for role in member.roles)

    async def on_message(self, message):

        if message.author.bot:
            return

        if isinstance(message.channel, discord.DMChannel):

            if await self.store.is_blacklisted(message.author.id):
                return

            try:
                if await self.store.pop_session_if_active(message.author.id):
                    await self.create_case_from_dm(message)
                    return
            except Exception:
                log.exception("Failed checking/consuming DM session for user_id=%s", message.author.id)
                try:
                    await message.author.send("Sorry—something went wrong on our side. Please try again later.")
                except Exception:
                    pass
                return

            last = self._dm_menu_last_sent.get(message.author.id)
            if last and (datetime.utcnow() - last).total_seconds() < DM_MENU_COOLDOWN_SECONDS:
                return

            embed = discord.Embed(
                title="🛡️ DungeonKeeper Report System",
                color=discord.Color.blurple(),
                description=(
                    "**Report rule violations safely to staff**\n\n"
                    "📋 Include:\n"
                    "• Username of the member\n"
                    "• What they did\n"
                    "• Screenshot evidence\n\n"
                    "⚠ False reports may result in punishment."
                )
            )

            view = StartView(self)

            try:
                await message.author.send(embed=embed, view=view)
                self._dm_menu_last_sent[message.author.id] = datetime.utcnow()
            except Exception:
                log.exception("Failed sending DM menu to user_id=%s", message.author.id)
            return

        await self.process_commands(message)

    async def create_case_from_dm(self, message: discord.Message):
        staff_channel = self.get_channel(STAFF_CHANNEL_ID)
        if staff_channel is None or not isinstance(staff_channel, (discord.TextChannel, discord.Thread)):
            log.error("STAFF_CHANNEL_ID=%s not found/invalid", STAFF_CHANNEL_ID)
            try:
                await message.author.send("Sorry—staff channel is not configured correctly. Please contact staff.")
            except Exception:
                pass
            return

        attachment_urls = [a.url for a in message.attachments]
        try:
            case_id = await self.store.create_case(
                reporter_id=message.author.id,
                report_content=message.content,
                attachment_urls=attachment_urls,
            )
        except Exception:
            log.exception("Failed creating case in Supabase for user_id=%s", message.author.id)
            try:
                await message.author.send("Sorry—your report could not be saved. Please try again later.")
            except Exception:
                pass
            return

        embed = discord.Embed(
            title=f"🚨 New Report Case #{case_id}",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(
            name="Reporter",
            value=f"{message.author} ({message.author.id})",
            inline=False
        )

        embed.add_field(
            name="Report",
            value=message.content,
            inline=False
        )

        embed.add_field(
            name="Status",
            value="🟢 OPEN",
            inline=True
        )

        files = []
        for attachment in message.attachments:
            try:
                files.append(await attachment.to_file())
            except Exception:
                log.exception("Failed downloading attachment for case_id=%s", case_id)

        role_pings = " ".join(f"<@&{rid}>" for rid in STAFF_ROLE_IDS)

        msg = None
        try:
            msg = await staff_channel.send(
                content=f"{role_pings} 🚨 **New Report Case #{case_id}**",
                embed=embed,
                files=files,
                view=StaffPersistentView(self),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
        except Exception:
            log.exception("Failed posting case to staff channel for case_id=%s", case_id)
            try:
                await message.author.send("Sorry—your report could not be delivered to staff. Please try later.")
            except Exception:
                pass
            return

        thread = await msg.create_thread(
            name=f"case-{case_id}-{message.author.name}",
            auto_archive_duration=1440
        )

        try:
            guild_id = staff_channel.guild.id if isinstance(staff_channel, discord.TextChannel) else None
            await self.store.attach_case_message_context(
                case_id=case_id,
                guild_id=guild_id,
                staff_channel_id=STAFF_CHANNEL_ID,
                staff_message_id=msg.id,
                thread_id=thread.id,
            )
        except Exception:
            log.exception("Failed updating case context for case_id=%s", case_id)

        try:
            await message.author.send(f"✅ Your report has been submitted.\nCase ID: **#{case_id}**")
        except Exception:
            pass


bot = DungeonKeeper()


class StartView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot

    @discord.ui.button(label="Proceed", style=discord.ButtonStyle.success)
    async def proceed(self, interaction: discord.Interaction, button):

        try:
            await self.bot.store.create_or_refresh_session(interaction.user.id, PROCEED_SESSION_TTL_SECONDS)
        except Exception:
            log.exception("Failed creating DM session for user_id=%s", interaction.user.id)
            await interaction.response.send_message("Sorry—something went wrong. Please try again.", ephemeral=True)
            return

        await interaction.response.send_message(
            "Send your report now (and attach screenshot evidence if you have it).",
            ephemeral=True
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, button):

        await interaction.response.send_message(
            "Report cancelled.",
            ephemeral=True
        )


class StaffPersistentView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def check_staff(self, interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return False

        if not self.bot.is_staff(interaction.user):
            await interaction.response.send_message(
                "You are not staff.",
                ephemeral=True
            )
            return False

        return True

    async def _get_case_or_respond(self, interaction: discord.Interaction) -> Optional[dict[str, Any]]:
        if interaction.message is None:
            await interaction.response.send_message("Missing case message context.", ephemeral=True)
            return None
        try:
            case = await self.bot.store.get_case_by_staff_message_id(interaction.message.id)
        except Exception:
            log.exception("Failed loading case for staff_message_id=%s", interaction.message.id)
            await interaction.response.send_message("Could not load case from DB.", ephemeral=True)
            return None
        if not case:
            await interaction.response.send_message("Case not found in DB (was it created before DB setup?).", ephemeral=True)
            return None
        return case

    @discord.ui.button(label="Reply", style=discord.ButtonStyle.primary, custom_id="dk:reply")
    async def reply(self, interaction, button):

        if not await self.check_staff(interaction):
            return

        case = await self._get_case_or_respond(interaction)
        if not case:
            return

        await interaction.response.send_modal(
            ReplyModal(self.bot, int(case["id"]), int(case["reporter_id"]))
        )

    @discord.ui.button(label="Warn", style=discord.ButtonStyle.secondary, custom_id="dk:warn")
    async def warn(self, interaction, button):

        if not await self.check_staff(interaction):
            return

        await interaction.response.send_modal(WarnModal())

    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, custom_id="dk:mute")
    async def mute(self, interaction, button):

        if not await self.check_staff(interaction):
            return

        await interaction.response.send_modal(MuteModal())

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, custom_id="dk:ban")
    async def ban(self, interaction, button):

        if not await self.check_staff(interaction):
            return

        await interaction.response.send_modal(BanModal())

    @discord.ui.button(label="Close Case", style=discord.ButtonStyle.success, custom_id="dk:close")
    async def close(self, interaction, button):

        if not await self.check_staff(interaction):
            return

        case = await self._get_case_or_respond(interaction)
        if not case:
            return

        await interaction.response.send_modal(
            CloseModal(self.bot, int(case["id"]), int(case["reporter_id"]))
        )

    @discord.ui.button(label="Blacklist Reporter", style=discord.ButtonStyle.danger, custom_id="dk:blacklist")
    async def blacklist(self, interaction, button):

        if not await self.check_staff(interaction):
            return

        case = await self._get_case_or_respond(interaction)
        if not case:
            return

        try:
            await self.bot.store.add_blacklist(int(case["reporter_id"]))
        except Exception:
            log.exception("Failed blacklisting reporter_id=%s", case.get("reporter_id"))
            await interaction.response.send_message("Failed to blacklist reporter (DB error).", ephemeral=True)
            return

        await interaction.response.send_message(
            "Reporter blacklisted.",
            ephemeral=True
        )


class ReplyModal(discord.ui.Modal, title="Reply to Reporter"):

    message = discord.ui.TextInput(label="Message")

    def __init__(self, bot, case_id, reporter_id):
        super().__init__()
        self.bot = bot
        self.case_id = case_id
        self.reporter_id = reporter_id

    async def on_submit(self, interaction):

        try:
            user = await self.bot.fetch_user(self.reporter_id)
        except Exception:
            await interaction.response.send_message("Could not fetch reporter user.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📩 Staff Reply – Case #{self.case_id}",
            description=self.message.value,
            color=discord.Color.green()
        )

        try:
            await user.send(embed=embed)
        except Exception:
            await interaction.response.send_message("Could not DM the reporter (DMs closed?).", ephemeral=True)
            return

        await interaction.response.send_message("Reply sent.", ephemeral=True)


class WarnModal(discord.ui.Modal, title="Warn User"):

    user = discord.ui.TextInput(label="User ID or mention")
    reason = discord.ui.TextInput(label="Reason")

    async def on_submit(self, interaction):

        try:
            user_id = parse_user_id(self.user.value)
        except ValueError:
            await interaction.response.send_message("Invalid user ID/mention.", ephemeral=True)
            return

        try:
            user = await interaction.client.fetch_user(user_id)
        except Exception:
            await interaction.response.send_message("Could not fetch that user.", ephemeral=True)
            return

        embed = discord.Embed(
            title="⚠ Warning from Staff",
            description=self.reason.value,
            color=discord.Color.red()
        )

        try:
            await user.send(embed=embed)
        except Exception:
            await interaction.response.send_message("Could not DM that user.", ephemeral=True)
            return

        await interaction.response.send_message("Warning sent.", ephemeral=True)


class MuteModal(discord.ui.Modal, title="Mute User"):

    user = discord.ui.TextInput(label="User ID or mention")
    duration = discord.ui.TextInput(label="Duration (minutes)")
    reason = discord.ui.TextInput(label="Reason")

    async def on_submit(self, interaction):

        if interaction.guild is None:
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return
        if not interaction.app_permissions.moderate_members:
            await interaction.response.send_message("Bot is missing Moderate Members permission.", ephemeral=True)
            return

        try:
            user_id = parse_user_id(self.user.value)
        except ValueError:
            await interaction.response.send_message("Invalid user ID/mention.", ephemeral=True)
            return

        try:
            minutes = int(self.duration.value)
            if minutes <= 0 or minutes > 60 * 24 * 28:
                raise ValueError()
        except Exception:
            await interaction.response.send_message("Invalid duration. Use minutes (1 - 40320).", ephemeral=True)
            return

        member = interaction.guild.get_member(user_id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(user_id)
            except Exception:
                await interaction.response.send_message("User is not a member of this server.", ephemeral=True)
                return

        if member.top_role >= interaction.guild.me.top_role:  # type: ignore
            await interaction.response.send_message("I can't mute that member due to role hierarchy.", ephemeral=True)
            return

        try:
            await member.timeout(timedelta(minutes=minutes), reason=self.reason.value)
        except Exception:
            log.exception("Failed to timeout member_id=%s", user_id)
            await interaction.response.send_message("Failed to mute user (permission/hierarchy).", ephemeral=True)
            return

        await interaction.response.send_message("User muted.", ephemeral=True)


class BanModal(discord.ui.Modal, title="Ban User"):

    user = discord.ui.TextInput(label="User ID or mention")
    reason = discord.ui.TextInput(label="Reason")

    async def on_submit(self, interaction):

        if interaction.guild is None:
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return
        if not interaction.app_permissions.ban_members:
            await interaction.response.send_message("Bot is missing Ban Members permission.", ephemeral=True)
            return

        try:
            user_id = parse_user_id(self.user.value)
        except ValueError:
            await interaction.response.send_message("Invalid user ID/mention.", ephemeral=True)
            return

        try:
            user = await interaction.client.fetch_user(user_id)
        except Exception:
            await interaction.response.send_message("Could not fetch that user.", ephemeral=True)
            return

        try:
            await interaction.guild.ban(user, reason=self.reason.value)
        except Exception:
            log.exception("Failed banning user_id=%s", user_id)
            await interaction.response.send_message("Failed to ban user (permission/hierarchy).", ephemeral=True)
            return

        await interaction.response.send_message("User banned.", ephemeral=True)


class CloseModal(discord.ui.Modal, title="Close Case"):

    action = discord.ui.TextInput(label="Action taken")

    def __init__(self, bot, case_id, reporter_id):
        super().__init__()
        self.bot = bot
        self.case_id = case_id
        self.reporter_id = reporter_id

    async def on_submit(self, interaction):

        try:
            await self.bot.store.close_case(self.case_id)
        except Exception:
            log.exception("Failed closing case_id=%s", self.case_id)

        try:
            reporter = await self.bot.fetch_user(self.reporter_id)
        except Exception:
            await interaction.response.send_message("Could not fetch reporter user.", ephemeral=True)
            return

        embed = discord.Embed(
            title="✅ Report Reviewed",
            description=self.action.value,
            color=discord.Color.green()
        )

        try:
            await reporter.send(embed=embed)
        except Exception:
            await interaction.response.send_message("Could not DM the reporter (DMs closed?).", ephemeral=True)
            return

        await interaction.response.send_message(
            "Case closed and reporter notified.",
            ephemeral=True
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    bot.run(TOKEN)
