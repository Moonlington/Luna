import discord
from discord.ext import commands
from cogs.utils import checks
import os
import random
import copy
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from itertools import islice, cycle, tee
from textblob import TextBlob
from io import BytesIO
import re
import asyncio
import textblob
import aiohttp
from PIL import Image, ImageDraw, ImageFont

if not os.path.exists('discord.tags'):
    open('discord.tags', 'w').close()

if not os.path.exists('overrides.tags'):
    open('overrides.tags', 'w').close()


class CallLine:

    def __init__(self, _client, message, name):
        self.client = _client
        self.channels = [message.channel]
        self.name = name
        self.calling = self.client.loop.create_task(self.call_task())

    def __str__(self):
        return self.name

    async def sendOtherChannels(self, origin, what):
        otherchannels = [c for c in self.channels if c != origin]
        if otherchannels:
            tasks = [
                asyncio.ensure_future(
                    self.client.send_message(
                        ochannel,
                        what)) for ochannel in otherchannels]
            await asyncio.wait(tasks)
        else:
            return

    async def addChannel(self, channel):
        if channel in self.channels:
            await self.client.send_message(channel, "This channel is already in call-line `{}`".format(self.name))
        else:
            self.channels.append(channel)
            await self.client.send_message(channel, "Connected to call-line `{}`".format(self.name))
            await self.sendOtherChannels(channel, "Someone connected to the call-line `{}`...".format(self.name))

    async def removeChannel(self, channel):
        if channel in self.channels:
            self.channels.remove(channel)
            await self.client.send_message(channel, "Disconnected from call-line `{}`".format(self.name))
            await self.sendOtherChannels(channel, "Someone disconnected from the call-line `{}`...".format(self.name))
        else:
            await self.client.send_message(channel, "This channel is not connected to call-line `{}`".format(self.name))

    async def call_task(self):
        while True:
            callchannels = self.channels
            user = self.client.user
            if len(self.channels) == 0:
                del self.call_lines[self.name]
                break
            else:
                message = await self.client.wait_for_message(timeout=10, check=lambda m: m.channel in callchannels and m.author != user and not m.content.startswith('&'))
                if message is not None:
                    await self.sendOtherChannels(message.channel, "📞**{}**: {}".format(self.name, message.clean_content))
                else:
                    continue


class LsgPlayer:

    def __init__(self, client, member):
        self.client = client
        self.member = member
        self.health = 100
        self.hunger = 0
        self.starving = False
        # self.morale = 100
        self.equippeditem = None

    def __str__(self):
        fmt = "+ {0.display_name} - Health: {1}, Hunger: {2}"
        return fmt.format(self.member, self.health, self.hunger)

    def changeHealth(self, amount):
        self.health += amount
        if self.health > 100:
            self.health = 100

    def changeHunger(self, amount):
        self.hunger += amount
        if self.hunger < 0:
            self.hunger = 0

    def checkStarving(self, death=False):
        if self.hunger >= 6:
            self.starving = True
            return True

        else:
            self.starving = False
            return False

    def setEquipped(self, item):
        self.equippeditem = item


