from typing import Tuple, Any
import os
from pathlib import Path
from typing import List
import dropbox
import logging
from typing import Any
from dotenv import load_dotenv
import random
from datetime import date
import config


# -------------------------------------------------------------------------
# Handler for checking arguments and creation of options
# -------------------------------------------------------------------------
def get_args() -> Tuple[str, dict[str, Any]]:
    load_dotenv()
    """
    Parse command-line arguments for Dropbox sync
    Returns:
        path (str): Path to output folder
        random (Optional[float]): Number of files to randomly sample
        out (bool): Whether to log downloaded files
    """
    options = {}
    options["log"] = config.LOG_DBX
    options["random"] = config.SAMPLE_RATE_DBX
    options["dry-run"] = config.DRY_RUN_DBX
    options["out"] = config.OUTPUT_DBX
    options["flat"] = config.FLAT_DBX
    options["exclude"] = config.EXCLUDE_DBX
    options["want"] = config.WANT_DBX

    if not os.path.exists(config.DESTINATION_PATH_DBX):
        RuntimeError("ERROR: User Folder Not Found!")

    if options["random"] < 0 or options["random"] > 1.0:
        RuntimeError("ERROR: Probability needs to be between 0 and 1!")

    if len(options["want"]) != 0 and len(options["exclude"]) != 0:
        RuntimeError("ERROR: Can not have wants and excludes!")

    print(config.DESTINATION_PATH_DBX)
    return config.DESTINATION_PATH_DBX, options

def _rec_file_creator(dir_path: Path, root_dir: Path, file_paths: List[str], flat: bool) -> None:
    """Helper function to recursively walk through directories and collect file paths"""
    for item in dir_path.iterdir():
        if item.is_dir(): #if a directory then mark it with 'dir%'
            rel_path = "dir%/" + str(item.relative_to(root_dir))
            file_paths.append(rel_path)
            _rec_file_creator(item, root_dir, file_paths, flat)

        elif item.is_file(): #if a directory then mark it with 'file%'
            rel_path = "file%/" + (str(item.relative_to(root_dir)) if not flat else str(item.name))
            file_paths.append(rel_path)

def create_file_list(dir_path: str, flat_download: bool) -> List[str]:
    """
    Recursively create a list of all file and folder paths inside dir_path
    Each folder starts with 'dir%' and each file with 'file%'
    """
    root_dir = Path(dir_path).resolve()
    file_paths: List[str] = []

    _rec_file_creator(root_dir, root_dir, file_paths, flat_download)

    return file_paths

# -------------------------------------------------------------------------
# Context for syncing
# -------------------------------------------------------------------------
class SyncContext:
    def __init__(self, dbx: dropbox.Dropbox, options: dict[str, Any], dest_root: str, user_dat_paths: [str]) -> None:
        self.dbx = dbx
        self.options = options
        self.dest_root = dest_root
        self.user_dat_paths = user_dat_paths
        self.output_txt = ""

# -------------------------------------------------------------------------
# Setup logging and logging colors
# -------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)

def log_red(message: str) -> None:
    logging.error(f"\033[91m{message}\033[0m")

def log_green(message: str) -> None:
    logging.info(f"\033[92m{message}\033[0m")

def log_blue(message: str) -> None:
    logging.info(f"\033[94m{message}\033[0m")


# -------------------------------------------------------------------------
# Dropbox Authentication
# -------------------------------------------------------------------------
def load_dbx_api() -> dropbox.Dropbox:
    """Load Dropbox API client using token from environment variable"""

    load_dotenv()

    token = os.getenv("DBX_TOKEN")
    if not token:
        raise RuntimeError("Dropbox token not found. Set DBX_TOKEN environment variable.")
    return dropbox.Dropbox(token)

# -------------------------------------------------------------------------
# File Ops
# -------------------------------------------------------------------------
def create_folder(ctx: SyncContext, folder_name: str, src_path: str, depth: int) -> None:
    """Create a folder locally"""
    try:
        os.makedirs(os.path.join(ctx.dest_root, src_path.strip("/"), folder_name), exist_ok=True)
        log_blue(f"Created folder: {folder_name} in {ctx.dest_root}")
        ctx.output_txt += "+d:" + '\t'*depth + f"{folder_name}\n"
    except Exception as err:
        logging.error(f"Failed to create folder {folder_name}: {err}")

