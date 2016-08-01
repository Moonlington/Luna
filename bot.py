from discord.ext import commands
import discord
from cogs.utils import checks
import datetime, re
import json, asyncio
import copy
import logging
import traceback
import os
import sys
import requests
import linecache

initial_extensions = [
    'cogs.Funstuff',
    'cogs.Members',
    'cogs.Music',
    'cogs.Searches'
]

botdesc = '''Luna is a simple bot made by Floretta for fun ¯\_(ツ)_/¯'''

discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.CRITICAL)
log = logging.getLogger()
log.setLevel(logging.INFO)
handler = logging.FileHandler(filename='luna.log', encoding='utf-8', mode='w')
log.addHandler(handler)

prefix = ['&']

bot = commands.Bot(command_prefix=prefix, description=botdesc, pm_help=None)


@bot.event
async def on_command_error(error, ctx):
    if isinstance(error, commands.NoPrivateMessage):
        await bot.send_message(ctx.message.author, 'This command cannot be used in private messages.')
    elif isinstance(error, commands.DisabledCommand):
        await bot.send_message(ctx.message.author, 'Sorry. This command is disabled and cannot be used.')
    elif isinstance(error, commands.CommandInvokeError):
        print('In {0.command.qualified_name}:'.format(ctx), file=sys.stderr)
        traceback.print_tb(error.original.__traceback__)
        print('{0.__class__.__name__}: {0}'.format(error.original), file=sys.stderr)


@bot.event
async def on_ready():
    print('\n\n\nLogged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('--------------')
    print('In servers:')
    print("\n".join(s.name for s in bot.servers if s.name))
    print('--------------')
    if sys.platform == "win32":
        if os.path.exists(os.path.join(os.getcwd(), "libopus.dll")):
            found = "libopus"
        else:
            found = False

    else:
        found = find_library("opus")
    if found:
        print(">> Loaded libopus from {}".format(found))
        discord.opus.load_opus(found)
    else:
        if sys.platform == "win32":
            print(">> Downloading libopus for Windows.")
            sfbit = sys.maxsize > 2 ** 32
            if sfbit:
                to_dl = 'x64'
            else:
                to_dl = 'x86'
            r = requests.get(
                "https://github.com/SexualRhinoceros/MusicBot/raw/develop/libopus-0.{}.dll".format(to_dl),
                stream=True)
            with open("libopus.dll", 'wb') as f:
                for chunk in r.iter_content(256):
                    f.write(chunk)
            discord.opus.load_opus("libopus")
            del sfbit, to_dl
        else:
            print(">> Cannot load opus library - cannot use voice.")
            del found


@bot.event
async def on_resumed():
    print('resumed bot...')


@bot.event
async def on_command(command, ctx):
    message = ctx.message
    destination = None
    if message.channel.is_private:
        destination = 'Private Message'
    else:
        destination = '#{0.channel.name} ({0.server.name})'.format(message)

    log.info('{0.timestamp}: {0.author.name} in {1}: {0.content}'.format(message, destination))


def load_credentials():
    with open('credentials.json') as f:
        return json.load(f)


@bot.command()
@checks.is_owner()
async def load(extension_name : str):
    """Loads an extension."""
    try:
        bot.load_extension(extension_name)
    except (AttributeError, ImportError) as e:
        await bot.say("```py\n{}: {}\n```".format(type(e).__name__, str(e)))
        return
    await bot.say("{} loaded.".format(extension_name))


@bot.command()
@checks.is_owner()
async def reload(extension_name : str):
    """Unloads an extension."""
    bot.unload_extension(extension_name)
    try:
        bot.load_extension(extension_name)
    except (AttributeError, ImportError) as e:
        await bot.say("```py\n{}: {}\n```".format(type(e).__name__, str(e)))
        return
    await bot.say("{} reloaded.".format(extension_name))


@bot.command()
@checks.is_owner()
async def unload(extension_name : str):
    bot.unload_extension(extension_name)
    await bot.say("{} unloaded.".format(extension_name))

@bot.command()
async def invite():
    """Sends an invite link for you to invite me to your personal server."""
    await bot.say(
        'E-excuse me senpai, if you want me on your server, simply click this l-link and select a server where you have t-the "Manage server" role...\n'
        'https://discordapp.com/oauth2/authorize?&bot_id={}}&scope=bot&permissions=-1\n'.format(bot.bot_id))


@bot.command()
async def botabout():
    """I'll tell a little about myself."""
    uptime = datetime.datetime.now() - starttime
    ucounter = 0
    for _ in bot.get_all_members():
        ucounter += 1
    ccounter = 0
    for _ in bot.get_all_channels():
        ccounter += 1
    scounter = 0
    for _ in bot.servers:
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
    await bot.say(fmt.format(bot.user, uptime, scounter, ccounter, ucounter))


def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    print('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))


if __name__ == '__main__':
    credentials = load_credentials()
    bot.bot_id = credentials['client_id']
    for extension in initial_extensions:
        try:
            bot.load_extension(extension)
        except:
            PrintException()

    bot.run(credentials['token'])
    handlers = log.handlers[:]
    for hdlr in handlers:
        hdlr.close()
        log.removeHandler(hdlr)
        