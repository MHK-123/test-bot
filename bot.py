import discord
from discord.ext import commands
import os
from datetime import datetime, timedelta

TOKEN = os.environ["DISCORD_TOKEN"]
STAFF_CHANNEL_ID = int(os.environ["STAFF_CHANNEL_ID"])
STAFF_ROLE_ID = int(os.environ["STAFF_ROLE_ID"])

class DungeonKeeper(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.dm_messages = True

        super().__init__(command_prefix="!", intents=intents)

        self.case_counter = 1
        self.cases = {}
        self.blacklisted_users = set()
        self.active_sessions = {}

    async def on_ready(self):
        print(f"{self.user} is online")

    def is_staff(self, member):
        return any(role.id == STAFF_ROLE_ID for role in member.roles)

    async def on_message(self, message):

        if message.author.bot:
            return

        if isinstance(message.channel, discord.DMChannel):

            if message.author.id in self.blacklisted_users:
                return

            # waiting for report message
            if message.author.id in self.active_sessions:

                if self.active_sessions[message.author.id] == "awaiting_report":
                    await self.create_case(message)
                    self.active_sessions.pop(message.author.id)
                    return

            # show start panel
            embed = discord.Embed(
                title="🛡️ DungeonKeeper Report System",
                color=discord.Color.blurple(),
                description=(
                    "**Use this system to report rule violations.**\n\n"
                    "📋 **Include:**\n"
                    "• 👤 Username of the member\n"
                    "• 📜 What they did\n"
                    "• 📸 Screenshot evidence\n\n"
                    "⚠ False reports may lead to punishment."
                )
            )

            view = StartView(self)
            await message.author.send(embed=embed, view=view)
            return

        await self.process_commands(message)

    async def create_case(self, message):

        case_id = self.case_counter
        self.case_counter += 1

        staff_channel = self.get_channel(STAFF_CHANNEL_ID)

        embed = discord.Embed(
            title=f"🚨 Support Case #{case_id}",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(
            name="Reporter",
            value=f"{message.author} ({message.author.id})",
            inline=False
        )

        embed.add_field(
            name="Status",
            value="🟢 OPEN",
            inline=True
        )

        embed.add_field(
            name="Report",
            value=message.content,
            inline=False
        )

        files = []
        for attachment in message.attachments:
            files.append(await attachment.to_file())

        view = StaffButtons(self, case_id, message.author.id)

        msg = await staff_channel.send(embed=embed, view=view, files=files)

        thread = await msg.create_thread(
            name=f"case-{case_id}-{message.author.name}",
            auto_archive_duration=1440
        )

        self.cases[case_id] = {
            "reporter": message.author.id,
            "thread": thread.id,
            "status": "OPEN"
        }

        await message.author.send(
            f"✅ Report submitted successfully.\nCase ID: **#{case_id}**"
        )


bot = DungeonKeeper()


# START VIEW

class StartView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot

    @discord.ui.button(label="Proceed", style=discord.ButtonStyle.success)
    async def proceed(self, interaction: discord.Interaction, button):

        self.bot.active_sessions[interaction.user.id] = "awaiting_report"

        await interaction.response.send_message(
            "Please send your report message now with screenshot evidence.",
            ephemeral=True
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, button):

        await interaction.response.send_message(
            "Report cancelled.",
            ephemeral=True
        )


# STAFF BUTTONS

class StaffButtons(discord.ui.View):

    def __init__(self, bot, case_id, reporter_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.case_id = case_id
        self.reporter_id = reporter_id

    async def staff_check(self, interaction):

        if not self.bot.is_staff(interaction.user):
            await interaction.response.send_message(
                "You are not staff.",
                ephemeral=True
            )
            return False
        return True


    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary)
    async def claim(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        await interaction.response.send_message(
            f"{interaction.user.mention} claimed this case.",
            ephemeral=True
        )


    @discord.ui.button(label="Reply", style=discord.ButtonStyle.primary)
    async def reply(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        await interaction.response.send_modal(
            ReplyModal(self.bot, self.case_id, self.reporter_id)
        )


    @discord.ui.button(label="Warn", style=discord.ButtonStyle.secondary)
    async def warn(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        await interaction.response.send_modal(
            WarnModal(self.bot, self.case_id, self.reporter_id)
        )


    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary)
    async def mute(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        await interaction.response.send_modal(
            MuteModal(self.bot, self.case_id, self.reporter_id)
        )


    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger)
    async def ban(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        user = await self.bot.fetch_user(self.reporter_id)

        await interaction.guild.ban(user)

        await interaction.response.send_message(
            "User banned.",
            ephemeral=True
        )


    @discord.ui.button(label="Close", style=discord.ButtonStyle.success)
    async def close(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        await interaction.response.send_modal(
            CloseModal(self.bot, self.case_id, self.reporter_id)
        )


    @discord.ui.button(label="Blacklist", style=discord.ButtonStyle.danger)
    async def blacklist(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        self.bot.blacklisted_users.add(self.reporter_id)

        await interaction.response.send_message(
            "Reporter blacklisted.",
            ephemeral=True
        )


# MODALS

class ReplyModal(discord.ui.Modal, title="Reply to Reporter"):

    message = discord.ui.TextInput(label="Message")

    def __init__(self, bot, case_id, reporter_id):
        super().__init__()
        self.bot = bot
        self.case_id = case_id
        self.reporter_id = reporter_id

    async def on_submit(self, interaction):

        user = await self.bot.fetch_user(self.reporter_id)

        embed = discord.Embed(
            title=f"📩 Staff Reply – Case #{self.case_id}",
            description=self.message.value,
            color=discord.Color.green()
        )

        await user.send(embed=embed)

        await interaction.response.send_message(
            "Reply sent.",
            ephemeral=True
        )


class WarnModal(discord.ui.Modal, title="Warn User"):

    reason = discord.ui.TextInput(label="Reason")

    def __init__(self, bot, case_id, reporter_id):
        super().__init__()
        self.bot = bot
        self.case_id = case_id
        self.reporter_id = reporter_id

    async def on_submit(self, interaction):

        user = await self.bot.fetch_user(self.reporter_id)

        embed = discord.Embed(
            title="⚠ Warning from Staff",
            description=self.reason.value,
            color=discord.Color.red()
        )

        await user.send(embed=embed)

        await interaction.response.send_message(
            "Warning sent.",
            ephemeral=True
        )


class MuteModal(discord.ui.Modal, title="Mute User"):

    duration = discord.ui.TextInput(label="Duration (minutes)")
    reason = discord.ui.TextInput(label="Reason")

    def __init__(self, bot, case_id, reporter_id):
        super().__init__()
        self.bot = bot
        self.case_id = case_id
        self.reporter_id = reporter_id

    async def on_submit(self, interaction):

        member = interaction.guild.get_member(self.reporter_id)

        duration_minutes = int(self.duration.value)

        await member.timeout(
            timedelta(minutes=duration_minutes),
            reason=self.reason.value
        )

        await interaction.response.send_message(
            "User muted.",
            ephemeral=True
        )


class CloseModal(discord.ui.Modal, title="Close Case"):

    result = discord.ui.TextInput(label="Action Taken")

    def __init__(self, bot, case_id, reporter_id):
        super().__init__()
        self.bot = bot
        self.case_id = case_id
        self.reporter_id = reporter_id

    async def on_submit(self, interaction):

        user = await self.bot.fetch_user(self.reporter_id)

        embed = discord.Embed(
            title="✅ Report Reviewed",
            description=self.result.value,
            color=discord.Color.green()
        )

        await user.send(embed=embed)

        await interaction.response.send_message(
            "Case closed and reporter notified.",
            ephemeral=True
        )


if __name__ == "__main__":
    bot.run(TOKEN)