class LsgGame:

    def __init__(self, client, players, channel):
        self.client = client
        self.channel = channel
        self.players = players
        self.teaminventory = [('food', 15), ('wood', 5)]
        self.gametask = None
        self.playing = False
        self.day = 1
        self.radiostat = 0
        self.temperature = 12.0
        self.gunUsed = False
        self.coldnessmod = 1.0
        self.deletelist = []
        self.waitingfor = None
        self.kyslist = []
        self.log = []
        self.chooselog = []

    def returnMembers(self):
        return [p.member for p in self.players]

    def changeItem(self, item, amount):
        found = False
        for i, titem in enumerate(self.teaminventory):
            if item == titem[0]:
                newamount = titem[1] + amount
                if newamount <= 0:
                    self.teaminventory.remove(titem)
                else:
                    self.teaminventory.insert(i, (titem[0], newamount))
                    self.teaminventory.remove(titem)
                found = True
        if not found:
            self.teaminventory.append((item, amount))

    def getItem(self, itemname):
        for titem in self.teaminventory:
            if titem[0] == itemname:
                return titem[1]
        else:
            return 0

    async def playerDeath(self, player, message='- {} died'):
        await self.pm(player, "```diff\nYou died! The rest will have to go on without you.```")
        self.log.append(message.format(player.member.display_name))
        self.deletelist.append(player)
        if len(self.players) == 0:
            await self.loseGame()

    def lsgMessage(self, header, message):
        fmt = "```diff\n!{:=^50}!\n{}\n!{:=^50}!```"
        return fmt.format("[{}]".format(header), message, '')

    async def passDay(self):
        foodeaten = 0
        gothungry = []
        for player in self.players:
            wantedtoeat = random.randint(1, 3)
            foodeaten += wantedtoeat
            startingfood = self.getItem('food')
            if player.starving:
                if player.checkStarving():
                    await self.playerDeath(player, message='- {} died of starvation')
                    continue
            else:
                if player.checkStarving():
                    self.log.append(
                        '- WARNING: {} is starving! Next day he/she will die!'.format(player.member.display_name))
            if wantedtoeat > self.getItem('food'):
                gothungry.append(player)
                self.changeItem('food', self.getItem('food'))
                player.changeHunger(wantedtoeat)
            else:
                player.changeHunger(-wantedtoeat * 2)
                self.changeItem('food', -wantedtoeat)
        else:
            if gothungry:
                foodeaten = startingfood
            self.log.append('! Your group ate {} food ({} left)'.format(
                foodeaten, self.getItem('food')))
            if gothungry:
                self.log.append("- {} got hungry cause there was not enough food!".format(
                    " and ".join([p.member.display_name for p in gothungry])))
        self.temperature -= 2.0 * self.coldnessmod
        if self.temperature <= -5.0:
            damage = -3 * (int(self.temperature) + 5)
            self.log.append(
                '- You all begin to freeze... (- {} health to all)'.format(damage))
            for player in self.players:
                player.changeHealth(-damage)
        if self.temperature <= 0:
            self.log.append('- You all begin to get cold...')
            self.coldnessmod += 0.1
        if self.kyslist:
            tasks = [
                asyncio.ensure_future(
                    self.playerDeath(
                        player,
                        message='- {} committed suicide...')) for player in self.kyslist]
            await asyncio.wait(tasks)
        for player in self.players:
            if player.health <= 0:
                await self.playerDeath(player)
        random.shuffle(self.players)
        fmtlog = self.lsgMessage('Day {} log, Radio: {}'.format(self.day, str(self.radiostat) + '%'), "\n".join(
            self.log) + '\n! Next queue: ' + ' -> '.join([p.member.display_name for p in self.players]))
        fmtlog += self.lsgMessage('Stats', "\n".join(
            [str(p) for p in self.players if p not in self.deletelist]) + '\nTemp: {}° C'.format(round(self.temperature, 1)))
        await self.sayToAll(fmtlog)
        if self.radiostat >= 100:
            await self.winGame()
        if self.deletelist:
            for player in self.deletelist:
                self.players.remove(player)
        self.day += 1
        self.log = []
        self.deletelist = []
        self.kyslist = []
        self.chooselog = []
        self.gunUsed = False
        # save_pkl(currentgames, 'currentgames')

    async def winGame(self):
        await self.say(self.lsgMessage("You won!", """After successfully repairing the radio you hear a noise coming from it.
This strange noise becomes a voice and it's clearly asking who this is.
You and the others call for help, the one coming from the radio says: 'We... will... send... help...'
You and the others cheer in happiness as you see the ship landing in front of you.
The end.

THANKS FOR PLAYING AND ACTUALLY WINNING!"""))
        self.playing = False

    async def loseGame(self):
        await self.say(self.lsgMessage("You lose!", """Everyone's dead.
Try better.
Git gud
(sorry i need a good story for this)"""))
        self.playing = False

    async def sayToAll(self, message):
        tasks = [
            asyncio.ensure_future(
                self.client.send_message(
                    player.member,
                    message)) for player in self.players]
        await asyncio.wait(tasks)

    async def say(self, message):
        await self.client.send_message(self.channel, message)

    async def pm(self, user, message):
        await self.client.send_message(user.member, message)

    async def startgame(self):
        await self.say(self.lsgMessage("Intro", """You and 3 others have stranded in the middle of a tundra.
Together you will gather food and try to survive as long as possible.
You can also try to fix your friend's radio, which you can use to call for help.
+ You have 15 pieces of food and water is plenty.
+ You also have a hunting rifle, which will help with hunting.
HOW TO PLAY:
You get a DM from Luna, telling you what you can do at the moment.
Lets say you want to choose option 1, gather food.
You send a DM to luna with the content '&1'. It's that simple"""))
        self.playing = True
        self.gametask = self.client.loop.create_task(self.game_task())

    async def game_task(self):
        while self.playing:
            for player in self.players:
                self.waitingfor = player
                if self.chooselog:
                    chosen = "\nOthers have chosen:\n" + \
                        "\n".join(self.chooselog)
                else:
                    chosen = ''
                await self.pm(player, self.lsgMessage('Day {}'.format(self.day), """You can choose from a few choices:
&1 Gather for food (+ food) (Gun is {0})
&2 Gather for wood (+ wood)
&3 Light the fire (+ temp, - 2 wood ({2} left))
&4 Try to repair the radio
&5 Sleep (+ health)
&suicide Commit suicide, pls dont tho. (+ instant death){1}""".format("not used, use '&1+gun' to use the gun" if not self.gunUsed else "used, sorry", chosen, self.getItem('wood'))))
                choices = ['&1', '&2', '&3', '&4', '&5', '&suicide']
                if not self.gunUsed:
                    choices.append('&1+gun')
                kyslist = []
                choice = await self.client.wait_for_message(timeout=60, author=player.member, check=lambda m: m.channel.is_private and m.content in choices)
                if choice is None:
                    await self.pm(player, '```You did nothing```')
                    self.log.append('! {} didn\'t do anything, he might be AFK'.format(
                        player.member.display_name))
                    self.chooselog.append(
                        '+ {} has chosen nothing'.format(player.member.display_name))
                    continue

                if choice.content == '&1':
                    chance = random.randint(1, 100)
                    if chance <= 15:
                        damage = random.randint(30, 50)
                        player.changeHealth(-damage)
                        self.log.append('- {} got bitten by some wolves while he/she was gathering, he/she came back with no food (-{} Health)'.format(
                            player.member.display_name, damage))
                    elif chance <= 15 + 25:
                        self.log.append(
                            '- {} dropped the food while he/she was coming back.'.format(player.member.display_name))
                    else:
                        amountfound = random.randint(2, 5)
                        self.changeItem('food', amountfound)
                        self.log.append(
                            '+ {} gathered some food. (+{} food)'.format(player.member.display_name, amountfound))
                    self.chooselog.append(
                        '+ {} has chosen to gather food.'.format(player.member.display_name))
                    await self.pm(player, '```You\'ve chosen to gather some food...```')

                elif choice.content == '&1+gun':
                    chance = random.randint(1, 100)
                    if chance <= 3:
                        player.changeHealth(-90)
                        self.log.append(
                            '- {} was shooting an animal when he/she accidentaly shot himself, he/she is SERIOUSLY injured (-90 Health)'.format(player.member.display_name))
                    elif chance <= 3 + 15:
                        damage = random.randint(15, 25)
                        amountfood = random.randint(4, 6)
                        self.changeItem('food', amountfood)
                        player.changeHealth(-damage)
                        self.log.append('+ {} got bitten by some wolves while he/she was gathering but he/she shot them down and got food from them (-{} Health, +{} food)'.format(
                            player.member.display_name, damage, amountfood))
                    elif chance <= 3 + 15 + 15:
                        self.log.append(
                            '- {} dropped the food while he/she was coming back.'.format(player.member.display_name))
                    else:
                        amountfound = random.randint(1, 4)
                        amountfound += random.randint(1, 3)
                        self.changeItem('food', amountfound)
                        self.log.append('+ {} gathered some food with the gun. (+{} food)'.format(
                            player.member.display_name, amountfound))
                    self.chooselog.append(
                        '+ {} has chosen to gather food with the gun.'.format(player.member.display_name))
                    self.gunUsed = True
                    await self.pm(player, '```You\'ve chosen to gather some food with the gun...```')

                elif choice.content == '&2':
                    chance = random.randint(1, 100)
                    if chance <= 15:
                        damage = random.randint(30, 50)
                        player.changeHealth(-damage)
                        self.log.append('- {} got bitten by some wolves while he/she was gathering, he/she came back with no wood (-{} Health)'.format(
                            player.member.display_name, damage))
                    elif chance <= 15 + 25:
                        damage = random.randint(5, 15)
                        player.changeHealth(-damage)
                        amountwood = random.randint(1, 3)
                        self.changeItem('wood', amountwood)
                        self.log.append('- {} got splinters in his fingers while gathering wood. (+{} wood, -{} health)'.format(
                            player.member.display_name, amountwood, damage))
                    else:
                        amountwood = random.randint(1, 3)
                        self.changeItem('wood', amountwood)
                        self.log.append(
                            '+ {} gathered some wood. (+ {} wood)'.format(player.member.display_name, amountwood))
                    self.chooselog.append(
                        '+ {} has chosen to gather wood.'.format(player.member.display_name))
                    await self.pm(player, '```You\'ve chosen to gather some wood...```')

                elif choice.content == '&3':
                    chance = random.randint(1, 100)
                    if chance <= 15:
                        damage = random.randint(30, 50)
                        player.changeHealth(-damage)
                        tempgot = random.randint(2.0, 4.0)
                        self.changeItem('wood', -2)
                        self.temperature += tempgot
                        self.log.append('- {} burned himself while lighting the fire (-{} Health, -2 wood, +{} temp)'.format(
                            player.member.display_name, damage, tempgot))
                    else:
                        tempgot = random.randint(2.0, 4.0)
                        self.temperature += tempgot
                        self.changeItem('wood', -2)
                        self.log.append(
                            '+ {} lighted the fire. (- 2 wood, +{} temp)'.format(player.member.display_name, tempgot))
                    self.chooselog.append(
                        '+ {} has chosen to light the fire.'.format(player.member.display_name))
                    await self.pm(player, '```You\'ve chosen to light the fire...```')

                elif choice.content == '&4':
                    chance = random.randint(1, 100)
                    if chance <= 10:
                        amountrepaired = random.randint(1, 3)
                        self.radiostat -= amountrepaired
                        self.log.append('- {} tried to repair the radio, but failed horribly. (- {} repaired)'.format(
                            player.member.display_name, str(amountrepaired) + '%'))
                    else:
                        amountrepaired = random.randint(1, 3)
                        self.radiostat += amountrepaired
                        self.log.append('+ {} repaired the radio a little. (+ {} repaired)'.format(
                            player.member.display_name, str(amountrepaired) + '%'))
                    self.chooselog.append(
                        '+ {} has chosen to repair the radio.'.format(player.member.display_name))
                    await self.pm(player, '```You\'ve chosen to repair the radio...```')

                elif choice.content == '&5':
                    chance = random.randint(1, 100)
                    if chance <= 20:
                        self.log.append(
                            '- {} had nightmares while sleeping, he didn\'t sleep well...'.format(player.member.display_name))
                    else:
                        amounthealed = random.randint(10, 25)
                        player.changeHealth(amounthealed)
                        self.log.append('+ {} slept and healed up a bit (+ {} health)'.format(
                            player.member.display_name, amounthealed))
                    self.chooselog.append(
                        '+ {} decided to sleep this day'.format(player.member.display_name))
                    await self.pm(player, '```You\'ve chosen to sleep today...```')

                elif choice.content == '&suicide':
                    await self.pm(player, '```You\'ve chosen to commit suicide...```')
                    self.kyslist.append(player)
                    self.chooselog.append(
                        '- {} decided to commit suicide'.format(player.member.display_name))
            else:
                await self.passDay()

