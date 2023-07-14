import os
import asyncio
import typing

from pathlib import Path
from io import BytesIO
from datetime import datetime

import discord
import humanize as h
import filetype

from config.utils.xwb import XWBCreator, XWBCreatorError
from config.utils.ytdl import YTDL, YTDLError
from config.utils.fileio import FileIO
from config.utils.convertors import AudioConverter
from config.utils.pacfile import FileHeader


from discord.ext import commands

from main import ES


class BlazBlue(commands.Cog):
    """
    Blazblue related commands
    """

    def __init__(self, bot):
        self.bot = bot
        self.creator = XWBCreator

    async def upload_to_fileio(self, ctx: commands.Context, file: discord.File, file_directory: str) -> None:

        file = await FileIO.upload_file(ctx, file.filename, file_directory)
        expiration_date = datetime.fromisoformat(file.expires[:-1])

        m = f"Here's your modified .pac file (uploaded to file.io exceeded upload size limits):\n"
        m += f"Filename: `{file.filename}`\n"
        m += f"Size: `{h.naturalsize(file.size)}`\n"
        m += f"Expires: `{h.naturaldate(expiration_date)}`\n"
        m += f"Download link: `{file.download_link}` ( copy and open it in browser one time download )"

        await ctx.send(m)

    async def generate_discord_file(self, ctx: commands.Context, audio: typing.Union[discord.Attachment, str],
                                    pac_file: discord.Attachment, temp_dir: str) -> [tuple[discord.File, str],
                                                                                     discord.Message]:
        # catching exceptions so the rest of the coroutines can run without issue if one fails
        try:
            aud_format, aud = await self.get_audio_data(ctx.bot, audio)

            xwb_name = pac_file.filename.replace(".pac", "")
            pac_name = YTDL.generate_unique_filename()
            pac_path = Path(os.path.join(temp_dir, pac_name + ".pac"))

            await pac_file.save(pac_path)

            xw = self.creator(xwb_name,
                              pac_name,
                              audio_file=aud,
                              audio_file_format=aud_format,
                              directory=temp_dir)
            xw.create_xwb()
            xw.replace_xwb()

            file = discord.File(pac_path)
            file.filename = xwb_name + ".pac"

        except YTDLError as e:
            return await ctx.send(f"{e}")

        except XWBCreatorError as e:
            return await ctx.send(f"{e}")

        return file, pac_name

    async def check_if_pac(self, argument: discord.Attachment) -> bool:

        if not isinstance(argument, discord.Attachment):
            return False

        magic_word = (await argument.read())[:4].decode("ASCII")

        # has file extension
        if argument.content_type:
            if "application/x-ns-proxy-autoconfig" not in argument.content_type:
                return False

            if magic_word != "FPAC":
                raise commands.BadArgument(f"The .pac file {argument.filename} has an incorrect structure.")

        else:
            # no file extension so only checking the magic word
            return magic_word == "FPAC"

        return True

    @staticmethod
    async def get_audio_data(bot: ES, audio: typing.Union[discord.Attachment, str]) -> [str, BytesIO]:

        aud = BytesIO()

        if isinstance(audio, str):
            audio = await YTDL.create_mp3(bot, audio)
            aud = audio.audio

        else:
            await audio.save(aud)
            aud.seek(0)

        _, extension = os.path.splitext(audio.filename)

        extension = extension.replace(".", "")

        return extension, aud

    async def categorize_files(self, ctx: commands.Context,
                               files: list[typing.Union[str, discord.Attachment]]) -> [typing.List, typing.List]:
        pac_files = []
        audio_files = []

        for file in files:
            if await self.check_if_pac(file):
                pac_files.append(file)
            else:
                audio_files.append(await AudioConverter().convert(ctx, file))

        return pac_files, audio_files

    @commands.command(invoke_without_command=True, aliases=["mc"])
    async def music(self, ctx: commands.Context, files: commands.Greedy[discord.Attachment], *,
                    urls: typing.Optional[str]):
        """Replaces music inside a .pac file(s) with a supplied audio file(s) or url(s)
           .pac file(s) are edited by order of their upload and are paired to one audio file/url
           if there are multiple .pac files and one audio file/url all .pac files will get edited
           with said audio and vice versa.
           -------------------------------------------------------------
           es music pac_file url or audio_file
           es music pac_file pac_file pac_file url audio_file url
           es music pac_file pac_file audio_file
           """

        if len(files) == 0:
            return await ctx.send(":no_entry: | no file(s) were supplied.")

        if urls:
            files.extend(urls.split())

        pac_files, audio_files = await self.categorize_files(ctx, files)

        if len(pac_files) == 0:
            return await ctx.send(":no_entry: | no .pac file(s) was supplied.")

        if len(audio_files) == 0:
            return await ctx.send(":no_entry: | no audio file(s) or url(s) was supplied.")

        check = len(pac_files) - len(audio_files)

        if check > 0:
            # duplicate the last item in the list until it's the same size as the pac file list
            audio_files = audio_files + [audio_files[-1]] * check

        async with ctx.typing():
            temp_dir = os.path.join(os.getcwd(), f"temp/{ctx.author.id}/")
            generate_files_tasks = []
            upload_files_tasks = []

            ctx.bot.create_directory(temp_dir)

            for i, pac_file in enumerate(pac_files):
                audio = audio_files[i]
                task = asyncio.create_task(self.generate_discord_file(ctx, audio, pac_file, temp_dir))
                generate_files_tasks.append(task)

            await asyncio.gather(*generate_files_tasks)

            files = [f.result() for f in generate_files_tasks if isinstance(f.result(), tuple)]

            for file, name in files:
                try:
                    await ctx.send("Here's your modified .pac file", file=file)
                except discord.errors.HTTPException:
                    # file was too big to be sent
                    # upload it to file.io
                    fn = file.filename
                    await ctx.send(f"{fn} is too big to be uploaded to discord and will be shortly uploaded to file.io")
                    task = asyncio.create_task(self.upload_to_fileio(ctx, file, os.path.join(temp_dir, f"{name}.pac")))
                    upload_files_tasks.append(task)

            await asyncio.gather(*upload_files_tasks)

    @commands.command(aliases=["ex"])
    async def extract(self, ctx, pac_file: discord.Attachment):
        """
        extract's the contents of a uploaded .pac file
        -------------------------------------------------------------
        extract pac_file
        """

        if not await self.check_if_pac(pac_file):
            await ctx.send("> A .pac file wasn't supplied.")

        async with ctx.typing():
            temp_dir = os.path.join(os.getcwd(), f"temp/{ctx.author.id}/extract")

            ctx.bot.create_directory(temp_dir)

            pac_name = pac_file.filename.replace(".pac", "")
            pac_path = Path(os.path.join(temp_dir, pac_name + ".pac"))
            await pac_file.save(pac_path)

            header = FileHeader(pac_path)
            header.extract_all_files(temp_dir)
            # [!seq] -> matches any character not in seq
            files = XWBCreator.get_files(f"*.[!pac]*", temp_dir)

            for file in files:
                await ctx.send(file=discord.File(file[0]))

    @music.after_invoke
    @extract.after_invoke
    async def after_music(self, ctx: commands.Context[commands.Bot]):
        """This triggers after the command ran."""
        path = os.path.join(os.getcwd(), f"temp/{ctx.author.id}")
        self.bot.dead_files.put(path)

    @music.error
    async def on_music_error(self, ctx: commands.Context[commands.Bot], _):
        """This triggers after the command ran into an unexpected error."""
        path = os.path.join(os.getcwd(), f"temp/{ctx.author.id}")
        self.bot.dead_files.put(path)

    @extract.error
    async def on_extract_error(self, ctx: commands.Context[commands.Bot], _):
        """This triggers after the command ran into an unexpected error."""
        path = os.path.join(os.getcwd(), f"temp/{ctx.author.id}/extract")
        self.bot.dead_files.put(path)

    @extract.after_invoke
    async def after_extract(self, ctx: commands.Context[commands.Bot]):
        """This triggers after the command ran into an unexpected error."""
        path = os.path.join(os.getcwd(), f"temp/{ctx.author.id}/extract")
        self.bot.dead_files.put(path)


async def setup(bot):
    await bot.add_cog(BlazBlue(bot))
