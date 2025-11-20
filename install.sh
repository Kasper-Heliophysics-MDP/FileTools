#!/bin/bash

echo "Upgrade pip..."
pip install --upgrade pip

echo "Install required Python packages..."
pip install -r requirements.txt

echo "Setup complete!"