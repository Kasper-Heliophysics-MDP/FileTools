#!/bin/bash

# Run dropbox and collect data
echo "Making Temp File..."
mkdir -p "./sps_files"

PROBABILITY=0.001

echo "Running DropBox Sync..."
python3 ./Dropbox_Sync/src/dropbox_sync.py -p ./sps_files -r $PROBABILITY --flat --out --log -w sps

# Convert data
echo "Converting Files..."
python3 ./STTC/src/convertSPS.py -s ./sps_files -d ./fits_out

# Delete sps files
echo "Download and conversion completed! Deleting sps files..."
rm -r "./sps_files"
