import discord
from discord.ext import commands
from cogs.utils import checks
import random
import asyncio
import re
import sqlite3


def setup(bot):
    bot.add_cog(Gambling(bot))

def moneyparser(money):
    money = str(money)
    nmoney = ""
    if money.endswith("000000000000000"):
        nmoney = money[:-15] + "Q"
    elif money.endswith("000000000000"):
        nmoney = money[:-12] + "T"
    elif money.endswith("000000000"):
        nmoney = money[:-9] + "B"
    elif money.endswith("000000"):
        nmoney = money[:-6] + "M"
    elif money.endswith("000"):
        nmoney = money[:-3] + "K"
    else:
        nmoney = money

    if int(money) >= 1000000000:
        nmoney += " 💴"
    elif int(money) >= 1000000: 
        nmoney += " 💷"
    elif int(money) >= 1000:
        nmoney += " 💰"
    else:
        nmoney += " 💵"
    return nmoney

def moneyunparser(money):
    money = str(money).lower()
    nmoney = ""
    if money.isdigit():
        return int(money)
    else:
        if not money[:-1].isdigit():
            return
    if money.endswith("q"):
        nmoney = money[:-1] + "000000000000000"
    elif money.endswith("t"):
        nmoney = money[:-1] + "000000000000"
    elif money.endswith("b"):
        nmoney = money[:-1] + "000000000"
    elif money.endswith("m"):
        nmoney = money[:-1] + "000000"
    elif money.endswith("k"):
        nmoney = money[:-1] + "000"
    else:
        nmoney = money

    return int(nmoney)

