import discord
from discord.ext import commands
from cogs.utils import checks
import asyncio
import string
import re

def setup(bot):
    bot.add_cog(Mods(bot))

class Mods:
    def __init__(self, bot):
        self.bot = bot

    def findUserseverywhere(self, query):
        mentionregex = "<@!?(\d+)>"
        userid = ''
        discrim = None
        if bool(re.search(mentionregex, query)):
            userid = re.findall(mentionregex, query)[0]
            user = discord.utils.get(self.bot.get_all_members(), id=userid)
            return [user]
        elif bool(re.search(r"^.*#\d{4}$", query)):
            discrim = query[-4:]
            query = query[:-5]
        exact = set()
        wrongcase = set()
        startswith = set()
        contains = set()
        lowerquery = query.lower()
        for u in self.bot.get_all_members():
            if discrim is not None and u.discriminator != discrim:
                continue
            if u.name == query:
                exact.add(u)
            elif not exact and u.name.lower() == lowerquery:
                wrongcase.add(u)
            elif not wrongcase and u.name.lower().startswith(lowerquery):
                startswith.add(u)
            elif not startswith and lowerquery in u.name.lower():
                contains.add(u)
        if exact:
            return list(exact)
        if wrongcase:
            return list(wrongcase)
        if startswith:
            return list(startswith)
        return list(contains)


    def findUsers(self, query, server):
        mentionregex = "<@!?(\d+)>"
        userid = ''
        discrim = None
        if bool(re.search(mentionregex, query)):
            userid = re.findall(mentionregex, query)[0]
            user = discord.utils.get(server.members, id=userid)
            return [user]
        elif bool(re.search(r"^.*#\d{4}$", query)):
            discrim = query[-4:]
            query = query[:-5]
        exact = set()
        wrongcase = set()
        startswith = set()
        contains = set()
        lowerquery = query.lower()
        for u in server.members:
            nick = u.display_name
            if discrim is not None and u.discriminator != discrim:
                continue
            if u.name == query or nick == query:
                exact.add(u)
            elif not exact and (u.name.lower() == lowerquery or nick.lower() == lowerquery):
                wrongcase.add(u)
            elif not wrongcase and (u.name.lower().startswith(lowerquery) or nick.lower().startswith(lowerquery)):
                startswith.add(u)
            elif not startswith and (lowerquery in u.name.lower() or lowerquery in nick.lower()):
                contains.add(u)
        if exact:
            return list(exact)
        if wrongcase:
            return list(wrongcase)
        if startswith:
            return list(startswith)
        return list(contains)

    @commands.group(pass_context=True, invoke_without_command=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int):
        """Chat clearing commands."""
        messages = await self.bot.purge_from(ctx.message.channel, limit=amount, before=ctx.message)
        await self.bot.delete_message(ctx.message)
        send = await self.bot.say("Successfully cleared **{}** messages".format(len(messages)))
        await asyncio.sleep(3)
        await self.bot.delete_message(send)

    @clear.command(name="bots", pass_context=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def _bots(self, ctx, amount: int=100):
        """Clears bots and bot calls."""
        def check(m):
            if m.author.bot:
                return True
            for mem in m.mentions:
                if mem.bot:
                    return True
            if m.content.startswith(tuple(i for i in string.punctuation)):
                return True
            return False
        messages = await self.bot.purge_from(ctx.message.channel, limit=amount, before=ctx.message, check=check)
        await self.bot.delete_message(ctx.message)
        send = await self.bot.say("Successfully cleared **{}** messages".format(len(messages)))
        await asyncio.sleep(3)
        await self.bot.delete_message(send)

    @clear.command(name="user", pass_context=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def _user(self, ctx, who: str, amount: int=100):
        """Clears posts by a specific user."""
        users = None
        if ctx.message.server is not None:
            users = self.findUsers(who, ctx.message.server)
        if users is None or not users:
            users = self.findUserseverywhere(who)
        if not users:
            await self.bot.say('⚠ No users found matching "{}"'.format(who))
        elif len(users) > 1:
            out = '⚠ Multiple users found matching "{}":'.format(who)
            for u in users[:6]:
                out += "\n - {}".format(str(u))
            if len(users) > 6:
                out += "\n And {} more...".format(str(len(users) - 6))
            await self.bot.say(out)
        else:
            messages = await self.bot.purge_from(ctx.message.channel, limit=amount, before=ctx.message, check=lambda m: m.author == users[0])
            await self.bot.delete_message(ctx.message)
            send = await self.bot.say("Successfully cleared **{}** messages".format(len(messages)))
            await asyncio.sleep(3)
            await self.bot.delete_message(send)

    @clear.command(name="images", pass_context=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def _images(self, ctx, amount: int=100):
        """Only clears images."""
        def check(m):
            for e in m.embeds:
                if e["type"] == "photo" or e["type"] == "image":
                    return True
            for a in m.attachments:
                if a['url'].endswith(('.jpg', '.tif', '.gif', '.gifv', '.png', '.raw')):
                    return True
            return False
        messages = await self.bot.purge_from(ctx.message.channel, limit=amount, before=ctx.message, check=check)
        await self.bot.delete_message(ctx.message)
        send = await self.bot.say("Successfully cleared **{}** messages".format(len(messages)))
        await asyncio.sleep(3)
        await self.bot.delete_message(send)
