#!/bin/bash
# Development script: setup venv, install dependencies, and run the app

# Default Python command (can be overridden)
PYTHON="${PYTHON:-python}"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  $PYTHON -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run the app
echo "Starting Gamer Reminder..."
python -m apps.desktop

