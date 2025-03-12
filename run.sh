#!/bin/bash

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3 and try again."
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ]; then
    # Check if .env file exists
    if [ -f ".env" ]; then
        echo "Loading OpenAI API key from .env file..."
        export $(grep -v '^#' .env | xargs)
    else
        echo "OPENAI_API_KEY is not set and .env file does not exist."
        echo "Please set your OpenAI API key by creating a .env file with OPENAI_API_KEY=your-key-here"
        exit 1
    fi
fi

# Run the agent
echo "Starting Android AI Agent..."
python android_ai_agent.py