# Android Vision Agent Usage Guide

This document provides information on how to use the Android Vision Agent for automating tasks on Android devices.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- ADB (Android Debug Bridge) installed and in your PATH
- scrcpy installed (optional but recommended for visual feedback)
- An Android device with USB debugging enabled
- OpenAI API key

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/areu01or00/android-vision-agent.git
   cd android-vision-agent
   ```

2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Initialize UIAutomator2:
   ```bash
   python -m uiautomator2 init
   ```

4. Set up your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="your_api_key_here"
   ```
   Or create a `.env` file in the project directory with:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

### Running the Agent

To start the agent:
```bash
python android_vision_agent.py
```

Or use the convenience script:
```bash
./run.sh
```

## Task Formats

The Android Vision Agent accepts natural language commands. Here are some examples:

- Simple app launch: `open gmail`
- Navigational task: `open settings and turn on wifi`
- Text messaging: `send a message to John saying I'll be late`
- Social media: `post a new status on twitter saying Hello world`
- Email: `compose an email to example@example.com with subject Meeting tomorrow`
- Complex tasks: `find nearby restaurants on google maps, sort by rating and navigate to the top one`

## How It Works

The Android Vision Agent uses a two-phase approach:

1. **Initial Task Analysis**: The agent first analyzes your task to determine if it requires launching an app or other direct actions.

2. **XML-based UI Analysis with Multi-Step Planning**: The agent uses XML data from the phone's UI to understand what's on screen. It then uses a language model (GPT-4o-mini) to plan multiple steps at once, which is more efficient than planning each step individually.

The agent also uses caching to avoid redundant API calls for similar UI states.

## Cost-Efficient Design

The Android Vision Agent is designed to be cost-efficient:

- **Multi-step planning**: Plans multiple actions at once to reduce API calls
- **XML preprocessing**: Simplifies the UI data before sending to the LLM
- **UI state caching**: Avoids repeated API calls for similar screens
- **gpt-4o-mini**: Uses a smaller, more efficient model for text-based analysis
- **Adaptive verification**: Only checks the UI when necessary

## Advanced Features

### Direct App Launch

The agent maintains a database of common app package names for direct launching, which bypasses the need for UI analysis for simple "open app" tasks.

### Repetitive Action Handling

For tasks that involve repetitive actions (like scrolling multiple times), the agent can bundle these into a single operation with a repeat count.

### Fault Tolerance

If an element can't be found using the primary selector method, the agent will try alternative methods like text matching or class+index combinations.

## Troubleshooting

### UIAutomator Issues

If you experience issues with UI hierarchy retrieval:

```bash
# Reinitialize UIAutomator2 with reinstall option
python -m uiautomator2 init --reinstall

# Check if the UIAutomator service is running
adb shell "ps -A | grep uiautomator"
```

### Connection Issues

If the agent can't connect to your device:

```bash
# List connected devices
adb devices

# Restart ADB
adb kill-server
adb start-server
```

### XML Hierarchy Not Available

The agent tries multiple methods to get the UI hierarchy. If all fail, you may need to:

```bash
# Manually dump UI hierarchy to check if working
adb shell uiautomator dump /sdcard/window_dump.xml
adb pull /sdcard/window_dump.xml

# Create writable directory if needed
adb shell "mkdir -p /data/local/tmp"
adb shell "chmod 777 /data/local/tmp"
adb shell "uiautomator dump /data/local/tmp/view.xml"
adb pull /data/local/tmp/view.xml
```

## Performance Optimization

To get the best performance:

1. Use a USB 3.0 connection instead of wireless debugging
2. Keep your device screen on and unlocked
3. Close unnecessary background apps on your phone
4. Ensure your phone has sufficient storage space available
5. Consider lowering resolution with scrcpy if using screen mirroring

## Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `OPENAI_MODEL`: Override the default model (optional)
- `DEBUG_MODE`: Set to "1" for verbose logging (optional)

## Examples

### Navigation Example
```
open settings and navigate to connections
```

### Social Media Example
```
open twitter and search for #androiddev
```

### Productivity Example
```
open gmail, compose a new email to boss@example.com with subject Quarterly Report and body The report is ready for review
```