def download_file(ctx: SyncContext, src_path: str, depth: int) -> None:
    """Download a file from Dropbox to local directory"""
    try:
        # Load in the file data
        metadata, res = ctx.dbx.files_download(src_path)
        # Create the local path of downloaded file
        local_path = os.path.join(ctx.dest_root, src_path.strip("/")) if not ctx.options["flat"] \
            else f"{ctx.dest_root}/{metadata.name}"
        if not ctx.options["dry-run"]:  # (skip if doing a dry run)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            # Write the file
            with open(local_path, "wb") as f:
                f.write(res.content)

        log_green(f"Downloaded {metadata.name} to {local_path}")
        ctx.output_txt += "+f:" + '\t'*depth + f"{metadata.name}\n"

    except dropbox.exceptions.ApiError as err:
        logging.error(f"Dropbox API error downloading {src_path}: {err}")

# -------------------------------------------------------------------------
# Recursive Sync
# -------------------------------------------------------------------------
def recursive_sync(ctx: SyncContext, src_path: str, depth: int) -> None:
    """Recursively sync Dropbox folder with local directory"""
    try:
        result = ctx.dbx.files_list_folder(src_path)
        for entry in result.entries:
            # Entry is a FILE
            if isinstance(entry, dropbox.files.FileMetadata):
                # Get the path of the file
                dbx_file_path = f"{entry.path_display}" if not ctx.options["flat"] else f"/{entry.name}"
                # Check if the file exists AND if it passes the probability
                if (f"file%{dbx_file_path}" not in ctx.user_dat_paths and
                        random.random() <= ctx.options["random"] and
                        (entry.name.split('.')[-1] not in ctx.options["exclude"] if len(ctx.options["exclude"]) > 0 else True) and
                        (entry.name.split('.')[-1] in ctx.options["want"] if len(ctx.options["want"]) > 0 else True)
                ):
                    # Download the missing file
                    download_file(ctx, entry.path_display, depth)

            # Entry is a FOLDER
            elif isinstance(entry, dropbox.files.FolderMetadata):
                # Get the path to the dir
                dbx_dir_path = f"{entry.path_display}"
                # Check if the dir exists (don't make new one if flat output)
                if f"dir%{dbx_dir_path}" not in ctx.user_dat_paths and not ctx.options["flat"]:
                    # Create the missing dir
                    create_folder(ctx, entry.name, src_path, depth)

                # Recurse inside the directory
                recursive_sync(ctx, entry.path_display, depth + 1)

    except dropbox.exceptions.ApiError as err:
        logging.error(f"Error listing folder {src_path}: {err}")

# -------------------------------------------------------------------------
# Main entry
# -------------------------------------------------------------------------
def update_local_dir(dbx: dropbox.Dropbox, options: dict[str, any], user_dir_path: str, user_dat_paths: [str]) -> None:
    """Update local directory with missing files from Dropbox"""
    # Create sync context
    ctx = SyncContext(dbx, options, user_dir_path, user_dat_paths)

    # Disable logging if wanted
    if not ctx.options["log"]:
        logging.disable(logging.INFO)

    logging.info("Starting Dropbox sync...")

    # Begin recursive walk through the dropbox
    recursive_sync(ctx, "", 0)

    logging.info("Sync completed successfully.")

    if ctx.options["out"]:
        with open(f"{user_dir_path}/dbx_{date.today()}.out", "w") as f:
            f.write(ctx.output_txt)
        print(f"Output written to dbx_{date.today()}.out")

if __name__ == "__main__":
    # Take in args
    user_folder_path, options = get_args()

    # Recursively go though and map of files
    usr_files = create_file_list(user_folder_path, options["flat"])

    # Load Dropbox Api
    dbx = load_dbx_api()

    # Compare files in input dir to GRL files
    update_local_dir(dbx, options, user_folder_path, usr_files)
