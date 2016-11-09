import discord
from discord.ext import commands
from cogs.utils import checks
import datetime
import os
import asyncio
import traceback

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
        """Clears the console."""
        os.system("cls")
        await self.bot.say("Cleared console.")

    @commands.command()
    async def invite(self):
        """Sends an invite link for you to invite me to your personal server."""
        await self.bot.say(
            'E-excuse me senpai, if you want me on your server, simply click this l-link and select a server where you have t-the "Manage server" role...\n'
            'https://discordapp.com/oauth2/authorize?&client_id={}&scope=bot&permissions=1072819255\n'.format(self.bot.bot_id))

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
Author: {5.name} (ID: {5.id})
Language: Snek language (python)\n
**Statistics**
Uptime: {1}
Visible Servers: {2}
Visible Channels: {3}
Visible Users: {4}'''
        await self.bot.say(fmt.format(self.bot.user, uptime, scounter, ccounter, ucounter, discord.utils.get(self.bot.get_all_members(), id=self.bot.ownerid)))

    @commands.command(hidden=True, pass_context=True)
    @checks.is_owner()
    async def say(self, ctx, *, text: str):
        try:
            await self.bot.delete_message(ctx.message)
            await self.bot.say(text)
        except:
            await self.bot.say(text)

    @commands.command(pass_context=True, hidden=True, name='eval')
    @checks.is_owner()
    async def debug(self, ctx, *, code: str):
        """Evaluates code."""
        code = code.strip('` ')
        python = '```py\n{}\n```'
        try:
            result = eval(code)
        except Exception as e:
            await self.bot.say(python.format(type(e).__name__ + ': ' + str(e)))
            return

        if asyncio.iscoroutine(result):
            result = await result

        await self.bot.say(python.format(result))

    @commands.command(pass_context=True, hidden=True, name='run')
    @checks.is_owner()
    async def debug2(self, ctx, *, code: str):
        """Runs code."""
        code = code.strip('` ')
        python = '```py\n{}\n```'
        try:
            result = exec(code)
        except Exception as e:
            await self.bot.say(python.format(type(e).__name__ + ': ' + str(e)))
            return

        if asyncio.iscoroutine(result):
            result = await result

        await self.bot.say(python.format(result))

    @commands.command(pass_context=True, hidden=True)
    @checks.is_owner()
    async def repl(self, ctx):
        def cleanup_code(content):
            """Automatically removes code blocks from the code."""
            # remove ```py\n```
            if content.startswith('```') and content.endswith('```'):
                return '\n'.join(content.split('\n')[1:-1])

            # remove `foo`
            return content.strip('` \n')

        def get_syntax_error(e):
            return '```py\n{0.text}{1:>{0.offset}}\n{2}: {0}```'.format(
                e, '^', type(e).__name__)

        msg = ctx.message

        repl_locals = {}
        repl_globals = {'ctx': ctx, 'bot': self.bot,
                        'message': msg, 'last': None}

        await self.bot.say('Enter code to execute or evaluate. `exit()` or `quit` to exit.')
        while True:
            response = await self.bot.wait_for_message(author=msg.author, channel=msg.channel,
                                                       check=lambda m: m.content.startswith('`'))

            cleaned = cleanup_code(response.content)

            if cleaned in ('quit', 'exit', 'exit()'):
                await self.bot.say('Exiting.')
                return
            code = None
            executor = exec
            if cleaned.count('\n') == 0:
                # single statement, potentially 'eval'
                try:
                    code = compile(cleaned, '<repl session>', 'eval')
                except SyntaxError:
                    pass
                else:
                    executor = eval

            if executor is exec:
                try:
                    code = compile(cleaned, '<repl session>', 'exec')
                except SyntaxError as e:
                    await self.bot.say(get_syntax_error(e))
                    continue

            repl_globals['message'] = response

            fmt = None

            try:
                result = executor(code, repl_globals, repl_locals)
                if asyncio.iscoroutine(result):
                    result = await result
            except Exception as e:
                fmt = '```py\n{}\n```'.format(traceback.format_exc())
            else:
                if result is not None:
                    fmt = '```py\n{}\n```'.format(result)
                    repl_globals['last'] = result

            try:
                if fmt is not None:
                    await self.bot.send_message(msg.channel, fmt)
            except discord.Forbidden:
                pass
            except discord.HTTPException as e:
                await self.bot.send_message(msg.channel, 'Unexpected error: `{}`'.format(e))
