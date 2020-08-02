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


async def try_system_message(guild, message):
    if guild.system_channel is not None:
        await guild.system_channel.send(message)


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
        self.update_brig_members.start()
        with open("bot_state.json", "r") as file:
            self.state_data = json.load(file)

    def cog_unload(self):
        self.update_brig_members.cancel()

    def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage("Why are you performing this command in DMs?")
        elif not ctx.author.permissions_in(ctx.channel).administrator:
            raise NotAdministrator("You are not an administrator!")
        return True

    @commands.command(brief="Put someone in the brig")
    async def brig(self, ctx, member: discord.Member, duration: typing.Optional[int]):
        await self.add_to_brig(ctx.guild, member, duration)

    @commands.command(brief="Remove someone from the brig")
    async def unbrig(self, ctx, member: discord.Member):
        await self.remove_from_brig(ctx.guild, member)

    @tasks.loop(seconds=1.0)
    async def update_brig_members(self):
        for guild, data in self.state_data.items():
            for member, sentence in data["brigMembers"].items():
                if sentence[1] != 0 and sentence[1] < time.time():
                    guild = self.bot.get_guild(int(guild))
                    member = guild.get_member(int(member))
                    await self.remove_from_brig(guild, member)

    async def remove_from_brig(self, guild: discord.Guild, member: discord.Member):
        with open("bot_state.json", "r+") as file:
            self.state_data = json.load(file)
            self.state_data[str(guild.id)]["brigMembers"].pop(str(member.id), None)
            file.seek(0)
            json.dump(self.state_data, file)
            file.truncate()
        role = discord.utils.get(guild.roles, name="THE BRIG")
        if role is None:
            message = "No role named \"THE BRIG\" exists! Please create one before using `unbrig`."
            await try_system_message(guild, message)
            return
        else:
            await member.remove_roles(role, reason="Removed from the brig")
            message = "Removed {0} from the brig.".format(member.mention)
            await try_system_message(guild, message)

    async def add_to_brig(self, guild: discord.Guild, member: discord.Member, duration: typing.Optional[int]):
        with open("bot_state.json", "r+") as file:
            self.state_data = json.load(file)
            guild_data = self.state_data.get(str(guild.id), {})
            brig_dict1 = {member.id: [time.time(), time.time() + (duration * 60)] if duration else [0, 0]}
            brig_dict2 = guild_data.get("brigMembers", {})
            guild_data["brigMembers"] = {**brig_dict1, **brig_dict2}
            self.state_data[str(guild.id)] = guild_data
            file.seek(0)
            json.dump(self.state_data, file)
            file.truncate()
        role = discord.utils.get(guild.roles, name="THE BRIG")
        if role is None:
            message = "No role named \"THE BRIG\" exists! Please create one before using this command."
            await try_system_message(guild, message)
            return
        else:
            # TODO: Add event logging to file
            # TODO: Add event logging to server
            await member.add_roles(role, reason="Put in the brig")
            message = "Added {0} to the brig for {1} minutes."\
                .format(member.mention, duration if duration is not None else "indefinite")
            await try_system_message(guild, message)

    # TODO: Add command for showing brig members


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
