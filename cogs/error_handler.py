import traceback
import sys

import discord
from discord.ext import commands

from config.utils.requests import RequestFailed
from config.utils.ytdl import YTDLError


class CommandErrorHandler(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        owner_id = (await self.bot.application_info()).owner.id
        owner = ctx.bot.get_user(owner_id)

        if isinstance(error, commands.errors.CommandInvokeError):

            error = error.original

        ignored = commands.CommandNotFound

        accounted_for = (commands.errors.BotMissingPermissions, commands.errors.MissingRequiredAttachment,

                         commands.errors.MissingPermissions, commands.errors.CommandOnCooldown,

                         commands.errors.NoPrivateMessage, commands.errors.NotOwner,
                         commands.errors.CommandNotFound, commands.errors.TooManyArguments,

                         commands.errors.DisabledCommand, commands.errors.BadArgument, commands.errors.BadUnionArgument,

                         commands.errors.UnexpectedQuoteError, YTDLError,

                         RequestFailed)

        error = getattr(error, 'original', error)

        if isinstance(error, discord.errors.ClientException):
            return

        if isinstance(error, ignored):

            return

        if isinstance(error, accounted_for):

            return await ctx.send(f"> :no_entry: | {error}")

        accounted_for += (commands.CheckFailure,)

        error_messsage = traceback.format_exception(type(error), error, error.__traceback__)
        error_messsage = "".join(c for c in error_messsage)

        try:

            if not isinstance(error, accounted_for):

                await ctx.send(f"The command `{ctx.command.name}` has ran into an unexpected error, "
                               f"the bot owner has been notified.", delete_after=8)

                await owner.send("```Python\n" + error_messsage + "```")

        except discord.errors.HTTPException:

            pass

        else:

            print("Ignoring exception in command {}:".format(ctx.command), file=sys.stderr)

            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


async def setup(bot):

    await bot.add_cog(CommandErrorHandler(bot))
