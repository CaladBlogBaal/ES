import typing

from discord.ext import commands
from os import PathLike

UPLOAD_URL = "https://file.io/?expires=1d"


class FileIO:

    def __init__(self, data: dict, api_key: str = ""):
        self.API_KEY = api_key  # for added functionality later if needed
        self.download_link = data.get("link")
        self.filename = data.get("name")
        self.size = data.get("size")
        self.expires = data.get("expires")

    @staticmethod
    async def upload_to_fileio(ctx: commands.Context, name, file: bytes):
        data = {name: file}
        js = await ctx.bot.post(UPLOAD_URL, data=data)
        return js

    @classmethod
    async def upload_file(cls, ctx: commands.Context, name: str, file: typing.Union[str, bytes, PathLike[str]]):

        if isinstance(file, bytes):
            js = await cls.upload_to_fileio(ctx, name, file)
        else:
            with open(file, 'rb') as f:
                js = await cls.upload_to_fileio(ctx, name, f.read())

        return cls(data=js)
