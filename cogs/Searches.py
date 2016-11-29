import discord
from discord.ext import commands
import urbandictionary as ud
import re
import random
import aiohttp
import google
import urllib.request as request
from io import BytesIO
from bs4 import BeautifulSoup as bs

google_api = []
api_count = 0

def setup(bot):
    bot.add_cog(Searches(bot))


class Searches:

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def define(self, *, to_define: str):
        """Using Urban Dictionary, define stuff."""
        to_define
        defs = ud.define(to_define)
        try:
            tosend = '__**' + defs[0].word + ':**__\n'
            tosend += defs[0].definition + ''
            if defs[0].example:
                tosend += '\n\n**Example:**\n' + defs[0].example
            if len(tosend) >= 4000:
                await self.bot.say("**Error:** Definition is too long to send, Sorry.")
            else:
                await self.bot.say(tosend)
        except IndexError:
            await self.bot.say('**Error:** Definition not found')

    @commands.command(name='google', pass_context=True)
    async def _google(self, ctx, *, googlesearch):
        """Googles stuff"""
        query = googlesearch
        await self.bot.type()
        url = google.search(query)
        await self.bot.say(
            '{}, you searched for: **{}**\nThis is the result: {}'.format(ctx.message.author.mention, query, next(url)))

    @commands.command(pass_context=True, aliases=['yt'])
    async def youtube(self, ctx, *, ytsearch: str):
        """Does a little YouTube search."""
        opener = request.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        search = ytsearch.split()
        search = "+".join(search)
        errorthing = ytsearch
        url = ('https://www.youtube.com/results?search_query={}'.format(search))
        ourUrl = opener.open(url).read()
        await self.bot.type()
        soup = bs(ourUrl, "html.parser")
        alexpls = re.findall('"(/watch\?v=.*?)"',
                             str(soup.find_all('a',
                                               attrs={'href': re.compile('^/watch\?v=.*')})))
        try:
            await self.bot.say('{}: https://www.youtube.com{}'.format(ctx.message.author.mention, alexpls[0]))
        except IndexError:
            await self.bot.say('Sorry I could not find any results containing the name `{}`'.format(errorthing))

    @commands.command()
    async def fanfiction(self, *, fanfucksearch: str):
        """Searches the shittiest and weirdest fanfics on fanfiction.net"""
        search = fanfucksearch.split()
        thing = "+".join(search)
        errorthing = fanfucksearch
        url = 'https://www.fanfiction.net/search.php?ready=1&keywords={}&categoryid=0&genreid1=0&genreid2=0&languageid=1&censorid=4&statusid=2&type=story&match=&sort=&ppage=1&characterid1=0&characterid2=0&characterid3=0&characterid4=0&words=1&formatid=0'.format(
            thing)
        opener = request.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        ourUrl = opener.open(url).read()
        soup = bs(ourUrl, "html.parser")
        alexpls = re.findall(
            '"(/s/.*?)"', str(soup.find_all('a', attrs={'href': re.compile('/s/*')})))
        try:
            x = len(alexpls)
            newurl = 'https://www.fanfiction.net' + \
                alexpls[random.randrange(x)]
            ourUrl = opener.open(newurl).read()
            soup = bs(ourUrl, "html.parser")
            alexpls2 = re.findall('<p>(.*?)</p>', str(soup.find_all('p')))
            text = ''
            for y in alexpls2:
                text += y + '\n'
            thingy = re.findall(
                '<a.*?>(.*?)</a>', str(soup.find_all('a', attrs={'href': re.compile('/u/*')})))
            text = re.sub('</?em>', '*', text)
            text = re.sub('</?strong>', '**', text)
            fmt = 'Fanfuck: **{}** by **{}**\n'.format(re.sub(', a .*? fanfic \| FanFiction', '', soup.title.text), thingy[0])
            fmt += text + '\n'
            fmt += 'Url: {}'.format(newurl)
            await self.bot.say(fmt)
        except ValueError:
            await self.bot.say("Sorry, but no fanfucks were found with the name: **{}**".format(errorthing))

    # @commands.command(pass_context=True, aliases=['im', 'photo', 'img'])
    # async def image(self, ctx, *, text:str):
    #     requrl = "https://api.cognitive.microsoft.com/bing/v5.0/images/search?q={}".format(text)
    #     res = await aiohttp.get(requrl, headers={"Ocp-Apim-Subscription-Key": "c84ce598f43143bbb35031a134d7ddd1"})
    #     strem = await res.json()
    #     print(strem)
    #     images = strem["value"]
    #     randimg = random.choice(images)
    #     async with aiohttp.get(randimg["contentUrl"]) as r:
    #         data = await r.read()
    #         img = BytesIO(data)
    #     await self.bot.upload(img)
