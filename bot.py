import config
import discord
from discord.ext import commands, tasks
import json
import time
import typing

bot = commands.Bot(command_prefix=";")


class NotAdministrator(commands.CheckFailure):
    pass


def is_in_dms(ctx):
    if ctx.guild is None:
        raise commands.NoPrivateMessage("Why are you performing this command in DMs?")
    return True


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    @commands.is_owner()
    async def quit(self, ctx):
        await ctx.send("Goodbye!")
        await bot.close()

    @commands.command()
    @commands.has_role('test')
    @commands.check(is_in_dms)
    async def poke(self, ctx):
        await ctx.author.send('boop')
        await ctx.message.delete()


class Administration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage("Why are you performing this command in DMs?")
        elif not ctx.author.permissions_in(ctx.channel).administrator:
            raise NotAdministrator("You are not an administrator!")
        return True

    @commands.command(brief="Put someone in the brig")
    async def brig(self, ctx, member: discord.Member, duration: typing.Optional[int]):
        with open("bot_state.json", "r+") as file:
            data = json.load(file)
            guild_data = data.get(ctx.guild.id, {})
            brig_dict1 = {member.id: [time.time(), time.time() + (duration * 60)] if duration else [0, 0]}
            brig_dict2 = guild_data.get("brigMembers", {})
            guild_data["brigMembers"] = {**brig_dict1, **brig_dict2}
            data[ctx.guild.id] = guild_data
            file.seek(0)
            json.dump(data, file)
            file.truncate()
        role = discord.utils.get(ctx.guild.roles, name="THE BRIG")
        if role is None:
            await ctx.send("No role named \"THE BRIG\" exists! Please create one before using this command.")
            return
        else:
            # TODO: Add event logging to file
            # TODO: Add event logging to server
            await member.add_roles(role, reason="Put in the brig")
            await ctx.send("Added {0} to the brig for {1} minutes."
                           .format(member.mention, duration if duration is not None else "indefinite"))

    @commands.command(brief="Remove someone from the brig")
    async def unbrig(self, ctx, member: discord.Member):
        with open("bot_state.json", "r+") as file:
            data = json.load(file)
            data[str(ctx.guild.id)]["brigMembers"].pop(str(member.id), None)
            file.seek(0)
            json.dump(data, file)
            file.truncate()
        role = discord.utils.get(ctx.guild.roles, name="THE BRIG")
        if role is None:
            await ctx.send("No role named \"THE BRIG\" exists! Please create one before using this command.")
            return
        else:
            await member.remove_roles(role, reason="Removed from the brig")
            await ctx.send("Removed {0} from the brig.".format(member.mention))

    # TODO: automatically remove people from the brig


allowed_errors = {NotAdministrator, commands.NoPrivateMessage, commands.MissingRequiredArgument,
                  commands.CommandNotFound, commands.MissingRole}


def is_allowed_error(error):
    for allowed_error in allowed_errors:
        if isinstance(error, allowed_error):
            return True
    return False


@bot.event
async def on_command_error(ctx, error):
    if is_allowed_error(error):
        await ctx.send(error)
    else:
        # TODO: Add error logging to file
        await ctx.send("Unknown issue. Contact fest1ve#4958 for help.")
        raise error


@bot.event
async def on_ready():
    print('------')
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    await bot.change_presence(activity=discord.Game(name='bowling :)'))


bot.add_cog(General(bot))
bot.add_cog(Administration(bot))
bot.run(config.TOKEN)
