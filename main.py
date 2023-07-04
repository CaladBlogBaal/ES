import os
import threading
import queue
import shutil

import re

import asyncio
import aiohttp
import sys

import platform

import psutil

import humanize as h

import discord

from discord.ext import commands

from config.cogs import __cogs__
from config.utils import requests
from config import config


class ES(commands.Bot):
    def __init__(self, *args, **kwargs):
        # when you want to delete a file, do:
        # dead_files.put(file_path)
        self.dead_files = queue.Queue()
        self.END_OF_DATA = object()  # a unique sentinel value
        self.embed_colour = 0x00dcff
        self.deleter = threading.Thread(target=self.background_deleter)
        super().__init__(*args, **kwargs)

    async def __ainit__(self, *args, **kwargs):
        self.request = requests.Request(self, self.session)

    def handle_remove_error(self, func, path, exc_info):
        """
        Error handling function for shutil.rmtree.
        """
        if func == os.rmdir:
            os.remove(path)

    def background_deleter(self):

        while True:
            path = self.dead_files.get()
            if path is self.END_OF_DATA:
                return
            try:
                shutil.rmtree(path, onerror=self.handle_remove_error)
            except OSError:
                pass

    async def setup_hook(self):
        await self.loop.create_task(self.__ainit__())

    async def fetch(self, url, **kwargs):
        return await self.request.fetch(url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.request.post(url, **kwargs)

    async def on_message(self, message):
        # dunno why im doing this here
        if self.user.mentioned_in(message) and re.match(r"^<@(!?)([0-9]*)>(?!.)", message.content):
            prefixes = ", ".join(config.__prefixes__)
            await message.channel.send(f"UwU my prefixes are {prefixes}")

        await self.process_commands(message)

    async def close(self):
        await self.session.close()
        # shutting down thread cleanly
        self.dead_files.put(self.END_OF_DATA)
        self.deleter.join()
        print("closed thread and session.")
        await super().close()


# since I have a say command and in the future may implement replies for long to process commands
allowed_mentions = discord.AllowedMentions(everyone=False, roles=False, replied_user=False)
intents = discord.Intents.default()  # All but the privileged ones
# need this for discord.User to work as intended
intents.members = True
intents.message_content = True


async def get_prefix(bot, message):
    return commands.when_mentioned_or(*config.__prefixes__)(bot, message)


bot = ES(command_prefix=get_prefix,
         case_insensitive=True,
         intents=intents,
         allowed_mentions=allowed_mentions)


@bot.event
async def on_ready():
    print(f"Successfully logged in and booted...!")
    print(f"\nLogged in as: {bot.user.name} - {bot.user.id}\nDiscord.py version: {discord.__version__}\n")


@bot.command()
async def say(ctx, *, mesasage):
    """
    Echo a message
    -------------------------------------------------------------
    tataru say message
    """
    await ctx.send(mesasage)


@bot.command()
async def ping(ctx):
    """
    Returns the bots web socket latency
    -------------------------------------------------------------
    tataru ping
    """

    await ctx.send(f":information_source: | :ping_pong: **{ctx.bot.latency * 1000:.0f}**ms")


@bot.command()
async def prefix(ctx):
    """
    returns the bot current prefixes
    -------------------------------------------------------------
    tataru prefix
    """
    prefixes = ", ".join(config.__prefixes__)
    await ctx.send(f"The prefixes for this bot is {prefixes}")


@bot.command()
async def invite(ctx):
    """
    returns the bot invite url
    -------------------------------------------------------------
    tataru invite
    """
    await ctx.send(discord.utils.oauth_url(ctx.me.id, permissions=discord.Permissions(100352)))


@bot.command()
async def about(ctx):
    """
    provides information about the bot
    -------------------------------------------------------------
    es about
    """

    invite_url = f"[invite url]({discord.utils.oauth_url(ctx.me.id, permissions=discord.Permissions(100352))})"
    proc = psutil.Process()
    mem = proc.memory_full_info()
    command_count = len({command for command in ctx.bot.walk_commands() if "jishaku" not in
                         command.name and "jishaku" not in command.qualified_name})
    py_version = ".".join(str(n) for n in sys.version_info[:3])
    guild_count = f"```{(len(bot.guilds))}```"
    embed = discord.Embed(color=bot.embed_colour, title="", description=f"")
    embed.add_field(name="Basic:", value=f"**OS**: {platform.platform()}\n**Hostname: **OVH\n**Python Version: **"
                                         f"{py_version}\n**Links**: {invite_url}", inline=False)
    embed.add_field(name="Dev:", value="```CaladWoDestroyer#9313```")
    embed.add_field(name="Library:", value=f"```Discord.py {discord.__version__}```")
    embed.add_field(name="Commands:", value=f"```{command_count}```")
    embed.add_field(name="RAM:", value=f"```Using {h.naturalsize(mem.rss)}```")
    embed.add_field(name="VRAM:", value=f"```Using {h.naturalsize(mem.vms)}```")
    embed.add_field(name="Web socket ping", value=f"```{round(ctx.bot.latency * 1000, 2)}```")
    embed.add_field(name="Guilds:", value=guild_count)
    await ctx.send(embed=embed)


if __name__ == "__main__":

    async def main():
        async with aiohttp.ClientSession() as session:

            bot.session = session
            bot.deleter.start()  # starting the deleting thread
            # print(config.__mega_email__)
            # subprocess.run(["mega-login", config.__mega_email__, config.__mega_password__], shell=True)
            async with bot:

                for c in __cogs__:

                    try:

                        await bot.load_extension(c)

                    except Exception as e:
                        print(f"{c} could not be loaded.")
                        raise e

                await bot.start(config.__bot_token__, reconnect=True)


    asyncio.run(main())