class Gambling:

    def __init__(self, bot):
        self.conn = sqlite3.connect('data.db', isolation_level = None)
        self.bot = bot
        self.rrgroup = []
        self.bot.c = self.conn.cursor()

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

    @commands.group(pass_context=True, aliases=['rr'], invoke_without_command=True)
    async def russianroulette(self, ctx, betamount: str, bulletcount: int):
        """Russian Roulette, cause why not."""
        if ctx.message.author.id in self.rrgroup:
            await self.bot.say("Dont spam it.")
        else:
            if self.bot.c.execute("SELECT * FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone() is None:
                self.bot.c.execute("INSERT INTO users VALUES (?, 100, NULL, NULL)", [ctx.message.author.id])
                uid, money, times_died = self.bot.c.execute("SELECT user_id, money, times_died FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone()
            else:
                uid, money, times_died = self.bot.c.execute("SELECT user_id, money, times_died FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone()

            if betamount == "all":
                betamount = money
            elif betamount.isdigit():
                betamount = int(betamount)
            else:
                betamount = moneyunparser(betamount)
                if betamount is None:
                    return

            if times_died is None:
                times_died = 0
            self.rrgroup.append(ctx.message.author.id)
            if betamount > money:
                await self.bot.say("You cant bet more than you have. (You have {})".format(moneyparser(money)))
            elif betamount <= 0:
                await self.bot.say("You cant bet negative or no money.")

            elif bulletcount == 6:
                await self.bot.say("Do you want to kill yourself? You know a revolver only fits **6** bullets, right?")
            elif bulletcount > 6:
                await self.bot.say("A revolver only fits **6** bullets, not more.")
            elif bulletcount < 1:
                await self.bot.say("Why would you want a 100% win chance?")

            elif betamount > 20000 and bulletcount <= 2:
                await self.bot.say("Sorry but you can't bet over **20k** with less than 3 bullets.")                
            elif betamount > 5000 and bulletcount == 1:
                await self.bot.say("Sorry but you can't bet over **5k** with just one bullet.")
            else:
                m = await self.bot.say("{} shoots with {} bullet{} in the chamber... ({}/6 chance of winning)".format(ctx.message.author.mention, bulletcount, "s" if bulletcount > 1 else "", 6-bulletcount))
                roll = random.randint(0, 120)
                if roll >= 20 * bulletcount:
                    mon_mul = 6/(6-bulletcount)
                    newmoney = money - betamount + int(betamount*mon_mul)
                    await asyncio.sleep(2)
                    await self.bot.edit_message(m, m.content+"\n\nYou hear it click. You gained {} ({}*{}) `Total: {}`".format(int(betamount*mon_mul), moneyparser(betamount), mon_mul, moneyparser(newmoney)))
                    self.bot.c.execute("UPDATE users SET money = ? WHERE user_id = ?", [newmoney, uid])

                else:
                    newmoney = money - betamount
                    await asyncio.sleep(random.randint(1,3))
                    send = m.content+"\n\nThere's blood everywhere, but *somehow* you survived. You lost {} `Left: {}`".format(moneyparser(betamount), moneyparser(newmoney))
                    if newmoney == 0:
                        send += "\nYou seem to have lost everything. I'm not going to give you money, find someone to give you money."
                        self.bot.c.execute("UPDATE users SET money = ?, times_died = ? WHERE user_id = ?", [newmoney, times_died+1, uid])
                    else:
                        self.bot.c.execute("UPDATE users SET money = ? WHERE user_id = ?", [newmoney, uid])
                    await self.bot.edit_message(m, send)
            
            self.rrgroup.remove(ctx.message.author.id)


    @russianroulette.command(pass_context=True, name="money")
    async def _money(self, ctx):
        """Tells how much money you have"""
        if self.bot.c.execute("SELECT * FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone() is None:
            self.bot.c.execute("INSERT INTO users VALUES (?, 100, NULL, NULL)", [ctx.message.author.id])
            money = self.bot.c.execute("SELECT money FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone()
        else:
            money = self.bot.c.execute("SELECT money FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone()

        await self.bot.say("You have **{}**".format(moneyparser(money[0])))

    @russianroulette.command(pass_context=True, aliases=["lb"])
    async def leaderboard(self, ctx):
        """Shows the global leaderboard"""
        data = self.bot.c.execute("SELECT user_id, money, times_died FROM users ORDER BY money DESC LIMIT 10").fetchall()
        send = "__Current Russian Roulette leaderboard (R = Restarts)__\n"
        for uid, money, td in data:
            username = self.lookupid(uid).name
            send += "{} - **{}** (R: {})\n".format(username, moneyparser(money), td)
        await self.bot.say(send)

    @russianroulette.command(pass_context=True)
    @checks.is_owner()
    async def award(self, ctx, amount: str, *, name: str):
        """Gives away free money, only the bot owner can use this."""
        amount = moneyunparser(amount)
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
        if self.bot.c.execute("SELECT * FROM users WHERE user_id = ?", [personid]).fetchone() is None:
            self.bot.c.execute("INSERT INTO users VALUES (?, 100, NULL, NULL)", [personid])
            money = self.bot.c.execute("SELECT money FROM users WHERE user_id = ?", [personid]).fetchone()
        else:
            money = self.bot.c.execute("SELECT money FROM users WHERE user_id = ?", [personid]).fetchone()
        self.bot.c.execute("UPDATE users SET money = ? WHERE user_id = ?", [money[0] + amount, personid])
        await self.bot.say("Awarded {} **{}**".format(person.name, moneyparser(amount)))
    
    @russianroulette.command(pass_context=True)
    async def give(self, ctx, amount: str, *, name: str):
        """Gives money to someone else."""
        amount = moneyunparser(amount)
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

        if self.bot.c.execute("SELECT * FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone() is None:
            self.bot.c.execute("INSERT INTO users VALUES (?, 100, NULL, NULL)", [ctx.message.author.id])
            money = self.bot.c.execute("SELECT money FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone()
        else:
            money = self.bot.c.execute("SELECT money FROM users WHERE user_id = ?", [ctx.message.author.id]).fetchone()
        if amount > money[0]:
            await self.bot.say("You cant give more than you have. (You have {})".format(moneyparser(money[0])))
        elif amount <= 0:
            await self.bot.say("You cant give negative or no money.")
        else:
            self.bot.c.execute("UPDATE users SET money = ? WHERE user_id = ?", [money[0] - amount, ctx.message.author.id])

            if self.bot.c.execute("SELECT * FROM users WHERE user_id = ?", [personid]).fetchone() is None:
                self.bot.c.execute("INSERT INTO users VALUES (?, 100, NULL, NULL)", [personid])
                money = self.bot.c.execute("SELECT money FROM users WHERE user_id = ?", [personid]).fetchone()
            else:
                money = self.bot.c.execute("SELECT money FROM users WHERE user_id = ?", [personid]).fetchone()
            self.bot.c.execute("UPDATE users SET money = ? WHERE user_id = ?", [money[0] + amount, personid])

            await self.bot.say("{} gave {} **{}**".format(ctx.message.author.name, person.name, moneyparser(amount)))
        