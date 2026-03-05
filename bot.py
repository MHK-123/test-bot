import discord
from discord.ext import commands
import os
from datetime import datetime, timedelta

TOKEN = os.getenv("DISCORD_TOKEN")
STAFF_CHANNEL_ID = int(os.getenv("STAFF_CHANNEL_ID"))
STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID"))

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
        self.active_sessions = set()
        self.last_report_time = {}

    async def on_ready(self):
        print(f"{self.user} is online")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="DMs for reports"
            )
        )

    def is_staff(self, member):
        return any(role.id == STAFF_ROLE_ID for role in member.roles)

    async def on_message(self, message):

        if message.author.bot:
            return

        if isinstance(message.channel, discord.DMChannel):

            if message.author.id in self.blacklisted_users:
                return

            if message.author.id in self.active_sessions:
                return

            self.active_sessions.add(message.author.id)

            embed = discord.Embed(
                title="DungeonKeeper Support System",
                description=(
                    "Report issues directly to staff.\n\n"
                    "• Reports are reviewed by moderators\n"
                    "• False reports may lead to punishment\n\n"
                    "Press **Proceed** to continue."
                ),
                color=discord.Color.blue()
            )

            view = SupportStartView(self, message.author.id)
            msg = await message.author.send(embed=embed, view=view)
            view.message = msg

            return

        await self.process_commands(message)


bot = DungeonKeeper()


# START PANEL

class SupportStartView(discord.ui.View):

    def __init__(self, bot, user_id):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.message = None

    async def on_timeout(self):

        self.bot.active_sessions.discard(self.user_id)

        for item in self.children:
            item.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass

    @discord.ui.button(label="Proceed", style=discord.ButtonStyle.success)
    async def proceed(self, interaction: discord.Interaction, button):

        if interaction.user.id != self.user_id:
            return

        self.bot.active_sessions.discard(self.user_id)

        await interaction.response.send_modal(ReportModal(self.bot))

        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button):

        if interaction.user.id != self.user_id:
            return

        self.bot.active_sessions.discard(self.user_id)

        await interaction.response.send_message(
            "Support request cancelled.",
            ephemeral=True
        )

        self.stop()


# REPORT MODAL

