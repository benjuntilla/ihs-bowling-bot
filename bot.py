import config
import discord
from discord.ext import commands


prefix = "??"
bot = commands.Bot(command_prefix=prefix)


@bot.command(brief="Shutdown bot",
             hidden=True)
@commands.is_owner()
async def shutdown(ctx):
    await ctx.send("Shutting down")
    await bot.close()


@bot.command(brief='Test command',
             hidden=True)
@commands.has_role('test')
async def poke(ctx):
    await ctx.author.send('boop')
    await ctx.message.delete()


@bot.event
async def on_ready():
    print('------')
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    await bot.change_presence(activity=discord.Game(name='bowling :)'))


bot.run(config.TOKEN)
