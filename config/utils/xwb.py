import os
import glob
import fnmatch
import struct
import subprocess
import platform
import typing

from pydub import AudioSegment

from config.utils.pacfile import FileHeader


class XWBCreatorError(Exception):
    pass

class XSBEditorError(Exception):
    pass


class XSBEditor:
    def __init__(self, xsb_path):
        self.path = xsb_path

    def calculate_checksum(self):
        checksum_key = [
            0, 4489, 8978, 12955, 17956, 22445, 25910, 29887, 35912, 40385,
            44890, 48851, 51820, 56293, 59774, 63735, 4225, 264, 13203, 8730,
            22181, 18220, 30135, 25662, 40137, 36160, 49115, 44626, 56045, 52068,
            63999, 59510, 8450, 12427, 528, 5017, 26406, 30383, 17460, 21949,
            44362, 48323, 36440, 40913, 60270, 64231, 51324, 55797, 12675, 8202,
            4753, 792, 30631, 26158, 21685, 17724, 48587, 44098, 40665, 36688,
            64495, 60006, 55549, 51572, 16900, 21389, 24854, 28831, 1056, 5545,
            10034, 14011, 52812, 57285, 60766, 64727, 34920, 39393, 43898, 47859,
            21125, 17164, 29079, 24606, 5281, 1320, 14259, 9786, 57037, 53060,
            64991, 60502, 39145, 35168, 48123, 43634, 25350, 29327, 16404, 20893,
            9506, 13483, 1584, 6073, 61262, 65223, 52316, 56789, 43370, 47331,
            35448, 39921, 29575, 25102, 20629, 16668, 13731, 9258, 5809, 1848,
            65487, 60998, 56541, 52564, 47595, 43106, 39673, 35696, 33800, 38273,
            42778, 46739, 49708, 54181, 57662, 61623, 2112, 6601, 11090, 15067,
            20068, 24557, 28022, 31999, 38025, 34048, 47003, 42514, 53933, 49956,
            61887, 57398, 6337, 2376, 15315, 10842, 24293, 20332, 32247, 27774,
            42250, 46211, 34328, 38801, 58158, 62119, 49212, 53685, 10562, 14539,
            2640, 7129, 28518, 32495, 19572, 24061, 46475, 41986, 38553, 34576,
            62383, 57894, 53437, 49460, 14787, 10314, 6865, 2904, 32743, 28270,
            23797, 19836, 50700, 55173, 58654, 62615, 32808, 37281, 41786, 45747,
            19012, 23501, 26966, 30943, 3168, 7657, 12146, 16123, 54925, 50948,
            62879, 58390, 37033, 33056, 46011, 41522, 23237, 19276, 31191, 26718,
            7393, 3432, 16371, 11898, 59150, 63111, 50204, 54677, 41258, 45219,
            33336, 37809, 27462, 31439, 18516, 23005, 11618, 15595, 3696, 8185,
            63375, 58886, 54429, 50452, 45483, 40994, 37561, 33584, 31687, 27214,
            22741, 18780, 15843, 11370, 7921, 3960
        ]

        if not os.path.exists(self.path) or not self.path.lower().endswith(".xsb"):
            raise XSBEditorError("File doesn't exist or is the wrong extension.")

        num = 65535

        with open(self.path, "rb+") as file:
            file.seek(18, os.SEEK_SET)

            data = file.read()
            for byte in data:
                num = checksum_key[(byte ^ num) & 0xFF] ^ (num >> 8)

            num = ~num & 0xFFFF
            file.seek(8, os.SEEK_SET)
            file.write(struct.pack("<H", num))


    def __write_byte_at_offset(self, new_byte: int, offset: int):
        with open(self.path, "rb+") as f:
            f.seek(offset)
            f.write(struct.pack("<B", new_byte))
            f.flush()


    def write_sound(self, new_byte: int):
        self.__write_byte_at_offset(new_byte, 0xCD)

    def write_track(self, new_byte: int):
        self.__write_byte_at_offset(new_byte, 0xDB)


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
