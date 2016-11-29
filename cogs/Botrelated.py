import discord
from discord.ext import commands
from cogs.utils import checks
import datetime
import os
import asyncio
import traceback
import collections
import requests
import json
import inspect
from contextlib import redirect_stdout
import io

def setup(bot):
    bot.add_cog(Botrelated(bot))


class Botrelated:

    def __init__(self, bot):
        self.bot = bot
        self.repl_sessions = {}
        self.repl_embeds = {}

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

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    def get_syntax_error(self, e):
        return '```py\n{0.text}{1:>{0.offset}}\n{2}: {0}```'.format(e, '^', type(e).__name__)

    @commands.group(name='shell', aliases=['ipython', 'repl', 'longexec', 'core', 'overkill'], pass_context=True, invoke_without_command=True)
    async def repl(self, ctx, *, name: str=None):
        '''Head on impact with an interactive python shell.'''
        
        session = ctx.message.channel.id
        embed = discord.Embed(description="_Enter code to execute or evaluate. `exit()` or `quit` to exit._")
        embed.set_author(name="Interactive Python Shell", 
                         icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1024px-Python-logo-notext.svg.png")
        embed.set_footer(text="Based on RDanny's repl command by Danny.")
        if name is not None:
            embed.title = name.strip(" ")

        history = collections.OrderedDict()

        variables = {
            'ctx': ctx,
            'bot': self.bot,
            'message': ctx.message,
            'server': ctx.message.server,
            'channel': ctx.message.channel,
            'author': ctx.message.author,
            '_': None,
        }

        if session in self.repl_sessions:
            await self.bot.send_message(ctx.message.channel, embed = discord.Embed(color = 15746887, 
                                                description = "**Error**: _Shell is already running in channel._"))
            return

        shell = await self.bot.send_message(ctx.message.channel, embed=embed)

        self.repl_sessions[session] = shell
        self.repl_embeds[shell] = embed

        while True:
            response = await self.bot.wait_for_message(author=ctx.message.author, 
                                                  channel=ctx.message.channel, 
                                                  check=lambda m: m.content.startswith('`'))

            
            cleaned = self.cleanup_code(response.content)
            shell = self.repl_sessions[session]
            await self.bot.delete_message(response)

            if len(self.repl_embeds[shell].fields) >= 7:
                self.repl_embeds[shell].remove_field(0)

            if cleaned in ('quit', 'exit', 'exit()'):
                self.repl_embeds[shell].color = 16426522
                
                if self.repl_embeds[shell].title is not discord.Embed.Empty:
                    history_string = "History for {}\n\n\n".format(self.repl_embeds[shell].title)
                else:
                    history_string = "History for latest session\n\n\n"
                    
                for item in history.keys():
                    history_string += ">>> {}\n{}\n\n".format(item, history[item])
                    
                haste_response = requests.post("http://hastebin.com/documents", history_string.encode('utf-8'))
                haste_url = "http://hastebin.com/{}".format(json.loads(haste_response.content.decode())['key'])
                
                return_msg = "[`Leaving shell session. History hosted on hastebin.`]({})".format(haste_url)
                self.repl_embeds[shell].add_field(name = "`>>> {}`".format(cleaned), 
                                               value = return_msg, 
                                               inline = False)
                await self.bot.edit_message(self.repl_sessions[session], embed=self.repl_embeds[shell])
                
                del self.repl_embeds[shell]
                del self.repl_sessions[session]
                return

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
                    self.repl_embeds[shell].color = 15746887
                    
                    return_msg = self.get_syntax_error(e)
                    
                    history[cleaned] = return_msg
                    
                    if len(cleaned) > 800:
                        cleaned = "<Too big to be printed>"
                    if len(return_msg) > 800:
                        haste_response = requests.post("http://hastebin.com/documents", return_msg.encode('utf-8'))
                        haste_url = "http://hastebin.com/{}".format(json.loads(haste_response.content.decode())['key'])
                        return_msg = "[`SyntaxError too big to be printed. Hosted on hastebin.`]({})".format(haste_url)
                        
                    self.repl_embeds[shell].add_field(name="`>>> {}`".format(cleaned), 
                                                   value = return_msg, 
                                                  inline = False)
                    await self.bot.edit_message(self.repl_sessions[session], embed=self.repl_embeds[shell])
                    continue

            variables['message'] = response

            fmt = None
            stdout = io.StringIO()

            try:
                with redirect_stdout(stdout):
                    result = executor(code, variables)
                    if inspect.isawaitable(result):
                        result = await result
            except Exception as e:
                self.repl_embeds[shell].color = 15746887
                value = stdout.getvalue()
                fmt = '```py\n{}{}\n```'.format(value, traceback.format_exc())
            else:
                self.repl_embeds[shell].color = 4437377
                value = stdout.getvalue()
                if result is not None:
                    fmt = '```py\n{}{}\n```'.format(value, result)
                    variables['_'] = result
                elif value:
                    fmt = '```py\n{}\n```'.format(value)

            history[cleaned] = fmt
            
            if len(cleaned) > 800:
                cleaned = "<Too big to be printed>"
            
            try:
                if fmt is not None:
                    if len(fmt) >= 800:
                        haste_response = requests.post("http://hastebin.com/documents", fmt.encode('utf-8'))
                        haste_url = "http://hastebin.com/{}".format(json.loads(haste_response.content.decode())['key'])
                        
                        self.repl_embeds[shell].add_field(name = "`>>> {}`".format(cleaned), 
                                                     value = "[`Content too big to be printed. Hosted on hastebin.`]({})".format(haste_url),  # TODO: Add calls to a pastebin
                                                     inline = False)
                        await self.bot.edit_message(self.repl_sessions[session], embed=self.repl_embeds[shell])
                    else:
                        self.repl_embeds[shell].add_field(name = "`>>> {}`".format(cleaned), 
                                                     value = fmt, 
                                                    inline = False)
                        await self.bot.edit_message(self.repl_sessions[session], embed=self.repl_embeds[shell])
                else:
                    self.repl_embeds[shell].add_field(name = "`>>> {}`".format(cleaned), 
                                                 value = "`Empty response, assumed successful.`", 
                                                 inline = False)
                    await self.bot.edit_message(self.repl_sessions[session], embed=self.repl_embeds[shell])
            except discord.Forbidden:
                pass
            except discord.HTTPException as e:
                await self.bot.send_message(ctx.message.channel, embed=discord.Embed(color = 15746887,
                                                  description = '**Error**: _{}_'.format(e)))

    @repl.command(name='jump', aliases=['hop', 'pull', 'recenter', 'whereditgo'], pass_context=True)
    async def _repljump(ctx):
        '''Brings the shell back down so you can see it again.'''
        
        session = ctx.message.channel.id
        
        if session not in self.repl_sessions:
            await self.bot.send_message(ctx.message.channel, embed = discord.Embed(color = 15746887, 
                                                description = "**Error**: _No shell running in channel._"))
            return
        
        shell = self.repl_sessions[session]
        embed = self.repl_embeds[shell]
        
        await self.bot.delete_message(ctx.message)
        await self.bot.delete_message(shell)
        new_shell = await self.bot.send_message(ctx.message.channel, embed=embed)
        
        self.repl_sessions[session] = new_shell
        
        del self.repl_embeds[shell]
        self.repl_embeds[new_shell] = embed
        
    @repl.command(name='clear', aliases=['clean', 'purge', 'cleanup', 'ohfuckme', 'deletthis'], pass_context = True)
    async def _replclear(ctx):
        '''Clears the fields of the shell and resets the color.'''
        
        session = ctx.message.channel.id
        
        if session not in self.repl_sessions:
            await self.bot.send_message(ctx.message.channel, embed = discord.Embed(color = 15746887, 
                                                description = "**Error**: _No shell running in channel._"))
            return
        
        shell = self.repl_sessions[session]
        
        self.repl_embeds[shell].color = discord.Color.default()
        self.repl_embeds[shell].clear_fields()
        
        await self.bot.delete_message(ctx.message)
        await self.bot.edit_message(shell, embed=self.repl_embeds[shell])