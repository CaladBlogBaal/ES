import re

import discord
from discord import Attachment
from discord.ext import commands


class PacFileConverter:

    async def convert(self, ctx, argument: Attachment,
                      error_msg="An invalid file was passed.") -> Attachment:

        if not isinstance(argument, Attachment):
            raise commands.BadArgument(error_msg)

        magic_word = (await argument.read())[:4].decode("ASCII")

        if magic_word != "FPAC":
            raise commands.BadArgument(".pac File has an incorrect structure.")

        return argument


class AudioConverter:

    @staticmethod
    def remove_playlist_if_exists(argument: str) -> str:

        if "youtu" in argument and "list=" in argument or "m.youtu" in argument and "list=":
            argument = argument.split("list=")[0]

        return argument

    def convert(self, ctx, argument: [str, discord.Attachment],
                error_msg="An invalid url/file was passed for audio.") -> [str, discord.Attachment]:

        if isinstance(argument, str):
            if re.search(r"http[s]?:\/\/(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", argument):
                return self.remove_playlist_if_exists(argument)

            raise commands.BadArgument(error_msg)

        if "audio" not in argument.content_type.lower():
            raise commands.BadArgument(error_msg)

        return argument
