import mmap
import struct
import os

from discord.ext import commands


class File:
    def __init__(self, file_header):
        self._file_name = ""
        self._id = 0
        self._offset = 0
        self._file_size = 0
        self.file_header = file_header

    def __eq__(self, other):
        return self.id == other.id

    @property
    def file_name(self):
        return self._file_name

    @file_name.setter
    def file_name(self, value):
        self._file_name = value

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def offset(self):
        return self._offset

    @offset.setter
    def offset(self, value):
        self._offset = value

    @property
    def file_size(self):
        return self._file_size

    @file_size.setter
    def file_size(self, value):
        self._file_size = value


class FileHeader:
    def __init__(self, pac_path):
        self.file_path = pac_path
        self.magic_word = ""
        self.start_offset = 0
        self.file_size = 0
        self.count_of_files = 0
        self.name_length = 0
        self.files = []
        self.buffer_size = 1048576

        with open(pac_path, "rb") as binary_file:
            magic_word = binary_file.read(4).decode("ASCII")

            if magic_word != "FPAC":
                raise commands.BadArgument("File has an incorrect structure.")

            self.magic_word = magic_word
            self.start_offset = struct.unpack("<i", binary_file.read(4))[0]
            self.file_size = struct.unpack("<i", binary_file.read(4))[0]
            self.count_of_files = struct.unpack("<i", binary_file.read(4))[0]
            binary_file.seek(4, 1)
            self.name_length = struct.unpack("<i", binary_file.read(4))[0]
            binary_file.seek(8, 1)
            for _ in range(self.count_of_files):
                file_obj = File(self)
                file_obj.file_name = binary_file.read(self.name_length).decode("ASCII").replace("\0", "")
                file_obj.id = struct.unpack("<i", binary_file.read(4))[0]
                file_obj.offset = (struct.unpack("<i", binary_file.read(4))[0] + self.start_offset + 15) // 16 * 16
                file_obj.file_size = struct.unpack("<i", binary_file.read(4))[0]
                binary_file.seek(4 - (self.name_length % 4), 1)
                self.files.append(file_obj)

    def extract_all_files(self, dir_path):
        with open(self.file_path, "rb") as file_stream:
            for file_obj in self.files:
                with open(dir_path + "/" + file_obj.file_name, "wb") as file_output:
                    num = file_obj.file_size
                    buffer_size = self.buffer_size
                    file_stream.seek(file_obj.offset)
                    while num > 0:
                        data = file_stream.read(min(num, buffer_size))
                        file_output.write(data)
                        num -= len(data)



    def replace(self, file_obj, file_path):
        temp_file_path = "temp.tmp"
        file_size = os.path.getsize(file_path)

        with open(self.file_path, "rb") as file_stream, open(temp_file_path, "wb") as temp_file_stream:
            for file_item in self.files:
                if file_item.id == file_obj.id:
                    file_item.file_size = file_size

            self.recalculate_values()

            temp_file_stream.write(struct.pack("<4s", self.magic_word.encode("ASCII")))
            temp_file_stream.write(struct.pack("<i", self.start_offset))
            temp_file_stream.write(struct.pack("<i", self.file_size))
            temp_file_stream.write(struct.pack("<i", len(self.files)))
            temp_file_stream.write(struct.pack("<i", 1))
            temp_file_stream.write(struct.pack("<i", self.name_length))
            temp_file_stream.write(struct.pack("<q", 0))

            for file_item in self.files:
                temp_file_stream.write(file_item.file_name.encode("ASCII"))
                padding_size = max(0, self.name_length - len(file_item.file_name))
                temp_file_stream.write(b"\0" * padding_size)
                temp_file_stream.write(struct.pack("<i", file_item.id))
                temp_file_stream.write(struct.pack("<i", file_item.offset - self.start_offset))
                temp_file_stream.write(struct.pack("<i", file_item.file_size))
                temp_file_stream.write(struct.pack("<i", 0))
                # Align to 16-byte boundary
                while temp_file_stream.tell() % 16 != 0:
                    temp_file_stream.write(b"\0")

            for file_item in self.files:
                buffer_size = self.buffer_size

                if file_item.id == file_obj.id:
                    with open(file_path, "rb") as replacement_file:
                        bytes_written = 0
                        while True:
                            data = replacement_file.read(buffer_size)
                            if not data:
                                break
                            temp_file_stream.write(data)
                            bytes_written += len(data)

                        # Zero out remaining space if the replacement file is smaller
                        remaining_size = file_item.file_size - bytes_written
                        if remaining_size > 0:
                            temp_file_stream.write(b"\0" * remaining_size)
                else:
                    file_stream.seek(file_item.offset)
                    data = file_stream.read(file_item.file_size)
                    temp_file_stream.write(data)

                while temp_file_stream.tell() % 16 != 0:
                    temp_file_stream.write(b"\0")

        os.replace(temp_file_path, self.file_path)

    def recalculate_values(self):
        num = max(len(file_item.file_name) for file_item in self.files)
        self.name_length = ((num + 1 + 3) // 4) * 4

        # Calculate header entry size (aligned to 16 bytes)
        header_entry_size = self.name_length + 16
        header_entry_size = ((header_entry_size + 15) // 16) * 16

        header_size = 32 + len(self.files) * header_entry_size
        self.start_offset = ((header_size + 15) // 16) * 16

        self.files[0].offset = self.start_offset
        for i in range(1, len(self.files)):
            previous_file = self.files[i - 1]
            current_file = self.files[i]
            current_file.offset = previous_file.offset + previous_file.file_size
            current_file.offset = ((current_file.offset + 15) // 16) * 16

        last_file = self.files[-1]
        self.file_size = last_file.offset + last_file.file_size

        while self.file_size % 16 != 0:
            self.file_size += 1
