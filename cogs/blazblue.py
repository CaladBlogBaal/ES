import os
import asyncio
import typing

from pathlib import Path
from io import BytesIO

import discord

from config.utils.xwb import XWBCreator, XWBCreatorError
from config.utils.ytdl import YTDL, YTDLError
from config.utils.fileio import FileIO
from config.utils.convertors import AudioConverter


from discord.ext import commands

from main import ES


class BlazBlue(commands.Cog):
    """
    Blazblue related commands
    """

    def __init__(self, bot):
        self.bot = bot
        self.creator = XWBCreator

    async def upload_to_fileio(self, ctx: commands.Context, file: discord.File, user_dir: str) -> None:

        file = await FileIO.upload_file(ctx, file.filename, user_dir + file.filename)

        m = f"Here's your modified .pac file (uploaded to file.io exceeded upload size limits):\n"
        m += f"Filename: `{file.filename}`\n"
        m += f"Size: `{file.size}`\n"
        m += f"Expires In: `{file.expires}`\n"
        m += f"Download link: `{file.download_link}` ( copy and open it in browser one time download )"

        await ctx.send(m)

    async def generate_discord_file(self, ctx: commands.Context, audio: typing.Union[discord.Attachment, str],
                                    pac_file: discord.Attachment, user_dir: str) -> [discord.File, discord.Message]:
        # catching exceptions so the rest of the coroutines can run without issue if one fails
        try:
            aud_format, aud = await self.get_audio_data(ctx.bot, audio)

            xwb_name = pac_file.filename.replace(".pac", "")
            pac_name = YTDL.generate_unique_filename()
            pac_path = Path(os.path.join(user_dir, pac_name + ".pac"))

            await pac_file.save(pac_path)

            xw = self.creator(xwb_name,
                              pac_name,
                              audio_file=aud,
                              audio_file_format=aud_format,
                              directory=user_dir)
            xw.create_xwb()
            xw.replace_xwb()

            file = discord.File(pac_path)
            file.filename = xwb_name + ".pac"

        except YTDLError as e:
            return await ctx.send(f"{e}")

        except XWBCreatorError as e:
            return await ctx.send(f"{e}")

        return file

    async def check_if_pac(self, argument: discord.Attachment) -> bool:

        if not isinstance(argument, discord.Attachment):
            return False

        if "application/x-ns-proxy-autoconfig" not in argument.content_type:
            return False

        magic_word = (await argument.read())[:4].decode("ASCII")

        if magic_word != "FPAC":
            raise commands.BadArgument(".pac File has an incorrect structure.")

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

        return audio.filename.split(".")[1], aud

    async def categorize_files(self, ctx: commands.Context,
                               files: list[typing.Union[str, discord.Attachment]]) -> [typing.List, typing.List]:
        pac_files = []
        audio_files = []

        for file in files:
            if await self.check_if_pac(file):
                pac_files.append(file)
            else:
                audio_files.append(AudioConverter().convert(ctx, file))

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
            user_dir = os.path.join(os.getcwd(), f"temp/{ctx.author.id}/")
            generate_files_tasks = []
            upload_files_tasks = []

            if not os.path.exists(user_dir):
                os.makedirs(user_dir)

            for i, pac_file in enumerate(pac_files):
                audio = audio_files[i]
                task = asyncio.create_task(self.generate_discord_file(ctx, audio, pac_file, user_dir))
                generate_files_tasks.append(task)

            await asyncio.gather(*generate_files_tasks)

            files = [f.result() for f in generate_files_tasks if isinstance(f.result(), discord.File)]

            for file in files:
                try:
                    await ctx.send("Here's your modified .pac file", file=file)
                except discord.errors.HTTPException:
                    # file was too big to be sent
                    # upload it to file.io
                    fn = file.filename
                    await ctx.send(f"{fn} is too big to be uploaded to discord and will be shortly uploaded to file.io")
                    task = asyncio.create_task(self.upload_to_fileio(ctx, file, user_dir))
                    upload_files_tasks.append(task)

            await asyncio.gather(*upload_files_tasks)

    @music.after_invoke
    async def test_after(self, ctx: commands.Context[commands.Bot]):
        """This triggers after the command ran."""
        self.bot.dead_files.put(f"./temp/{ctx.author.id}/")

    @music.error
    async def on_error(self, ctx, error):
        """This triggers after the command ran into an unexpected error."""
        self.bot.dead_files.put(f"./temp/{ctx.author.id}/")


async def setup(bot):
    await bot.add_cog(BlazBlue(bot))
