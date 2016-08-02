import discord
from discord.ext import commands
from cogs.utils import checks
import datetime
import os

def setup(bot):
    bot.add_cog(Botrelated(bot))


class Botrelated:

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @checks.is_owner()
    async def load(self, extension_name: str):
        """Loads an extension."""
        try:
            self.bot.load_extension("cogs." + extension_name)
        except (AttributeError, ImportError) as e:
            await self.bot.say("```py\n{}: {}\n```".format(type(e).__name__, str(e)))
            return
        await self.bot.say("{} loaded.".format(extension_name))


    @commands.command()
    @checks.is_owner()
    async def reload(self, extension_name: str):
        """Reloads an extension."""
        self.bot.unload_extension("cogs." + extension_name)
        try:
            self.bot.load_extension("cogs." + extension_name)
        except (AttributeError, ImportError) as e:
            await self.bot.say("```py\n{}: {}\n```".format(type(e).__name__, str(e)))
            return
        await self.bot.say("{} reloaded.".format(extension_name))


    @commands.command()
    @checks.is_owner()
    async def unload(self, extension_name: str):
        """Unloads an extension."""
        self.bot.unload_extension("cogs." + extension_name)
        await self.bot.say("{} unloaded.".format(extension_name))

    @commands.command()
    @checks.is_owner()
    async def cls(self):
        os.system("cls")
        await self.bot.say("Cleared console.")

    @commands.command()
    async def invite(self):
        """Sends an invite link for you to invite me to your personal server."""
        await self.bot.say(
            'E-excuse me senpai, if you want me on your server, simply click this l-link and select a server where you have t-the "Manage server" role...\n'
            'https://discordapp.com/oauth2/authorize?&bot_id={}&scope=bot&permissions=-1\n'.format(self.bot.bot_id))


    @commands.command()
    async def botabout(self):
        """I'll tell a little about myself."""
        uptime = datetime.datetime.now() - self.bot.starttime
        ucounter = 0
        for _ in self.bot.get_all_members():
            ucounter += 1
        ccounter = 0
        for _ in self.bot.get_all_channels():
            ccounter += 1
        scounter = 0
        for _ in self.bot.servers:
            scounter += 1
        fmt = '''**About me**
Name: {0.name} (ID: {0.id})
Author: Moon Moon (ID: 139386544275324928)
Language: Snek language (python)\n
**Statistics**
Uptime: {1}
Visible Servers: {2}
Visible Channels: {3}
Visible Users: {4}'''
        await self.bot.say(fmt.format(self.bot.user, uptime, scounter, ccounter, ucounter))

    @commands.command(hidden=True, pass_context=True)
    async def say(self, ctx, *, text: str):
        try:
            await self.bot.delete_message(ctx.message)
            await self.bot.say(text)
        except:
            await self.bot.say(text)