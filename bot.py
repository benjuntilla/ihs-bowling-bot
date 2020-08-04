from config import *
from datetime import datetime
import discord
from discord.ext import commands, tasks
import json
import os
import psycopg2
from pytz import timezone
import time
import typing

bot = commands.Bot(command_prefix=";")


class NotAdministrator(commands.CheckFailure):
    pass


def is_in_dms(ctx):
    if ctx.guild is None:
        raise commands.NoPrivateMessage(phrases["no_dms"])
    return True


async def try_system_message(guild, message):
    if guild.system_channel is not None:
        await guild.system_channel.send(message)


def epoch_to_postgresql(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def datetime_to_phoenix(timestamp):
    return timestamp.replace(tzinfo=timezone("America/Phoenix")).strftime('%d/%m/%Y, %I:%M %p')


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    @commands.is_owner()
    async def quit(self, ctx):
        await ctx.send(phrases["shutdown"])
        await bot.close()

    @commands.command(brief="Show IHS Bowling Club social media platforms")
    async def social(self, ctx):
        embed = discord.Embed(title="Bowling Club Social Media", color=discord.Color.orange())
        for platform, link in social_media.items():
            embed.add_field(name=platform, value=link, inline=False)
        await ctx.send(embed=embed)


class Administration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        with self.conn, self.conn.cursor() as cur:
            sql = '''
            CREATE TABLE IF NOT EXISTS brigged_members (
                member_id bigint,
                guild_id bigint,
                brig_start timestamp NULL,
                brig_end timestamp NULL,
                PRIMARY KEY (member_id, guild_id)
            );
            '''
            cur.execute(sql)
        self.update_brig_members.start()

    def cog_unload(self):
        self.update_brig_members.cancel()
        self.conn.close()

    def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage(phrases["no_dms"])
        elif not ctx.author.permissions_in(ctx.channel).administrator:
            raise NotAdministrator(phrases["not_admin"])
        return True

    @commands.command(brief="Put someone in the brig")
    async def brig(self, ctx, member: discord.Member, duration: typing.Optional[int]):
        try:
            epoch_to_postgresql(time.time() + (duration * 60))
        except:
            await ctx.send(phrases["invalid_num_input"])
            return
        await self.add_to_brig(ctx.guild, member, duration)

    @commands.command(brief="Remove someone from the brig")
    async def unbrig(self, ctx, member: discord.Member):
        await self.remove_from_brig(ctx.guild, member)

    @commands.command(brief="List brig members and their sentences")
    async def listbrig(self, ctx):
        with self.conn, self.conn.cursor() as cur:
            sql = "SELECT * FROM brigged_members WHERE guild_id = %s;"
            cur.execute(sql, (ctx.guild.id,))
            brig_members = cur.fetchall()
        if len(brig_members) == 0:
            await ctx.send(phrases["brig_empty"])
            return
        embed = discord.Embed(title="The Brig", color=discord.Color.orange())
        for row in brig_members:
            member = ctx.guild.get_member(row[0])
            duration_formatted = "{0} — {1} ({2} minutes)".format(
                datetime_to_phoenix(row[2]), datetime_to_phoenix(row[3]),
                round((row[3] - row[2]).total_seconds() / 60)
            ) if row[2] is not None else "Indefinite"
            embed.add_field(name=member.name + "#" + member.discriminator, value=duration_formatted, inline=False)
        await ctx.send(embed=embed)

    @tasks.loop(seconds=1.0)
    async def update_brig_members(self):
        with self.conn, self.conn.cursor() as cur:
            cur.execute("SELECT * FROM brigged_members;")
            brig_members = cur.fetchall()
        for row in brig_members:
            if row[3] is not None and row[3].timestamp() < time.time():
                guild = self.bot.get_guild(row[1])
                member = guild.get_member(row[0])
                await self.remove_from_brig(guild, member)

    async def remove_from_brig(self, guild: discord.Guild, member: discord.Member):
        # Remove role
        role = discord.utils.get(guild.roles, name="THE BRIG")
        if role is None:
            message = phrases["no_role"].format("\"THE BRIG\"", "`unbrig`")
            await try_system_message(guild, message)
            return
        else:
            await member.remove_roles(role, reason="Removed from the brig")
            message = phrases["brig_remove"].format(member.mention)
            await try_system_message(guild, message)
        # Update db
        with self.conn, self.conn.cursor() as cur:
            sql = "DELETE FROM brigged_members WHERE member_id = %s AND guild_id = %s;"
            cur.execute(sql, (member.id, guild.id))

    async def add_to_brig(self, guild: discord.Guild, member: discord.Member, duration: typing.Optional[int]):
        # Add role
        role = discord.utils.get(guild.roles, name="THE BRIG")
        if role is None:
            message = phrases["no_role"].format("\"THE BRIG\"", "`brig`")
            await try_system_message(guild, message)
            return
        else:
            await member.add_roles(role, reason="Put in the brig")
            message = phrases["brig_add"]\
                .format(member.mention, "for " + str(duration) + " minutes" if duration else "indefinitely")
            await try_system_message(guild, message)
        # Update db
        with self.conn, self.conn.cursor() as cur:
            sql = '''
            INSERT INTO brigged_members VALUES (%s, %s, %s, %s)
            ON CONFLICT (member_id, guild_id) DO UPDATE SET 
                brig_start = excluded.brig_start,
                brig_end = excluded.brig_end;
            '''
            brig_start = epoch_to_postgresql(time.time())
            brig_end = epoch_to_postgresql(time.time() + (duration * 60))
            cur.execute(sql, (member.id, guild.id, brig_start, brig_end))


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
        await ctx.send(phrases["unknown_issue"])
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
bot.run(os.getenv("IHSBOT_TOKEN"))