class ReportModal(discord.ui.Modal, title="Submit Report"):

    message = discord.ui.TextInput(
        label="Report Message",
        style=discord.TextStyle.paragraph,
        max_length=2000
    )

    evidence = discord.ui.TextInput(
        label="Evidence Link",
        required=False
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction):

        now = datetime.utcnow()

        last = self.bot.last_report_time.get(interaction.user.id)

        if last and (now - last).seconds < 300:
            return await interaction.response.send_message(
                "You must wait before submitting another report.",
                ephemeral=True
            )

        self.bot.last_report_time[interaction.user.id] = now

        case_id = self.bot.case_counter
        self.bot.case_counter += 1

        self.bot.cases[case_id] = {
            "reporter": interaction.user.id,
            "status": "OPEN",
            "handled_by": None
        }

        await interaction.response.send_message(
            f"✅ Report submitted.\nCase ID: **#{case_id}**",
            ephemeral=True
        )

        staff_channel = bot.get_channel(STAFF_CHANNEL_ID)

        embed = discord.Embed(
            title=f"🚨 Support Case #{case_id}",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(
            name="Reporter",
            value=f"{interaction.user} ({interaction.user.id})",
            inline=False
        )

        embed.add_field(
            name="Status",
            value="🟢 OPEN",
            inline=True
        )

        embed.add_field(
            name="Report",
            value=self.message.value,
            inline=False
        )

        if self.evidence.value:
            embed.add_field(
                name="Evidence",
                value=self.evidence.value,
                inline=False
            )

        view = StaffButtons(bot, case_id)

        msg = await staff_channel.send(embed=embed, view=view)

        thread = await msg.create_thread(
            name=f"case-{case_id}-{interaction.user.name}",
            auto_archive_duration=1440
        )

        bot.cases[case_id]["thread"] = thread.id


# STAFF BUTTONS

class StaffButtons(discord.ui.View):

    def __init__(self, bot, case_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.case_id = case_id

    async def staff_check(self, interaction):

        if not self.bot.is_staff(interaction.user):
            await interaction.response.send_message(
                "Not authorized.",
                ephemeral=True
            )
            return False

        return True


    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary)
    async def claim(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        case = self.bot.cases[self.case_id]

        if case["handled_by"]:
            return await interaction.response.send_message(
                "Case already claimed.",
                ephemeral=True
            )

        case["handled_by"] = interaction.user.id

        embed = interaction.message.embeds[0]

        embed.add_field(
            name="Handled By",
            value=interaction.user.mention
        )

        await interaction.message.edit(embed=embed)

        await interaction.response.send_message(
            "Case claimed.",
            ephemeral=True
        )


    @discord.ui.button(label="Reply", style=discord.ButtonStyle.primary)
    async def reply(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        await interaction.response.send_modal(
            ReplyModal(self.bot, self.case_id)
        )


    @discord.ui.button(label="Warn", style=discord.ButtonStyle.secondary)
    async def warn(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        await interaction.response.send_modal(
            WarnModal(self.bot, self.case_id)
        )


    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary)
    async def mute(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        case = self.bot.cases[self.case_id]

        member = interaction.guild.get_member(case["reporter"])

        if not member:
            return await interaction.response.send_message(
                "User not in server.",
                ephemeral=True
            )

        await member.timeout(
            timedelta(hours=1),
            reason="Support case mute"
        )

        await interaction.response.send_message(
            "User muted.",
            ephemeral=True
        )


    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger)
    async def ban(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        case = self.bot.cases[self.case_id]

        user = await self.bot.fetch_user(case["reporter"])

        await interaction.guild.ban(user)

        await interaction.response.send_message(
            "User banned.",
            ephemeral=True
        )


    @discord.ui.button(label="Close", style=discord.ButtonStyle.success)
    async def close(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        case = self.bot.cases[self.case_id]

        case["status"] = "CLOSED"

        thread = interaction.guild.get_channel(case["thread"])

        if thread:
            await thread.edit(locked=True, archived=True)

        embed = interaction.message.embeds[0]

        for i, field in enumerate(embed.fields):
            if field.name == "Status":
                embed.set_field_at(i, name="Status", value="🔴 CLOSED")
                break

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(embed=embed, view=self)

        await interaction.response.send_message(
            "Case closed.",
            ephemeral=True
        )


    @discord.ui.button(label="Blacklist", style=discord.ButtonStyle.danger)
    async def blacklist(self, interaction, button):

        if not await self.staff_check(interaction):
            return

        case = self.bot.cases[self.case_id]

        self.bot.blacklisted_users.add(case["reporter"])

        await interaction.response.send_message(
            "User blacklisted.",
            ephemeral=True
        )


# STAFF MODALS

class ReplyModal(discord.ui.Modal, title="Reply to User"):

    reply = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.paragraph
    )

    def __init__(self, bot, case_id):
        super().__init__()
        self.bot = bot
        self.case_id = case_id

    async def on_submit(self, interaction):

        case = self.bot.cases[self.case_id]

        user = await self.bot.fetch_user(case["reporter"])

        embed = discord.Embed(
            title=f"Staff Reply - Case #{self.case_id}",
            description=self.reply.value,
            color=discord.Color.green()
        )

        await user.send(embed=embed)

        await interaction.response.send_message(
            "Reply sent.",
            ephemeral=True
        )


class WarnModal(discord.ui.Modal, title="Warn User"):

    reason = discord.ui.TextInput(
        label="Warning Reason",
        style=discord.TextStyle.paragraph
    )

    def __init__(self, bot, case_id):
        super().__init__()
        self.bot = bot
        self.case_id = case_id

    async def on_submit(self, interaction):

        case = self.bot.cases[self.case_id]

        user = await self.bot.fetch_user(case["reporter"])

        embed = discord.Embed(
            title=f"⚠ Warning - Case #{self.case_id}",
            description=self.reason.value,
            color=discord.Color.red()
        )

        await user.send(embed=embed)

        await interaction.response.send_message(
            "Warning sent.",
            ephemeral=True
        )


bot.run(TOKEN)
