# Android Vision Agent

A powerful AI-driven automation tool for Android devices that uses OpenAI's GPT-4o vision capabilities to analyze screens and perform actions. This agent can automate tasks on Android with natural language instructions.

## Features

- **Direct OpenAI Integration**: Uses GPT-4o vision API for screen analysis and decision making
- **Task Planning**: Analyzes tasks and determines if app launching is required
- **Interactive Mode**: Simple command-line interface for issuing instructions
- **Screen Recording**: Automatically records sessions for later review
- **App Discovery**: Can find and launch apps by name
- **Multiple Action Types**: Supports tapping, typing, scrolling and waiting

## Requirements

- Python 3.8+
- Android device with USB debugging enabled
- OpenAI API key (GPT-4o access required)
- scrcpy installed for screen recording
- adb command-line tools

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/areu01or00/android-vision-agent.git
   cd android-vision-agent
   ```

2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

4. Connect your Android device via USB and enable USB debugging

## Usage

Run the agent:
```
python android_ai_agent.py
```

Enter tasks using natural language, for example:
- "open twitter and scroll through my timeline"
- "open chrome and search for AI news"
- "open gmail and compose an email"
- "open youtube and search for coding tutorials"

### Available Commands

- `screenshot` - Takes a screenshot of the current screen
- `context` - Analyzes the current screen context
- `launch [app]` - Launches an app (e.g., `launch chrome`)
- `exit` or `quit` - Ends the session
- `help` - Shows available commands

## How It Works

The Android Vision Agent uses GPT-4o to analyze screenshots and determine actions:

1. **Task Analysis Phase**:
   - Determines if an app needs to be launched
   - Identifies the specific app to launch
   - Plans what to do after the app is launched

2. **Execution Phase**:
   - Takes screenshots of the current screen
   - Sends the screenshot to GPT-4o for analysis
   - Determines the next action (tap, type, scroll, etc.)
   - Executes the action using ADB commands
   - Repeats until the task is complete

## Key Design Principles

- **Vision-Based UI Analysis**: Uses GPT-4o to "see" and understand the screen
- **Percentage-Based Coordinates**: Taps use percentages of screen width/height for device independence
- **Built-in Session Recording**: Automatically records screen sessions for later review
- **Direct ADB Commands**: Uses ADB directly for reliable device interaction
- **JSON Communication**: All AI responses use JSON format for consistent parsing
- **Image Optimization**: Resizes screenshots to reduce API token usage

## Example Flows

**Simple Task**: "open twitter"
```
1. Task planner identifies Twitter app
2. Agent launches Twitter app directly
3. Task marked as complete
```

**Complex Task**: "open twitter and scroll through my timeline"
```
1. Task planner identifies Twitter app
2. Agent launches Twitter app
3. Agent takes screenshots and analyzes screen
4. Agent scrolls through timeline multiple times
5. Task continues until completion or max steps reached
```

## Performance Optimization

For best performance:
- Use a USB 3.0 connection instead of wireless debugging
- Keep your device screen on and unlocked 
- Close unnecessary background apps on your phone
- Use a device with good screen resolution

## Limitations

- Requires physical access to the Android device
- Some apps may have security measures preventing automation
- Performance depends on OpenAI API responsiveness
- May struggle with highly dynamic content or complex interfaces

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - See LICENSE file for details.