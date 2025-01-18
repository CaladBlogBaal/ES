import typing
from datetime import timedelta, datetime

import aiohttp
from discord.ext import commands
from os import PathLike

UPLOAD_URL = "https://filebin.net"


class FileBin:

    def __init__(self, data: dict, api_key: str = ""):
        self.API_KEY = api_key  # for added functionality later if needed
        self.download_link = data.get("url")
        self.filename = data.get("filename")
        self.size = data.get("bytes_readable")
        self.expires = data.get("expired_at_relative")

    @staticmethod
    async def upload_to_filebin(ctx: commands.Context, name, file: bytes, user_id: str):

        js = await ctx.bot.post(UPLOAD_URL + f"/{user_id}/{name}", data=file)
        return js

    @classmethod
    async def upload_file(cls, ctx: commands.Context, name: str, file: typing.Union[str, bytes, PathLike[str]], user_id: str):

        if isinstance(file, bytes):
            js = await cls.upload_to_filebin(ctx, name, file, user_id)
        else:
            with open(file, 'rb') as f:
                js = await cls.upload_to_filebin(ctx, name, f.read(), user_id)

        file_bin = js.get("bin")
        js = js.get("file")

        if js:
            js["expired_at_relative"] = file_bin.get("expired_at_relative")
            js["url"] = UPLOAD_URL + f"/{user_id}"

        return cls(data=js)
