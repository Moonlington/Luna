import asyncio
import copy
import datetime
import discord
import json
import linecache
import logging
import os
import re
import string
import sys
import traceback
import requests
from cogs.utils import checks
from ctypes.util import find_library
from discord.ext import commands

initial_extensions = [
    'cogs.Funstuff',
    'cogs.Gambling',
    'cogs.Music',
    'cogs.Searches',
    'cogs.Botrelated',
    'cogs.Mods'
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

bot.oldsay = bot.say

async def say(content):
    def SplitContent(content):
        content = content.replace("@everyone", "@\u200Beveryone").replace(
            "@here", "@\u200Bhere").strip()
        msgs = []
        while len(content) > 2000:
            leeway = 2000 - (len(content) % 2000)
            index = content.rfind("\n", 0, 2000)
            if index < leeway:
                index = content.rfind(" ", 0, 2000)
            if index < leeway:
                index = 2000
            temp = content[0:index].strip()
            if temp != "":
                msgs.append(temp)
            content = content[index:].strip()
        if content != "":
            msgs.append(content)
        return msgs
    for msg in SplitContent(content):
        messagesent = await bot.oldsay(msg)
    return messagesent

bot.say = say


@bot.event
async def on_command_error(error, ctx):
    if isinstance(error, commands.NoPrivateMessage):
        await bot.send_message(ctx.message.author, 'This command cannot be used in private messages.')
    elif isinstance(error, commands.DisabledCommand):
        await bot.send_message(ctx.message.author, 'Sorry. This command is disabled and cannot be used.')
    elif isinstance(error, commands.CommandInvokeError):
        print('In {0.command.qualified_name}:'.format(ctx), file=sys.stderr)
        traceback.print_tb(error.original.__traceback__)
        print('{0.__class__.__name__}: {0}'.format(
            error.original), file=sys.stderr)


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
                "https://github.com/SexualRhinoceros/MusicBot/raw/develop/libopus-0.{}.dll".format(
                    to_dl),
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

    log.info('{0.timestamp}: {0.author.name} in {1}: {0.content}'.format(
        message, destination))


def load_credentials():
    with open('credentials.json') as f:
        return json.load(f)


def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    print('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(
        filename, lineno, line.strip(), exc_obj))


if __name__ == '__main__':
    bot.bot_id = os.environ.get('LUNA_CLIENTID','')
    bot.starttime = datetime.datetime.now()
    for extension in initial_extensions:
        try:
            bot.load_extension(extension)
        except:
            PrintException()
    bot.run(os.environ.get('LUNA_TOKEN',''))
    handlers = log.handlers[:]
    for hdlr in handlers:
        hdlr.close()
        log.removeHandler(hdlr)
