import numpy as np
import mmap
import os
import struct
from typing import Any, Tuple
import matplotlib.pyplot as plt
from astropy.io import fits
import argparse

def get_args()->Tuple[str, str, bool]:
    """
    Parse command-line arguments for converter
    :return str: The source filename and destination folder
    """
    parser = argparse.ArgumentParser(
        description="Takes an SPS file and converts it into a FITS file"
    )
    parser.add_argument(
        "-s", "--source",
        required=True,
        type=str,
        help="Path to input SPS file"
    )
    parser.add_argument(
        "-d", "--destination",
        required=False,
        type=str,
        default=".",  # default to current directory
        help="Path to output directory (default: current directory)"
    )
    parser.add_argument(
        "-s", "--show",
        action="store_true",
        help="If set true will output the spectrogram plots"
    )
    args = parser.parse_args()

    # Check source file
    if not os.path.exists(args.source):
        raise RuntimeError(f"ERROR: SPS file not found: {args.source}")
    if not os.path.isfile(args.source):
        raise RuntimeError(f"ERROR: Source path is not a file: {args.source}")

    # Check destination folder
    if not os.path.exists(args.destination):
        try:
            os.makedirs(args.destination)
        except Exception as e:
            raise RuntimeError(f"ERROR: Cannot create destination folder '{args.destination}': {e}")
    elif not os.path.isdir(args.destination):
        raise RuntimeError(f"ERROR: Destination path is not a directory: {args.destination}")

    return args.source, args.destination, args.show

def extract_bytes(mapped_file: mmap.mmap, n_bytes: int, start_offset: int=0)->bytes:
    """
    Given a byte mapped file, will extract and return the n_bytes starting
    from the offset as a string.
    :param mapped_file: The memory mapped file of the sps file
    :param n_bytes: The number of bytes to extract
    :param start_offset: The offset to start extracting from
    :return: The extracted bytes
    """
    # Check that the end point doesn't go out of bounds
    if start_offset + n_bytes >= mapped_file.size():
        print(f"Out-of-bounds by {start_offset+n_bytes - mapped_file.size()}")
        return bytes(0) #consider exiting program

    # Extract and interpret as ascii
    return mapped_file[start_offset: start_offset + n_bytes]

def interpret_bytes(byte_data: bytes, data_type: str)->Any:
    """
    Given bytes and the data type, interpret the bytes as the given data type.
    :param byte_data: bytes to interpret
    :param data_type: data type to interpret
    :return data_type: The bytes in the interpreted data type
    """
    if data_type == "String":
        return byte_data.decode('ascii')
    # '>' is big endian and '<' is little endian
    elif data_type == "Real64":
        return struct.unpack("<d", byte_data)[0] #d for double
    elif data_type == "Int16":
        return struct.unpack("<h", byte_data)[0] #h for half signed
    elif data_type == "Int32":
        return struct.unpack("<i", byte_data)[0] #i for int signed
    elif data_type == "UInt16":
        return struct.unpack(">H", byte_data)[0] #H for half unsigned
    else: #should never be reached
        return byte_data

def extract_sps_header(mapped_file: mmap.mmap)->dict:
    """
    Given the sps file will extract and store the data of the header section.
    Will also have the number of bytes after position 152 where the data begins
    :param mapped_file: Memory mapped sps file
    :return: a dictionary with the header values of the sps file
    """
    fields = [
        # Position  Name        Type       Bytes
        (1,        "Version",   "String",  10),
        (11,       "Start",     "Real64",   8),
        (19,       "End",       "Real64",   8),
        (27,       "Latitude",  "Real64",   8),
        (35,       "Longitude", "Real64",   8),
        (43,       "ChartMax",  "Real64",   8),
        (51,       "ChartMin",  "Real64",   8),
        (59,       "TimeZone",  "Int16",    2),
        (61,       "Source",    "String",  10),
        (71,       "Author",    "String",  20),
        (91,       "Name",      "String",  20),
        (111,      "Location",  "String",  40),
        (151,      "Channels",  "Int16",    2),
        (153,      "NoteLength","Int32",    4),
    ]

    sps_header = {}

    for pos, name, data_type, size in fields:
        #1. Extract the raw value
        value = extract_bytes(mapped_file, size, pos-1) #Is 1-index in the specs

        #2. Based on the type reinterpret it
        value = interpret_bytes(value, data_type)

        #3. Store the value
        sps_header[name] = value

    return sps_header

