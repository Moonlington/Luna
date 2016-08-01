import discord
from discord.ext import commands

def setup(bot):
    bot.add_cog(Members(bot))

class Members:
    def __init__(self, bot):
        self.bot = bot
        