currentgames = []

def setup(bot):
    bot.add_cog(Funstuff(bot))


class Funstuff:

    def __init__(self, bot):
        self.bot = bot
        self.initiating = {}
        self.call_lines = {}
        self.rrgroup = []
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

    def lookupid(self, _id):
        user = discord.utils.get(self.bot.get_all_members(), id=_id)
        return user

    @commands.group(aliases=['t'], pass_context=True, invoke_without_command=True)
    async def tag(self, ctx, tagcalled: str=None, *args):
        """Luna's very own tag system, totally didn't rip off Spectra..."""
        def jagtagparser(content, args):
            def evaluateStatement(statement):
                index = statement.find('|=|')
                if index == -1:
                    index = statement.find('|<|')
                if index == -1:
                    index = statement.find('|>|')
                if index == -1:
                    index = statement.find('|~|')
                if index == -1:
                    index = statement.find('|?|')
                if index == -1:
                    return False
                s1 = statement[0:index]
                s2 = statement[index + 3:]
                try:
                    i1 = float(s1)
                    i2 = float(s2)
                    if statement[index:index + 3] == "|=|":
                        return i1 == i2
                    elif statement[index:index + 3] == "|~|":
                        return i1 * 100 == i2 * 100
                    elif statement[index:index + 3] == "|>|":
                        return i1 > i2
                    elif statement[index:index + 3] == "|<|":
                        return i1 < i2
                except ValueError:
                    if statement[index:index + 3] == "|=|":
                        return s1 == s2
                    elif statement[index:index + 3] == "|~|":
                        return s1.lower() == s2.lower()
                    elif statement[index:index + 3] == "|>|":
                        return s1 > s2
                    elif statement[index:index + 3] == "|<|":
                        return s1 < s2
                    elif statement[index:index + 3] == "|?|":
                        return bool(re.search(s2, s1))

            def evaluateMath(statement):
                index = statement.find('|+|')
                if index == -1:
                    index = statement.find('|-|')
                if index == -1:
                    index = statement.find('|*|')
                if index == -1:
                    index = statement.find('|%|')
                if index == -1:
                    index = statement.find('|/|')
                if index == -1:
                    return statement
                s1 = evaluateMath(statement[0:index])
                s2 = evaluateMath(statement[index + 3:])
                try:
                    i1 = float(s1)
                    i2 = float(s2)
                    print(i1, i2)
                    if statement[index:index + 3] == "|+|":
                        return str(i1 + i2)
                    elif statement[index:index + 3] == "|-|":
                        return str(i1 - i2)
                    elif statement[index:index + 3] == "|*|":
                        return str(i1 * i2)
                    elif statement[index:index + 3] == "|%|":
                        return str(i1 % i2)
                    elif statement[index:index + 3] == "|/|":
                        return str(i1 / i2)
                except ValueError:
                    if statement[index:index + 3] == "|+|":
                        return s1 + s2
                    elif statement[index:index + 3] == "|-|":
                        loc = s1.find(s2)
                        if loc != -1:
                            return s1[0:loc] + (s1[loc + len(s2)] if loc + len(s2) < len(s1) else "")
                        else:
                            return s1 + '-' + s2
                    elif statement[index:index + 3] == "|*|":
                        return s1 + '*' + s2
                    elif statement[index:index + 3] == "|%|":
                        return s1 + '%' + s2
                    elif statement[index:index + 3] == "|/|":
                        return s1 + '/' + s2

            content = content.replace("{user}", ctx.message.author.name).replace("{userid}", ctx.message.author.id).replace("{nick}", ctx.message.author.display_name).replace("{discrim}", str(ctx.message.author.discriminator)).replace("{server}", ctx.message.server.name if ctx.message.server is not None else "Direct Message").replace("{serverid}", ctx.message.server.id if ctx.message.server is not None else "0").replace("{servercount}", str(len(ctx.message.server.members)) if ctx.message.server is not None else "1").replace("{channel}", ctx.message.channel.name if ctx.message.server is not None else "Direct Message").replace(
                "{channelid}", ctx.message.channel.id if ctx.message.server is not None else "0").replace("{randuser}", random.choice(list(ctx.message.server.members)).display_name if ctx.message.server is not None else ctx.message.author.display_name).replace("{randonline}", random.choice([m for m in ctx.message.server.members if m.status is discord.Status.online]).display_name if ctx.message.server is not None else ctx.message.author.display_name).replace("{randchannel}", random.choice(list(ctx.message.server.channels)).name if ctx.message.server is not None else "Direct Message").replace("{args}", " ".join(args)).replace("{argslen}", str(len(args))).replace('{avatar}', ctx.message.author.avatar_url)
            output = content
            toEval = ""
            iterations = 0
            lastoutput = ""
            variables = {}
            while lastoutput != output and iterations < 200:
                lastoutput = output
                iterations += 1
                i1 = output.find("}")
                i2 = -1 if i1 == -1 else output.rfind("{", 0, i1)
                if i1 != -1 and i2 != -1:
                    toEval = output[i2 + 1:i1]
                    if toEval.startswith('length:'):
                        toEval = str(len(toEval[7:]))

                    elif toEval.startswith('arg:'):
                        try:
                            argget = int(toEval[4:])
                            if not args:
                                toEval = ""
                            else:
                                toEval = next(
                                    islice(cycle(args), argget, argget + 1))
                        except ValueError:
                            pass

                    elif toEval.startswith("choose:"):
                        choices = toEval[7:]
                        choices = choices.split('|')
                        toEval = random.choice(choices)

                    elif toEval.startswith("if:"):
                        index1 = toEval.find('|then:')
                        index2 = toEval.find('|else:', index1)
                        if index1 != -1 and index2 != -1:
                            statement = toEval[3:index1]
                            sthen = toEval[index1 + 6:index2]
                            selse = toEval[index2 + 6:]
                            if evaluateStatement(statement):
                                toEval = sthen
                            else:
                                toEval = selse

                    elif toEval.startswith('range:'):
                        evalrange = toEval[6:]
                        int1, int2 = evalrange.split('|', 1)
                        if int1.isdigit() and int2.isdigit():
                            toEval = str(random.randint(int(int1), int(int2)))

                    elif toEval.startswith('upper:'):
                        toEval = toEval[6:]
                        toEval = toEval.upper()

                    elif toEval.startswith('lower:'):
                        toEval = toEval[6:]
                        toEval = toEval.lower()

                    elif toEval.startswith('replaceregex:'):
                        index1 = toEval.find('|with:')
                        index2 = toEval.find('|in:', index1)

                        if index1 != -1 and index2 != -1:
                            rep = toEval[13:index1]
                            rwith = toEval[index1 + 6:index2]
                            rin = toEval[index2 + 4:]
                            if len(rep) > 0:
                                toEval = re.sub(rep.replace("\u0013", "{").replace(
                                    "\u0014", "}"), re.sub("\$(\d+)", "\\\1", rwith), rin)

                    elif toEval.startswith('replace:'):
                        index1 = toEval.find('|with:')
                        index2 = toEval.find('|in:', index1)
                        if index1 != -1 and index2 != -1:
                            rep = toEval[8:index1]
                            rwith = toEval[index1 + 6:index2]
                            rin = toEval[index2 + 4:]
                            if len(rep) > 0:
                                toEval = rin.replace(rep, rwith)

                    elif toEval.startswith('set:'):
                        variable, stuff = toEval[4:].split('|', 1)
                        variables[variable] = stuff
                        toEval = ''

                    elif toEval.startswith('get:'):
                        variable = toEval[4:]
                        toEval = variables.get(variable, '')

                    elif toEval.startswith('user:'):
                        query = toEval[5:]
                        if not query:
                            toEval = ""
                        else:
                            users = None
                            if ctx.message.server is not None:
                                users = self.findUsers(
                                    query, ctx.message.server)
                            if users is None or not users:
                                users = self.findUserseverywhere(query)
                            if not users:
                                return '⚠ No users found matching "{}"'.format(query)
                            elif len(users) > 1:
                                out = '⚠ Multiple users found matching "{}":'.format(
                                    query)
                                for u in users[:6]:
                                    out += "\n - {}".format(str(u))
                                if len(users) > 6:
                                    out += "\n And {} more...".format(
                                        str(len(users) - 6))
                                return out

                            toEval = users[0].name

                    elif toEval.startswith('nick:'):
                        query = toEval[5:]
                        if not query:
                            toEval = ""
                        else:
                            users = None
                            if ctx.message.server is not None:
                                users = self.findUsers(
                                    query, ctx.message.server)
                            if users is None or not users:
                                users = self.findUserseverywhere(query)
                            if not users:
                                return '⚠ No users found matching "{}"'.format(query)
                            elif len(users) > 1:
                                out = '⚠ Multiple users found matching "{}":'.format(
                                    query)
                                for u in users[:6]:
                                    out += "\n - {}".format(str(u))
                                if len(users) > 6:
                                    out += "\n And {} more...".format(
                                        str(len(users) - 6))
                                return out

                            toEval = users[0].display_name

                    elif toEval.startswith('url:'):
                        toEval = toEval[4:].replace(
                            '-', '--').replace('_', "__").replace('%', '~p').replace('?', '~q').replace(" ", "_")

                    elif toEval.startswith('math:'):
                        toEval = evaluateMath(toEval[5:])

                    elif toEval.startswith('note:'):
                        toEval = ''

                    else:
                        toEval = "\u0013" + toEval + "\u0014"

                    output = output[0:i2] + toEval + output[i1 + 1:]
            return output.replace("\u0013", "{").replace("\u0014", "}")

        if tagcalled is None:
            await self.bot.say("Use `&help tag` for the subcommands.")
        with open("overrides.tags", "rb+") as file:
            found = False
            for line in file:
                aid, tagname, content = line.decode('utf8').split('\u2E6F')
                if tagcalled.lower() == tagname.lower() and ctx.message.server.id == aid:
                    content = content.replace('\u2E6E', '\n')
                    await self.bot.say(jagtagparser(content, args))
                    found = True
                    break
            if not found:
                with open('discord.tags', 'rb+') as file:
                    found = False
                    for line in file:
                        aid, tagname, content = line.decode(
                            'utf8').split('\u2E6F')
                        if tagcalled.lower() == tagname.lower():
                            content = content.replace('\u2E6E', '\n')
                            await self.bot.say(jagtagparser(content, args))
                            found = True
                            break
                    if not found:
                        await self.bot.say('That is not a known tag, use `&help tag` for more information')

    @tag.command(name='create', pass_context=True)
    async def _create(self, ctx, tagname: str, *, content: str):
        with open('discord.tags', 'rb+') as file:
            found = False
            for line in file:
                aid, tagnamef, contentf = line.decode('utf8').split('\u2E6F')
                if tagname.lower() == tagnamef.lower():
                    found = True
                    await self.bot.say("Tag **{}** already exists!".format(tagnamef))
                    break
            if not found:
                with open('discord.tags', 'ab') as file:
                    content = content.replace('\n', '\u2E6E')
                    file.write('{}\u2E6F{}\u2E6F{}\n'.format(
                        ctx.message.author.id, tagname, content).encode('utf8'))
                    await self.bot.say("Successfully created tag **{}**".format(tagname))

    @tag.command(name='delete', pass_context=True, aliases=['remove'])
    async def _delete(self, ctx, tagname: str):
        def deletetag(name):
            f = open("discord.tags", "rb+")
            d = f.readlines()
            f.seek(0)
            for i in d:
                aid, tagnamef, contentf = i.decode('utf8').split('\u2E6F')
                if name.lower() != tagnamef.lower():
                    f.write(i)
            f.truncate()
            f.close()

        with open('discord.tags', 'rb+') as file:
            found = False
            lines = file.readlines()
            file.seek(0)
            for line in lines:
                aid, tagnamef, contentf = line.decode('utf8').split('\u2E6F')
                if tagname.lower() == tagnamef.lower():
                    found = True
                    if ctx.message.author.id == aid:
                        deletetag(tagname)
                        await self.bot.say("Successfully deleted tag **{}**".format(tagnamef))
                        break
                    else:
                        await self.bot.say("That tag doesn't belong to you!")
                        break
            if not found:
                await self.bot.say("That tag doesn't exist!")

    @tag.command(name='list', pass_context=True)
    async def _taglist(self, ctx, *, name: str=None):
        with open('discord.tags', 'rb+') as file:
            person = ctx.message.author
            if name is not None:
                users = None
                if ctx.message.server is not None:
                    users = self.findUsers(name, ctx.message.server)
                if users is None or not users:
                    users = self.findUserseverywhere(name)
                if not users:
                    await self.bot.say('⚠ No users found matching "{}"'.format(name))
                    return
                elif len(users) > 1:
                    out = '⚠ Multiple users found matching "{}":'.format(name)
                    for u in users[:6]:
                        out += "\n - {}".format(str(u))
                    if len(users) > 6:
                        out += "\n And {} more...".format(str(len(users) - 6))
                    await self.bot.say(out)
                    return
                person = users[0]
            personid = person.id
            lines = file.readlines()
            file.seek(0)
            taglist = []
            for line in lines:
                aid, tagnamef, contentf = line.decode('utf8').split('\u2E6F')
                if personid == aid:
                    taglist.append(tagnamef)
            await self.bot.say("__**{}'s** list of {} tag{}:__\n{}".format(person.name, len(taglist), '' if len(taglist) == 1 else 's', " ".join(taglist)))

    @tag.command(name='edit', pass_context=True)
    async def _edit(self, ctx, tagname: str, *, edittedcontent: str):
        def edittag(name, content):
            f = open("discord.tags", "rb+")
            d = f.readlines()
            f.seek(0)
            for i in d:
                aid, tagnamef, contentf = i.decode('utf8').split('\u2E6F')
                if name.lower() == tagnamef.lower():
                    content = content.replace('\n', '\u2E6E')
                    f.write('{}\u2E6F{}\u2E6F{}\n'.format(
                        aid, tagnamef, content).encode('utf8'))
                else:
                    f.write(i)
            f.truncate()
            f.close()

        with open('discord.tags', 'rb+') as file:
            found = False
            lines = file.readlines()
            file.seek(0)
            for line in lines:
                aid, tagnamef, contentf = line.decode('utf8').split('\u2E6F')
                if tagname.lower() == tagnamef.lower():
                    found = True
                    if ctx.message.author.id == aid:
                        edittag(tagname, edittedcontent)
                        await self.bot.say("Successfully edited tag **{}**".format(tagnamef))
                        break
                    else:
                        await self.bot.say("That tag doesn't belong to you!")
                        break
            if not found:
                await self.bot.say("That tag doesn't exist!")

    @tag.command(name='owner', pass_context=True)
    async def _owner(self, ctx, tagname: str):
        with open("overrides.tags", "rb+") as file:
            found = False
            for line in file:
                aid, tagnamef, contentf = line.decode('utf8').split('\u2E6F')
                if tagname.lower() == tagnamef.lower() and ctx.message.server.id == aid:
                    await self.bot.say("Tag **{}** is owned by the server *{}*".format(tagname, ctx.message.server.name))
                    found = True
                    break
            if not found:
                with open('discord.tags', 'rb+') as file:
                    found = False
                    lines = file.readlines()
                    file.seek(0)
                    for line in lines:
                        aid, tagnamef, contentf = line.decode(
                            'utf8').split('\u2E6F')
                        if tagname.lower() == tagnamef.lower():
                            found = True
                            owneruser = str(self.lookupid(aid))
                            await self.bot.say("Tag **{}** is owned by **{}**".format(tagnamef, owneruser))
                            break
                    if not found:
                        await self.bot.say("That tag doesn't exist!")

    @tag.command(name='raw', pass_context=True)
    async def _raw(self, ctx, tagname: str):
        with open('discord.tags', 'rb+') as file:
            found = False
            lines = file.readlines()
            file.seek(0)
            for line in lines:
                aid, tagnamef, contentf = line.decode('utf8').split('\u2E6F')
                if tagname.lower() == tagnamef.lower():
                    found = True
                    contentf = contentf.replace('\u2E6E', '\n')
                    await self.bot.say(contentf)
                    break
            if not found:
                await self.bot.say("That tag doesn't exist!")

    @tag.command(name='raw2', pass_context=True)
    async def _raw2(self, ctx, tagname: str):
        with open('discord.tags', 'rb+') as file:
            found = False
            lines = file.readlines()
            file.seek(0)
            for line in lines:
                aid, tagnamef, contentf = line.decode('utf8').split('\u2E6F')
                if tagname.lower() == tagnamef.lower():
                    found = True
                    contentf = contentf.replace('\u2E6E', '\n')
                    await self.bot.say('```' + contentf + '```')
                    break
            if not found:
                await self.bot.say("That tag doesn't exist!")

    @tag.command(name='search', pass_context=True)
    async def _search(self, ctx, search: str=None):
        with open('discord.tags', 'rb+') as file:
            lines = file.readlines()
            file.seek(0)
            listoftags = []
            if search is None:
                buf = BytesIO()
                for line in lines:
                    aid, tagnamef, contentf = line.decode(
                        'utf8').split('\u2E6F')
                    listoftags.append(tagnamef)
                buf.write("{} tags:\n{}".format(len(listoftags),
                                                " ".join(listoftags)).encode('utf-8'))
                buf.seek(0)
                await self.bot.upload(buf, filename="Search.txt", content="__**{}** tags found__".format(len(listoftags)))
            else:
                for line in lines:
                    aid, tagnamef, contentf = line.decode(
                        'utf8').split('\u2E6F')
                    if search.lower() in tagnamef.lower():
                        listoftags.append(tagnamef)
                if not listoftags:
                    await self.bot.say("No tags containing **{}**".format(search))
                else:
                    await self.bot.say("__**{}** tags found containing **{}**:__\n{}".format(len(listoftags), search, " ".join(listoftags)))

    @tag.command(name='override', pass_context=True)
    @checks.mod_or_permissions()
    async def _override(self, ctx, name, *, content=None):
        async def edittag(name, content):
            f = open("overrides.tags", "rb+")
            d = f.readlines()
            f.seek(0)
            for i in d:
                aid, tagnamef, contentf = i.decode('utf8').split('\u2E6F')
                if ctx.message.server.id == aid and tagnamef.lower() == name.lower():
                    if content is None:
                        await self.bot.say("Successfully removed the override for the tag **{}**".format(tagnamef))
                        continue
                    else:
                        content = content.replace('\n', '\u2E6E')
                        f.write('{}\u2E6F{}\u2E6F{}\n'.format(
                            aid, tagnamef, content).encode('utf8'))
                        await self.bot.say("Successfully edited the override for the tag **{}**".format(tagnamef))
                else:
                    f.write(i)
            f.truncate()
            f.close()

        with open('overrides.tags', 'rb+') as file:
            found = False
            lines = file.readlines()
            file.seek(0)
            for line in lines:
                aid, tagnamef, contentf = line.decode('utf8').split('\u2E6F')
                if ctx.message.server.id == aid and tagnamef.lower() == name.lower():
                    found = True
                    await edittag(name, content)
                    break
            if not found:
                if content is None:
                    await self.bot.say("I can't delete a tag override for a override that doesnt exist!".format(name))
                else:
                    with open('overrides.tags', 'ab') as file:
                        content = content.replace('\n', '\u2E6E')
                        file.write('{}\u2E6F{}\u2E6F{}\n'.format(
                            ctx.message.server.id, name, content).encode('utf8'))
                        await self.bot.say("Successfully overridden tag **{}**".format(name))

    @commands.command()
    async def hello(self):
        """Checks if I am alive."""
        await self.bot.say('Hi, I am alive!')

    @commands.command()
    async def lenny(self, eye=None, eye2=None):
        """It lennys, what else is it supposed to do?"""
        if eye is None and eye2 is None:
            await self.bot.say('( ͡° ͜ʖ ͡°)')
        elif eye2 is None:
            await self.bot.say('( ͡' + eye + ' ͜ʖ ͡' + eye + ')')
        else:
            await self.bot.say('( ͡' + eye + ' ͜ʖ ͡' + eye2 + ')')

    @commands.command()
    async def lennys(self, eye=None, eye2=None):
        """Same as lenny, but 2 lennys."""
        if eye is None and eye2 is None:
            await self.bot.say('( ͡ ° ͜ʖ ͡ °)  ( ͡°  ͜ʖ ͡°  )')
        elif eye2 is None:
            await self.bot.say('( ͡ ' + eye + ' ͜ʖ ͡  ' + eye + ')  ( ͡ ' + eye + '  ͜ʖ ͡ ' + eye + '  )')
        else:
            await self.bot.say('( ͡  ' + eye + ' ͜ʖ ͡  ' + eye2 + ')  ( ͡ ' + eye2 + '  ͜ʖ ͡ ' + eye + '  )')

    @commands.command(pass_context=True)
    async def glomp(self, ctx, *, who_to_glomp=None):
        """For that moment that you really want to glomp someone."""
        if who_to_glomp is not None:
            toglomp = who_to_glomp
            if toglomp is not None:
                await self.bot.say('*{} glomps {}*'.format(ctx.message.author.name, toglomp))
            else:
                await self.bot.say('*{} fell to the ground after trying to glomp someone that isnt there...*'.format(
                    ctx.message.author.name))
        else:
            await self.bot.say('*{} glomps {}*'.format(self.bot.user.name, ctx.message.author.name))

    @commands.command()
    async def reverse(self, *, to_reverse: str):
        """It reverses text."""
        text = to_reverse
        await self.bot.say(str(text)[::-1])

    @commands.command()
    async def respect(self):
        """For Moon Moon to know how good his bot is."""
        f = open('respects.txt', 'r+')
        respects = f.read()
        respects = int(respects)
        respects += 1
        f.seek(0)
        f.write(str(respects))
        f.close()
        await self.bot.say('Thank you!\n'
                           '**Total \"respects\" given:** ' + str(respects))

    @commands.command()
    async def execute(self, *, to_execute: str):
        """Executes people, Danganronpa style."""
        def make_execution(whotoexecute):
            img = Image.open('execution.jpg')
            imagesize = img.size
            whotoexecute += ' has been found guilty'
            fontsize = int(imagesize[1] / 5)
            font = ImageFont.truetype("/Library/Fonts/Pixelette.ttf", fontsize)
            bottomtextsize = font.getsize(whotoexecute)
            while bottomtextsize[0] > imagesize[0] - 20:
                fontsize -= 1
                font = ImageFont.truetype(
                    "/Library/Fonts/Pixelette.ttf", fontsize)
                bottomtextsize = font.getsize(whotoexecute)

            bottomtextpositionx = (imagesize[0] / 2) - (bottomtextsize[0] / 2)
            bottomtextpositiony = imagesize[1] - bottomtextsize[1] - 50
            bottomtextposition = (bottomtextpositionx, bottomtextpositiony)

            draw = ImageDraw.Draw(img)
            draw.text(bottomtextposition, whotoexecute,
                      (255, 255, 255), font=font)

            img.save("rip.png")

        meme = to_execute
        make_execution(meme)
        await self.bot.type()
        await self.bot.upload('rip.png')

    @commands.command(pass_context=True)
    async def rquote(self, ctx):
        """From a list of random quotes, it says one."""
        quotes = [
            'YOU THOUGHT THIS COMMENT WOULD MENTION [name] BUT IT WAS I, DIO!',
            'Even [name] didn\'t understand the usage of this command, However, [name] knew the truth! This command existed in order to be fun! The quotes that fueled the fun made this command exist! This command makes appear a random quote! he said.',
            'DID YOU QUOTE THIS TOO, [name]!? TELL ME!?\nWhat are you even asking? i settled this quote and you walked right into it!',
            'Even a bastard like me spot true evil when it sees it, true evil are those who use the weak for their own gain! Especially a innocent woman! And that is exactly what you\'ve done, isnt it [name]?!, thats why... I\'ll judge you myself!',
            'What is a [name]? A miserable little pile of secrets. But enough talk.',
            'Thank you [name]! But our Princess is in another castle!',
            'This is your fault. I\'m going to kill you. And all the [name] is gone. You don\'t even care, do you?',
            'The right man in the wrong place can make all the difference in the [name].',
            'I am the great mighty [name], and Im going to throw my shit at you.',
            'Why, that\'s the second biggest [name] head I\'ve ever seen!',
            'Look behind you, a three headed [name]!',
            'In the year 200x a super robot named [name] was created.',
            '[name] has been kidnapped by ninjas. Are you a bad enough dude to rescue the president?',
            'You were almost a [name] sandwich!',
            'All your [name] are belong to us.']
        i = random.randrange(len(quotes))
        quote = quotes[i]
        x = random.randrange(len(ctx.message.server.members))
        user = list(ctx.message.server.members)[x]
        fquote = quote.replace('[name]', user.name)
        await self.bot.say(fquote)

    @commands.group(pass_context=True)
    async def lsg(self, ctx):
        """Luna's very fun survival team-ish game-ish thing"""
        if ctx.invoked_subcommand is None:
            await self.bot.say('Use `&help lsg` to see the subcommands.')

    @lsg.command(name='start', pass_context=True)
    async def _start(self, ctx):
        """Initiates a LSG game"""
        if self.initiating.get(ctx.message.server.id, False):
            await self.bot.say("There's already a LSG initiating, wait until that game is done and then you can make your own")
        else:
            playerlist = [ctx.message.author]
            self.initiating[ctx.message.server.id] = True
            while len(playerlist) != 4:
                await self.bot.say("`[{}/4]`Alright, if you want to join this game, say `&yee`".format(len(playerlist)))
                addmsg = await self.bot.wait_for_message(timeout=600, channel=ctx.message.channel, content='&yee', check=lambda m: m.author not in playerlist)
                if addmsg is None:
                    self.initiating[ctx.message.server.id] = False
                    await self.bot.say("Not enough players to start! Stopping initializing...")
                    return
                else:
                    ingame = False
                    for game in currentgames:
                        for player in game.players:
                            if player.member == addmsg.author:
                                ingame = True
                    if not ingame:
                        playerlist.append(addmsg.author)
                    else:
                        await self.bot.say("You are already in a game! You can't join two games at the same time!")

            else:
                await self.bot.say('Alright we have four people: ```diff\n+ ' + "+ ".join(m.display_name + '\n' for m in playerlist) + "```\nI'll need confirmation from each of you to see if everything is correct. `&yee` for yes `&naw` for no")
                checklist = playerlist[:]
                count = 0
                cutoff = False
                while len(checklist) != 0 and not cutoff:
                    await self.bot.say("`[{}/4]`".format(count))
                    confirmmsg = await self.bot.wait_for_message(channel=ctx.message.channel, check=lambda m: (m.content == '&yee' or m.content == '&naw') and m.author in checklist)
                    count += 1
                    if confirmmsg.content == '&yee':
                        checklist.remove(confirmmsg.author)
                    else:
                        cutoff = True
                if cutoff:
                    await self.bot.say("Someone did not confirm! Exiting initiation...")
                    self.initiating[ctx.message.server.id] = False
                else:
                    userlist = []
                    for m in playerlist:
                        player = LsgPlayer(self.bot, m)
                        userlist.append(player)
                    else:
                        game = LsgGame(self.bot, userlist, ctx.message.channel)
                        currentgames.append(game)
                    await self.bot.say("Created the game! Game should start in 5 seconds...")
                    self.initiating = False
                    await asyncio.sleep(5)
                    await game.startgame()

    @lsg.command(name='test', pass_context=True)
    async def _test(self, ctx):
        """Initiates a 2 player LSG game, mostly used for testing."""
        if self.initiating.get(ctx.message.server.id):
            await self.bot.say("There's already a LSG initiating, wait untill that game is done and then you can make your own")
        else:
            playerlist = [ctx.message.author]
            self.initiating[ctx.message.server.id] = True
            while len(playerlist) != 2:
                await self.bot.say("`[{}/2]`Alright, if you want to join this game, say `&yee`".format(len(playerlist)))
                addmsg = await self.bot.wait_for_message(timeout=600, channel=ctx.message.channel, content='&yee', check=lambda m: m.author not in playerlist)
                if addmsg is None:
                    self.initiating[ctx.message.server.id] = False
                    await self.bot.say("Not enough players to start! Stopping initializing...")
                    return
                else:
                    ingame = False
                    for game in currentgames:
                        for player in game.players:
                            if player.member == addmsg.author:
                                ingame = True
                    if not ingame:
                        playerlist.append(addmsg.author)
                    else:
                        await self.bot.say("You are already in a game! You can't join two games at the same time!")

            else:
                await self.bot.say('Alright we have four people: ```diff\n+ ' + "+ ".join(m.display_name + '\n' for m in playerlist) + "```\nI'll need confirmation from each of you to see if everything is correct. `&yee` for yes `&naw` for no")
                checklist = playerlist[:]
                count = 0
                cutoff = False
                while len(checklist) != 0 and not cutoff:
                    await self.bot.say("`[{}/2]`".format(count))
                    confirmmsg = await self.bot.wait_for_message(channel=ctx.message.channel, check=lambda m: (m.content == '&yee' or m.content == '&naw') and m.author in checklist)
                    count += 1
                    if confirmmsg.content == '&yee':
                        checklist.remove(confirmmsg.author)
                    else:
                        cutoff = True
                if cutoff:
                    await self.bot.say("Someone did not confirm! Exiting initiation...")
                    self.initiating[ctx.message.server.id] = False
                else:
                    userlist = []
                    for m in playerlist:
                        player = LsgPlayer(self.bot, m)
                        userlist.append(player)
                    else:
                        game = LsgGame(self.bot, userlist, ctx.message.channel)
                        currentgames.append(game)
                    await self.bot.say("Created the game! Game should start in 5 seconds...")
                    self.initiating[ctx.message.server.id] = False
                    await asyncio.sleep(5)
                    await game.startgame()

    @lsg.command(name='waitingfor', pass_context=True)
    async def _waitingfor(self, ctx):
        """Lets you know what dude is being an asshole/is slow as fuck."""
        found = False
        for game in currentgames:
            if ctx.message.author in game.returnMembers():
                found = True
                if game.waitingfor.member is None:
                    pass
                else:
                    await self.bot.say('We are waiting for: ' + game.waitingfor.member.display_name)
        if not found:
            await self.bot.say('You are not in a game.')

    @commands.command()
    async def roll(self, dice: str):
        """Rolls a dice in NdN format."""
        try:
            rolls, limit = map(int, dice.split('d'))
        except Exception:
            await self.bot.say('Format has to be in NdN!')
            return

        result = ', '.join(str(random.randint(1, limit)) for _ in range(rolls))
        await self.bot.say(result)

    @commands.command()
    async def choose(self, *choices: str):
        """Chooses between multiple choices."""
        await self.bot.say(random.choice(choices))

    @commands.command()
    async def translate(self, language, *, text):
        """Translates text
        Usage: fromlang>tolang <text>
        for languagecodes, see https://cloud.google.com/translate/v2/translate-reference#supported_languages"""
        lang1, lang2 = language.split('>')
        if lang1 == '':
            yee = False
        else:
            yee = True
        try:
            if yee:
                translated = TextBlob(text).translate(
                    from_lang=lang1, to=lang2)
            else:
                translated = TextBlob(text).translate(to=lang2)
        except textblob.exceptions.NotTranslated:
            translated = text
        await self.bot.say(translated)

    @commands.group(pass_context=True)
    async def call(self, ctx):
        """A command which creates a call-line between channels, works cross-server"""
        if ctx.invoked_subcommand is None:
            await self.bot.say('Check `&help call` for the subcommands')

    @call.command(name='join', pass_context=True)
    async def _join(self, ctx, *, call_line: str):
        """Joins/creates a call-line between channels"""
        call_line = call_line.lower()
        if call_line == 'random':
            if len(self.call_lines) != 0:
                findcall = random.choice(list(self.call_lines))
                await self.call_lines[findcall].addChannel(ctx.message.channel)
            else:
                await self.bot.say("There are no call-lines open! You can make your own call-line with `&call join <name>`")
        else:
            findcall = self.call_lines.get(call_line)
            if findcall is None:
                self.call_lines[call_line] = CallLine(
                    self.bot, ctx.message, call_line)
                await self.bot.say("Connected to call-line `{}`".format(call_line))
            else:
                await findcall.addChannel(ctx.message.channel)

    @call.command(name='disconnect', pass_context=True)
    async def _disc(self, ctx, *, call_line: str):
        """Disconnects from a call-line"""
        call_line = call_line.lower()
        findcall = self.call_lines.get(call_line)
        if findcall is None:
            await self.bot.say("There is no call-line called `{}`".format(call_line))
        else:
            await findcall.removeChannel(ctx.message.channel)

    @call.command(name='list')
    async def _calllist(self):
        """Returns a list of current call-lines"""
        fmt = "__Current call-lines:__\nYou can make your own call-line with `&call join <name>`\n"
        if len(self.call_lines) != 0:
            for name, line in self.call_lines.items():
                fmt += '`{0}` - **{1}** channels connected\n'.format(
                    name, len(line.channels))
        else:
            fmt = "__Currently there are no call-lines__\nYou can make your own call-line with `&call join <name>`\n"
        await self.bot.say(fmt)

    @commands.command(pass_context=True)
    async def plotjoins(self, ctx):
        """Plots the joindates of everyone in the server"""
        sm = ctx.message.server.members
        x = sorted([m.joined_at for m in sm])
        y = range(len(x))
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d/%Y'))
        plt.plot(x, y)
        plt.gcf().autofmt_xdate()
        plt.title("Plot of joins from {}".format(ctx.message.server.name))
        buf = BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        await self.bot.upload(buf, filename='plot.png')
        buf.close()
        plt.close()

    @commands.command(pass_context=True)
    async def cats(self, ctx):
        async with aiohttp.get('http://random.cat/meow') as r:
            if r.status == 200:
                js = await r.json()
                await self.bot.say(js['file'])

    @commands.command(pass_context=True)
    async def glitch(self, ctx, imagelink: str, amount: int=None, seed: int=None, iterations: int=None):
        def pairwise(iterable):
            """Awesome function from the itertools cookbook
            https://docs.python.org/2/library/itertools.html
            s -> (s0,s1), (s1,s2), (s2, s3), ...
            """
            a, b = tee(iterable)
            next(b, None)
            return zip(a, b)


        class Glitchjpeg(object):

            def __init__(self, image_bytes, amount, seed, iterations):
                self.bytes = image_bytes
                self.new_bytes = None
                try:
                    self.header_length = self.get_header_length()
                except ValueError as e:
                    raise click.BadParameter(message=e.message)

                self.parameters = {
                    'amount': amount,
                    'seed': seed,
                    'iterations': iterations
                }

                self.glitch_bytes()

            def get_header_length(self):
                """Get the length of the header by searching sequential 0xFF 0xDA
                values. These values mark the end of a Jpeg header. We add two to give
                us a little leeway. We don't want to mess with the header.
                """

                for i, pair in enumerate(pairwise(self.bytes)):
                    if pair[0] == 255 and pair[1] == 218:
                        result = i + 2
                        return result

                raise ValueError('Not a valid jpg!')

            def glitch_bytes(self):
                """Glitch the image bytes, after the header based on the parameters.
                'Amount' is the hex value that will be written into the file. 'Seed'
                tweaks the index where the value will be inserted, rather than just a
                simple division by iterations. 'Iterations' should be self explanatory
                """

                amount = self.parameters['amount'] / 100
                seed = self.parameters['seed'] / 100
                iterations = self.parameters['iterations']

                # work with a copy of the original bytes. We might need the original
                # bytes around if we glitch it so much we break the file.
                new_bytes = copy.copy(self.bytes)
                new_bytes = bytearray(new_bytes)

                for i in (range(iterations)):
                    max_index = len(self.bytes) - self.header_length - 4

                    # The following operations determine where we'll overwrite a value
                    # Illustrate by example

                    # 36 = (600 / 50) * 3
                    px_min = int((max_index / iterations) * i)

                    # 48 = (600 / 50) * 3 + 1
                    px_max = int((max_index / iterations) * (i + 1))

                    # 12 = 48 - 36
                    delta = (px_max - px_min)  # * 0.8

                    # 36 + (12 * 0.8)
                    px_i = int(px_min + (delta * seed))

                    # If the index to be changed is beyond bytearray length file set
                    # it to the max index
                    if (px_i > max_index):
                        px_i = max_index

                    byte_index = self.header_length + px_i
                    new_bytes[byte_index] = int(amount * 256)

                self.new_bytes = new_bytes
        amount = random.randint(1,50) if amount is None else amount
        seed = random.randint(1,99) if seed is None else seed
        iterations = random.randint(1,500) if iterations is None else iterations

        async with aiohttp.get(imagelink) as r:
            data = await r.read()
            if not imagelink.endswith(".jpg"):
                stream = BytesIO(data)
                im = Image.open(stream)
                nstream = BytesIO()
                im.save(nstream, format="JPEG")
                data = nstream.getvalue()
            newbytes = BytesIO(Glitchjpeg(data, amount, seed, iterations).new_bytes)
            await self.bot.upload(newbytes, filename="Glitch.jpg", content="**Amount:** {}\n**Seed:** {}\n**Iterations:** {}".format(amount, seed, iterations))

    # @commands.group(pass_context=True, aliases=['rr'], invoke_without_command=True)
    # async def russianroulette(self, ctx, betamount: str, bulletcount: int):
    #     """Russian Roulette, cause why not."""
    #     if ctx.message.author.id in self.rrgroup:
    #         await self.bot.say("Dont spam it.")
    #     else:
    #         if self.c.execute("SELECT * FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone() is None:
    #             self.c.execute("INSERT INTO users VALUES (?, 1000, NULL, NULL)", [ctx.message.author.id])
    #             uid, money, times_died = self.c.execute("SELECT user_id, money, times_died FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone()
    #         else:
    #             uid, money, times_died = self.c.execute("SELECT user_id, money, times_died FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone()

    #         if betamount == "all":
    #             betamount = money
    #         elif betamount.isdigit():
    #             betamount = int(betamount)
    #         else:
    #             return

    #         if times_died is None:
    #             times_died = 0
    #         self.rrgroup.append(ctx.message.author.id)
    #         if betamount > money:
    #             await self.bot.say("You cant bet more than you have. (You have {} 💵)".format(money))
    #         elif betamount <= 0:
    #             await self.bot.say("You cant bet negative or no money.")

    #         elif bulletcount == 6:
    #             await self.bot.say("Do you want to kill yourself? You know a revolver only fits **6** bullets, right?")
    #         elif bulletcount > 6:
    #             await self.bot.say("A revolver only fits **6** bullets, not more.")
    #         elif bulletcount < 1:
    #             await self.bot.say("Why would you want a 100% win chance?")

    #         elif betamount > 20000 and bulletcount <= 2:
    #             await self.bot.say("Sorry but you can't bet over **20k** with less than 3 bullets.")                
    #         elif betamount > 5000 and bulletcount == 1:
    #             await self.bot.say("Sorry but you can't bet over **5k** with just one bullet.")
    #         else:
    #             m = await self.bot.say("{} shoots with {} bullet{} in the chamber... ({}/6 chance of winning)".format(ctx.message.author.mention, bulletcount, "s" if bulletcount > 1 else "", 6-bulletcount))
    #             roll = random.randint(0, 120)
    #             if roll >= 20 * bulletcount:
    #                 mon_mul = 6/(6-bulletcount)
    #                 newmoney = money - betamount + int(betamount*mon_mul)
    #                 await asyncio.sleep(2)
    #                 await self.bot.edit_message(m, m.content+"\n\nYou hear it click. You gained {} 💵 ({}*{}) `Total: {} 💵`".format(int(betamount*mon_mul), betamount, mon_mul, newmoney))
    #                 self.c.execute("UPDATE users SET money = ? WHERE user_id = ?", [newmoney, uid])

    #             else:
    #                 newmoney = money - betamount
    #                 await asyncio.sleep(random.randint(1,3))
    #                 send = m.content+"\n\nThere's blood everywhere, but *somehow* you survived. You lost {} 💵 `Left: {} 💵`".format(betamount, newmoney)
    #                 if newmoney == 0:
    #                     send += "\nYou seem to have lost everything. I'm not going to give you money, find someone to give you money."
    #                     self.c.execute("UPDATE users SET money = ?, times_died = ? WHERE user_id = ?", [newmoney, times_died+1, uid])
    #                 else:
    #                     self.c.execute("UPDATE users SET money = ? WHERE user_id = ?", [newmoney, uid])
    #                 await self.bot.edit_message(m, send)
            
    #         self.rrgroup.remove(ctx.message.author.id)


    # @russianroulette.command(pass_context=True, name="money")
    # async def _money(self, ctx):
    #     """Tells how much money you have"""
    #     if self.c.execute("SELECT * FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone() is None:
    #         self.c.execute("INSERT INTO users VALUES (?, 100, NULL, NULL)", [ctx.message.author.id])
    #         money = self.c.execute("SELECT money FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone()
    #     else:
    #         money = self.c.execute("SELECT money FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone()

    #     await self.bot.say("You have **{}** 💵".format(money[0]))

    # @russianroulette.command(pass_context=True, aliases=["lb"])
    # async def leaderboard(self, ctx):
    #     """Shows the global leaderboard"""
    #     data = self.c.execute("SELECT user_id, money, times_died FROM users ORDER BY money DESC LIMIT 10").fetchall()
    #     send = "__Current Russian Roulette leaderboard (R = Restarts)__\n"
    #     for uid, money, td in data:
    #         username = self.lookupid(uid).name
    #         send += "{} - **{}** 💵 (R: {})\n".format(username, money, td)
    #     await self.bot.say(send)

    # @russianroulette.command(pass_context=True)
    # @checks.is_owner()
    # async def award(self, ctx, amount: int, *, name: str):
    #     """Gives away free money, only the bot owner can use this."""
    #     users = None
    #     if ctx.message.server is not None:
    #         users = self.findUsers(name, ctx.message.server)
    #     if users is None or not users:
    #         users = self.findUserseverywhere(name)
    #     if not users:
    #         await self.bot.say('⚠ No users found matching "{}"'.format(name))
    #         return
    #     elif len(users) > 1:
    #         out = '⚠ Multiple users found matching "{}":'.format(name)
    #         for u in users[:6]:
    #             out += "\n - {}".format(str(u))
    #         if len(users) > 6:
    #             out += "\n And {} more...".format(str(len(users) - 6))
    #         await self.bot.say(out)
    #         return
    #     person = users[0]
    #     personid = person.id
    #     if self.c.execute("SELECT * FROM users WHERE user_id = ?", [personid]).fetchone() is None:
    #         self.c.execute("INSERT INTO users VALUES (?, 100, NULL, NULL)", [personid])
    #         money = self.c.execute("SELECT money FROM users WHERE user_id = ?", [personid]).fetchone()
    #     else:
    #         money = self.c.execute("SELECT money FROM users WHERE user_id = ?", [personid]).fetchone()
    #     self.c.execute("UPDATE users SET money = ? WHERE user_id = ?", [money[0] + amount, personid])
    #     await self.bot.say("Awarded {} **{}** 💵".format(person.name, amount))
    
    # @russianroulette.command(pass_context=True)
    # async def give(self, ctx, amount: int, *, name: str):
    #     """Gives money to someone else."""
    #     users = None
    #     if ctx.message.server is not None:
    #         users = self.findUsers(name, ctx.message.server)
    #     if users is None or not users:
    #         users = self.findUserseverywhere(name)
    #     if not users:
    #         await self.bot.say('⚠ No users found matching "{}"'.format(name))
    #         return
    #     elif len(users) > 1:
    #         out = '⚠ Multiple users found matching "{}":'.format(name)
    #         for u in users[:6]:
    #             out += "\n - {}".format(str(u))
    #         if len(users) > 6:
    #             out += "\n And {} more...".format(str(len(users) - 6))
    #         await self.bot.say(out)
    #         return
    #     person = users[0]
    #     personid = person.id

    #     if self.c.execute("SELECT * FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone() is None:
    #         self.c.execute("INSERT INTO users VALUES (?, 100, NULL, NULL)", [ctx.message.author.id])
    #         money = self.c.execute("SELECT money FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone()
    #     else:
    #         money = self.c.execute("SELECT money FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone()
    #     if amount > money[0]:
    #         await self.bot.say("You cant give more than you have. (You have {} 💵)".format(money[0]))
    #     elif amount <= 0:
    #         await self.bot.say("You cant give negative or no money.")
    #     else:
    #         self.c.execute("UPDATE users SET money = ? WHERE user_id = ?", [money[0] - amount, ctx.message.author.id])

    #         if self.c.execute("SELECT * FROM users WHERE user_id = ?", [personid]).fetchone() is None:
    #             self.c.execute("INSERT INTO users VALUES (?, 100, NULL, NULL)", [personid])
    #             money = self.c.execute("SELECT money FROM users WHERE user_id = ?", [personid]).fetchone()
    #         else:
    #             money = self.c.execute("SELECT money FROM users WHERE user_id = ?", [personid]).fetchone()
    #         self.c.execute("UPDATE users SET money = ? WHERE user_id = ?", [money[0] + amount, personid])

    #         await self.bot.say("{} gave {} **{}** 💵".format(ctx.message.author.name, person.name, amount))
    #     