import asyncio
import concurrent.futures
import functools
import io
import uuid

from copy import deepcopy

import yt_dlp as youtube_dl


youtube_dl.utils.bug_reports_message = lambda: ''


class YTDLError(Exception):
    pass


class YTDL:
    YTDL_OPTIONS = {
        "format": "bestaudio/best",
        "no_playlist": "true",
        "outtmpl": "placeholder",  # will be a unique file name for future-proofing naming conflicts since I"m lazy
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": "true",
    }

    FFMPEG_OPTIONS = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn",
    }

    def __init__(self, *, data: dict):
        self.data = data
        self.filename = data.get("title", "")
        self.filename += ".mp3"
        self.audio = data.get("audio")

    @classmethod
    def generate_unique_filename(cls):
        filename = str(uuid.uuid4().hex)
        return filename

    @classmethod
    async def create_mp3(cls, bot, search: str, *, loop: asyncio.BaseEventLoop = None):
        buffer = io.BytesIO()

        loop = loop or asyncio.get_event_loop()

        unique_filename = cls.generate_unique_filename()
        options = deepcopy(cls.YTDL_OPTIONS)

        options["outtmpl"] = unique_filename  # Update the unique filename in YTDL_OPTIONS

        with youtube_dl.YoutubeDL(options) as ydl:
            partial = functools.partial(ydl.download, search)

            with concurrent.futures.ThreadPoolExecutor() as pool:
                try:
                    data = await loop.run_in_executor(pool, partial)
                except youtube_dl.utils.DownloadError as e:
                    raise YTDLError("Audio unavailable. this video is not available for download. `{}`".format(search))
                except youtube_dl.utils.ExtractorError as e:
                    raise YTDLError("Couldn't extract audio data from the following link. `{}`".format(search))

            if data is None:
                raise YTDLError("Couldn't find anything that matches `{}`".format(search))

            filename = f"{unique_filename}.mp3"

            with open(filename, "rb") as f:
                buffer.write(f.read())
            buffer.seek(0)
            # schedule file for deletion
            bot.dead_files.put(filename)

        info = {"audio": buffer,
                "title": filename}

        return cls(data=info)
