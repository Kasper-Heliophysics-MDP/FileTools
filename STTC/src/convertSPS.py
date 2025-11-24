import numpy as np
import mmap
import os
import struct
from typing import Any, Tuple
import matplotlib.pyplot as plt
from astropy.io import fits
import argparse
import datetime

def get_args()->Tuple[str, str, bool, bool, bool]:
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
        help="Path to the directory with all SPS files"
    )
    parser.add_argument(
        "-d", "--destination",
        required=False,
        type=str,
        default=".",  # default to current directory
        help="Path to output directory (default: current directory)"
    )
    parser.add_argument(
        "-o", "--output",
        action="store_true",
        help="If set true will output the spectrogram plots"
    )
    parser.add_argument(
        "-n", "--numpy",
        action="store_true",
        help="If set true will output the spectrogram plots as .npy files"
    )
    parser.add_argument(
        "-c", "--csv",
        action="store_true",
        help="If set true will output the spectrogram plots as .csv files"
    )
    args = parser.parse_args()

    # Check source file
    if not os.path.exists(args.source):
        raise RuntimeError(f"ERROR: SPS directory not found: {args.source}")
    if not os.path.isdir(args.source):
        raise RuntimeError(f"ERROR: Source path is not a dir: {args.source}")

    # Check destination folder
    if not os.path.exists(args.destination):
        try:
            os.makedirs(args.destination)
        except Exception as e:
            raise RuntimeError(f"ERROR: Cannot create destination folder '{args.destination}': {e}")
    elif not os.path.isdir(args.destination):
        raise RuntimeError(f"ERROR: Destination path is not a directory: {args.destination}")

    return args.source, args.destination, args.output, args.numpy, args.csv

def get_sps_in_directory(directory_path: str)->list:
    """
    Creates a list of all the sps files in the given directory.
    :param directory_path: The directory to search for sps files
    :return: A list of all the sps files in the given directory
    """
    sps_files = []
    for root, dirs, files in os.walk(directory_path):
        for f in files:
            if f.lower().endswith('.sps'):
                sps_files.append(os.path.join(root, f))
    return sps_files

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
        while current_byte < mapped_file.size() - 1: # Exclude end of file delimiter
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
        return []

    return sweep_data

def sps_to_datetime(value):
    """
    Takes a Microsoft Date and converts it to a UTC timestamp
    :param value: The Date to convert
    """
    # SPS epoch: 1900-01-03
    epoch = datetime.datetime(1900, 1, 3)
    delta = datetime.timedelta(days=float(value))
    return (epoch + delta).isoformat()

def convert_sps_fits(sweep_data: np.ndarray, sps_header: dict, file_name: str, destination_dir: str,
                     as_numpy: bool, as_csv: bool)->str:
    """
    Taking the sweep data from the sps file and converting it into a fits file.
    :param sweep_data: The numpy array of the sweep data
    :param sps_header: Dictionary with the header values of the sps file
    :param file_name: The name of the input file
    :param destination_dir: The destination directory
    :param as_numpy: Whether to write the sweep data as a numpy array
    :return: The name of the new FITS file
    """
    # Create individual hdu
    hdu = fits.PrimaryHDU(data=sweep_data)
    hdu.header['OBJECT']    = 'RSS Spectrogram'
    hdu.header['COMMENT']   = 'Created from SPS sweep data'
    hdu.header['BUNIT']     = 'Intensity'
    hdu.header['OBS-LAT']   = sps_header['Latitude']
    hdu.header['OBS-LONG']  = sps_header['Longitude']
    hdu.header['SOURCE']    = sps_header['Name']
    hdu.header['DATE-OBS']  = sps_to_datetime(sps_header['Start'])
    hdu.header['DATE-END']  = sps_to_datetime(sps_header['End'])

    # Create HDU list
    hdu_list = fits.HDUList([hdu])

    # Create the Fits file
    file_path = f'{destination_dir}/{file_name[:-4]}'
    if as_csv: # CSV
        a = np.asarray(sweep_data)
        np.savetxt(f"{file_path}.csv", a, delimiter=",")
    if as_numpy: # Numpy
        np.save(f'{file_path}.npy', sweep_data)
    if not as_csv and not as_numpy: # Fits
        file_path = f'{file_path}.fits'
        hdu_list.writeto(file_path, overwrite=True)

    return file_path

def plot_fits_spectrogram(fits_filename: str)->None:
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

def plot_sps_spectrogram(sweep_array: np.ndarray)->None:
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
    src_dir, dest_dir, show, as_numpy, as_csv = get_args()
    sps_files = get_sps_in_directory(src_dir)

    print(f"Converting {len(sps_files)} sps files...")

    count = 0
    for file_path in sps_files:
        with open(file_path, "rb") as file:
            #1. Memory Map File
            mf = mmap.mmap(file.fileno(), 0, prot=mmap.PROT_READ)

            #2. Extract the SPS header
            sps_header = extract_sps_header(mf)

            #3. Get the starting byte of actual data
            data_head = sps_header["NoteLength"] + 157 - 1

            #4. Read in the data
            sweep_data = read_sps_data(mf, data_head)
            if len(sweep_data) == 0: #If data reading went wrong skip this file
                continue

            #5. Convert to numpy array
            sweep_array = np.array(sweep_data, dtype=np.uint16)

            #6. Convert to a fits file! (or numpy if specified)
            fits_path = convert_sps_fits(sweep_array, sps_header, os.path.basename(file_path), dest_dir, as_numpy, as_csv)

            #7. Display the results (optional)
            count += 1
            print(f"\tConverted {count}/{len(sps_files)} sps files...")
            if show and not as_numpy and not as_csv:
                plot_sps_spectrogram(sweep_array)
                plot_fits_spectrogram(fits_path)

    print(f"Complete!")

if __name__ =='__main__':
    main()