def read_sps_data(mapped_file: mmap.mmap, start_byte: int)->list:
    """
    Reads the sweep data from the sps file.
    :param mapped_file: The memory mapped sps file
    :param start_byte: The byte to start reading the sps data from
    :return: A 2d list of each sweep, where the ith row is the data of the ith sweep
    """
    end_delimiter = interpret_bytes(b'\xFE\xFE', "UInt16")

    sweep_count = 0
    current_byte = start_byte
    sweep_data = []
    current_sweep = []
    try:
        while current_byte < mapped_file.size() - 1: #exclude end of file delimiter
            byte_val = interpret_bytes(extract_bytes(mapped_file, 2, current_byte), "UInt16")
            if byte_val == end_delimiter: # Reached the End-of-Sweep delimiter
                sweep_data.append(current_sweep)
                current_sweep = []
                sweep_count += 1
            else:
                current_sweep.append(byte_val)
            current_byte += 2
    except Exception as e:
        print(f"An error occurred: {e}, please tell whoever wrote this to lock in")
        exit(1)

    return sweep_data

def convert_sps_fits(sweep_data: np.ndarray, file_name, destination_dir: str)->str:
    """
    Taking the sweep data from the sps file and converting it into a fits file.
    :param sweep_data: The numpy array of the sweep data
    :return: The name of the new FITS file
    """
    # Create individual hdu
    hdu = fits.PrimaryHDU(data=sweep_data)
    hdu.header['OBJECT'] = 'RSS Spectrogram'
    hdu.header['COMMENT'] = 'Created from SPS sweep data'
    hdu.header['BUNIT'] = 'Intensity'

    # Create HDU list
    hdu_list = fits.HDUList([hdu])

    # Create the Fits file
    hdu_list.writeto(f'{destination_dir}/{file_name}.fits', overwrite=True)

    return 'test.fits'

def plot_fits_spectrogram(fits_filename: str):
    """
    Plots the spectrogram of a fits file.
    :param fits_filename: Name of the FITS file to display
    :return: None
    """
    with fits.open(fits_filename) as hdu_list:
        data = hdu_list[0].data #take the primary HDU
        plt.figure(figsize=(10, 6))
        plt.imshow(
            data.T,
            aspect='auto',
            cmap='viridis'
        )
        plt.xlabel('Sweep (time)')
        plt.ylabel('Frequency channel')
        plt.title(f"Converted ({fits_filename}) FITS Spectrogram")
        plt.colorbar(label='Intensity')
        plt.show()

def plot_sps_spectrogram(sweep_array):
    """
    Plots the spectrogram of a fits file.
    :param sweep_array: The numpy array of the sweep data
    :return: None
    """
    plt.figure(figsize=(10, 6))
    plt.imshow(
        sweep_array.T,  # transpose so frequency is vertical
        aspect='auto',
        cmap='viridis'
    )
    plt.xlabel('Sweep (time)')
    plt.ylabel('Frequency channel')
    plt.title('Original SPS Spectrogram ')
    plt.colorbar(label='Intensity')
    plt.show()

def main():
    file_path, dest_dir, show = get_args()
    with open(file_path, "rb") as file:
        mf = mmap.mmap(file.fileno(), 0, prot=mmap.PROT_READ)

        sps_header = extract_sps_header(mf)

        data_head = sps_header["NoteLength"] + 157 - 1

        sweep_data = read_sps_data(mf, data_head)

        sweep_array = np.array(sweep_data, dtype=np.uint16)

        fits_name = convert_sps_fits(sweep_array, os.path.basename(file_path), dest_dir)

        if show:
            plot_sps_spectrogram(sweep_array)
            plot_fits_spectrogram(fits_name)

if __name__ =='__main__':
    main()