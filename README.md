# Android AI Agent

A vision-powered automation tool for Android devices using GPT-4o vision capabilities to interact with UI elements.

## Overview

The Android AI Agent is a powerful tool that uses GPT-4o's vision capabilities to analyze Android screens and perform actions based on natural language commands. Instead of hard-coding UI interactions for each application, the agent takes screenshots, sends them to GPT-4o for analysis, and follows its recommendations.

This approach allows the agent to:
- Work with any app without app-specific code
- Adapt to UI changes and different app versions
- Handle complex tasks with natural language instructions
- Find and interact with UI elements based on visual appearance

## Features

- **Vision-First Approach**: Uses GPT-4o vision model to understand what's on screen
- **Natural Language Control**: Operate your device with plain-language commands
- **App Agnostic**: Works with any Android app without customization
- **Zero App-Specific Code**: No need to write custom code for different apps
- **Adapts to UI Changes**: Works even when apps update their interface
- **Multiple Input Methods**: Handles text input challenges with multiple fallback methods
- **Screen Mirroring**: View device actions in real-time with scrcpy
- **Explanatory Output**: Detailed logs of what is happening at each step

## Requirements

- Python 3.8+
- Android device with USB debugging enabled
- USB connection to your Android device
- ADB (Android Debug Bridge) installed and configured
- OpenAI API key (for GPT-4o access)
- scrcpy (for screen mirroring, optional but recommended)

## Setup

### 1. Connect your Android device

1. Enable Developer Options and USB Debugging on your Android device
2. Connect your device to your computer via USB
3. Authorize USB debugging when prompted on your device
4. Verify connection with `adb devices` (your device should be listed)

### 2. Install the required Python packages

```bash
pip install -r requirements.txt
```

### 3. Set up your OpenAI API key

Create a `.env` file in the project root with your OpenAI API key:

```
OPENAI_API_KEY=your-api-key-here
```

Or set it as an environment variable:

```bash
export OPENAI_API_KEY=your-api-key-here
```

### 4. Install scrcpy (optional but recommended)

For real-time visualization of device actions:

**Ubuntu/Debian:**
```bash
apt install scrcpy
```

**macOS:**
```bash
brew install scrcpy
```

**Windows:**
Download from [https://github.com/Genymobile/scrcpy/releases](https://github.com/Genymobile/scrcpy/releases)

## Usage

Run the AI agent with a task to perform:

```bash
python android_ai_agent.py
```

You'll be prompted to enter a task. Examples of tasks:

- "Open Twitter and search for news"
- "Open camera and take a photo"
- "Open Gmail and compose a new email to someone@example.com"
- "Open Zomato and search for McDonald's"

The agent will:
1. Parse your command to understand the intent
2. Open the required app
3. Take a screenshot
4. Analyze the screen with GPT-4o vision
5. Perform the appropriate actions based on visual analysis
6. Repeat steps 3-5 for multi-step tasks

## How It Works

1. **Task Parsing**: The AI breaks down your natural language request into structured actions
2. **App Launching**: Opens the target application
3. **Screenshot Analysis**: Takes a screenshot of the current state
4. **Vision-Guided Action**: GPT-4o analyzes the screenshot and recommends precise actions
5. **Execution**: The agent performs the recommended actions (clicks, text input, etc.)
6. **Verification**: Another screenshot is taken to verify the results
7. **Next Steps**: For multi-step tasks, the process repeats from step 3

## Known Limitations

- **Text Input Challenges**: Android's keyboard input can be challenging; multiple fallback methods are implemented
- **API Costs**: Uses OpenAI's GPT-4o API, which has usage costs
- **Vision Model Availability**: Requires access to GPT-4o or another vision model
- **Task Complexity**: Very complex, multi-step tasks may require breaking down into simpler steps
- **App Compatibility**: Some apps with unusual UIs may be challenging
- **Authentication**: May struggle with apps requiring login (biometrics, CAPTCHA, etc.)

## Project Structure

```
android-ai-agent/
├── android_ai_agent.py   # Main agent implementation
├── requirements.txt      # Python dependencies
├── README.md            # This file
└── .env                 # Environment variables (create this)
```

## Customizing the Agent

You can modify the `analyze_screen_with_vision` method to adjust how the agent interprets screens or change the prompts to optimize for specific types of interactions.

## Contributing

Contributions are welcome! Areas for improvement:

- Add support for more vision models
- Improve text input reliability
- Enhance task parsing for complex instructions
- Add better error recovery mechanisms

## License

MIT License - See LICENSE file for details.