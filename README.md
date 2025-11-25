# File Tools Repository

This repository contains two Python file tools to assist in retreiving and converting to a better format of SRB data.

1. **SPS-to-FITS Converter (STTC)**: Convert SPS radio burst files into FITS format and visualize the spectrogram.
2. **Dropbox Sync Tool**: Synchronize a local folder with a Dropbox folder with filtering, logging, and dry-run options.

---

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Setup](#setup)
- [Usage](#usage)
  - [SPS-to-FITS Converter](#sps-to-fits-converter)
  - [Dropbox Sync Tool](#dropbox-sync-tool)
- [Requirements](#requirements)

---

## Features

### SPS-to-FITS Converter
- Convert SPS sweep files into FITS format.
- Plot original SPS spectrogram and FITS spectrogram.
- Supports large files via memory mapping.

### Dropbox Sync Tool
- Recursive sync from Dropbox to local folder.
- Skip specific file types.
- Flat download option (no subfolders).
- Dry-run mode (simulate without downloading).
- Random sampling of files.
- Terminal and file logging.
- Configurable via `.env` file.

---

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/{yourusername}/FileTools.git
cd utility-tools
```
```bash
pip install -r requirements.txt
```

---

## Setup

### Dropbox Configuration
Create a `.env` file in the `Dropbox_Sync` folder with your Dropbox API token:
```bash
DROPBOX_TOKEN=your_access_token_here
```
You can generate a token at [Dropbox Developers](https://www.dropbox.com/developers/apps)

--- 

## Usage

### SPS-to-Fits Converter
```bash
python terminal_src/sps_to_fits.py -s path/to/input.sps -d path/to/output_folder --show
```

| Flag                | Type  | Default      | Description                               |
|---------------------| ----- | ------------ |-------------------------------------------|
| `-s, --source`      | `str` | **required** | Path to directory of SPS file             |
| `-d, --destination` | `str` | `.`          | Output directory (default current folder) |
| `-o --output`       | flag  | False        | Show spectrogram plots after conversion   |
| `-n --output`       | flag  | False        | Export the data as a numpy file           |
| `-c --output`       | flag  | False        | Export the data as a csv file             |

### Dropbox Sync Tool
```bash
python terminal_src/dropbox_sync.py -p ./files
```
| Flag            | Type      | Default      | Description                                                 |
|-----------------| --------- | ------------ |-------------------------------------------------------------|
| `-p, --path`    | `str`     | **required** | Path to the local folder where files will be synced         |
| `-r, --random`  | `float`   | 1.0          | Probability of files being downloaded (0.0–1.0]             |
| `-o, --out`     | flag      | False        | Creates an output `.out` listing all newly downloaded files |
| `-l, --log`     | flag      | False        | Logs downloaded files to the terminal                       |
| `-f, --flat`    | flag      | False        | Downloads all files into a flat structure (no subfolders)   |
| `-e, --exclude` | list[str] | []           | List of file extensions to exclude (e.g. `.png .mp4`)       |
| `-d, --dry-run` | flag      | False        | Simulates the sync without downloading any files            |
| `-w, --want`    | list[str]      | []        | List of file extensions to include (e.g. `.sps .csv`)       |

`--want` and `--exclude` can't be used in tandem.

Examples: 
```bash
# Normal sync
python terminal_src/dropbox_sync.py -p ./files

# Sync but skip .png and .mp4 files
python terminal_src/dropbox_sync.py -p ./files -e .png .mp4

# Sync with logging
python terminal_src/dropbox_sync.py -p ./files --log

# Simulate without downloading
python terminal_src/dropbox_sync.py -p ./files --dry-run

# Flat structure download
python terminal_src/dropbox_sync.py -p ./files --flat

# Download files with 50% probability
python terminal_src/dropbox_sync.py -p ./files -r 0.5
```