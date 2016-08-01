from discord.ext import commands
import discord
from cogs.utils import checks
import datetime, re
import json, asyncio
import copy
import logging
import traceback
import sys

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


@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('--------------')
    print('In servers:')
    print("\n".join(s.name for s in client.servers if s.name))
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
@checks.is_owner
async def load(extension_name : str):
    """Loads an extension."""
    try:
        bot.load_extension(extension_name)
    except (AttributeError, ImportError) as e:
        await bot.say("```py\n{}: {}\n```".format(type(e).__name__, str(e)))
        return
    await bot.say("{} loaded.".format(extension_name))


@bot.command()
@checks.is_owner
async def unload(extension_name : str):
    """Unloads an extension."""
    bot.unload_extension(extension_name)
	await bot.say("{} unloaded.".format(extension_name))


@bot.command()
async def invite():
    """Sends an invite link for you to invite me to your personal server."""
    await bot.say(
        'E-excuse me senpai, if you want me on your server, simply click this l-link and select a server where you have t-the "Manage server" role...\n'
        'https://discordapp.com/oauth2/authorize?&client_id=170405995049254913&scope=bot&permissions=-1\n')


if __name__ == '__main__':
	credentials = load_credentials()
    bot.client_id = credentials['client_id']
    for extension in initial_extensions:
        try:
            bot.load_extension(extension)
        except Exception as e:
			print('Failed to load extension {}\n{}: {}'.format(extension, type(e).__name__, e))

	bot.run(credentials['token'])
    handlers = log.handlers[:]
    for hdlr in handlers:
        hdlr.close()
		log.removeHandler(hdlr)