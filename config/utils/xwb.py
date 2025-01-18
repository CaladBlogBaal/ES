import os
import glob
import fnmatch
import subprocess
import platform
import typing

from pydub import AudioSegment

from config.utils.pacfile import FileHeader


class XWBCreatorError(Exception):
    pass


class XWBCreator:
    FILE_FORMATS = ["mp3", "mp4", "ogg", "wav", "flac", "acc", "aiff", "amr", "mid"]
    # HZ
    OUTPUT_RATE = 48000

    def __init__(self, xwb_name: str,
                 pac_name: str,
                 audio_file="*",
                 audio_file_format="",
                 directory=os.getcwd() + "/"):
        """
        :param xwb_name: The xwb filename to be replaced
        :param pac_name: The pac filename
        :param audio_file: The filename of the audio file to be inserted into the newly created .xwb,
        if no filename is inserted will look for audio files in the parent then subdirectories
        :param audio_file_format: The file format of this audio file
        :param directory: The directory file creation operations will take place in.
        """
        self.xwb_name = xwb_name
        self.pac_name = pac_name
        self.directory = directory
        self.output: AudioSegment = None
        self.input: AudioSegment = None

        if not audio_file_format or audio_file == "*":

            audio_files = []

            for file_type in self.FILE_FORMATS:
                audio_files.extend(list(self.get_files(f"{audio_file}.{file_type}", directory)))

            file = audio_files[0][1]
            self.input = AudioSegment.from_file(self.directory + file, format=file.split(".")[1])

        else:

            self.input = AudioSegment.from_file(audio_file, format=audio_file_format)

    @staticmethod
    def walk_path(path) -> [typing.List[tuple[str, str, str]]]:
        # using glob to return paths that meet the pattern
        paths = glob.glob(path)
        if not paths:
            return []
        result = []
        for p in paths:
            # yields a tuple of dirpath, dirnames and filenames
            result.extend(os.walk(p))

        return result

    @staticmethod
    def get_files(pattern, path) -> [str, str]:
        for dirpath, _, filenames in XWBCreator.walk_path(path):
            for f in filenames:
                if fnmatch.fnmatch(f, pattern):
                    yield os.path.join(dirpath, f), f

    def export_input(self):
        audio_data = self.input.set_frame_rate(self.OUTPUT_RATE).set_sample_width(2).set_channels(2)
        self.output = audio_data

    def create_xwb_file(self, wav_file_path):
        # to be done later
        pass

    def adpcm_compress(self):
        self.export_input()

        self.output.export(self.directory + "temp.wav", format="wav", codec="adpcm_ms", parameters=
        ["-block_size", "512",
         "-ar", "48000",
         "-ac", "2",
        "-strict", "experimental",
        ])

    def create_xwb(self):
        self.adpcm_compress()

        # for later
        # self.create_xwb_file(self.cwd + "1.wav")

        # using XWBTool for now
        # get the tools directory path
        xwb_tools_path = os.path.join(os.getcwd(), "tools/XWBTool.exe")

        if platform.system() == "Windows":
            subprocess.run([xwb_tools_path, "-o",
                            self.xwb_name + ".xwb",
                            "temp.wav", "-f", "-nc"], check=True, stdout=subprocess.DEVNULL, cwd=self.directory)
        else:
            # use wine if it's linux
            subprocess.run(["wine", xwb_tools_path, "-o",
                            self.xwb_name + ".xwb",
                            "temp.wav", "-f", "-nc"], check=True, stdout=subprocess.DEVNULL, cwd=self.directory,
                           env={"DISPLAY": ":1", **os.environ})

    def replace_xwb(self, new_xwb_path=""):

        xwb_name = self.xwb_name + ".xwb"
        pac_name = self.pac_name + ".pac"

        if new_xwb_path == "":
            new_xwb_path = self.directory + xwb_name

        header = FileHeader(self.directory + pac_name)
        to_replace = None

        for file in header.files:

            if file.file_name.lower() == xwb_name.lower():
                to_replace = file
            # for vs themes
            elif file.file_name.lower() in xwb_name.lower() and ".xsb" not in file.file_name.lower():
                to_replace = file

        if to_replace is None:
            raise XWBCreatorError(f"Replacing the xwb ran into error the File {xwb_name} was not found in the .pac.")

        header.replace(to_replace, new_xwb_path)
