# Android Vision Agent

A powerful AI-driven automation tool for Android devices that combines direct actions with vision-based guidance.

## Features

- **Fast Direct Actions**: Instantly launches apps and performs common tasks without screenshots
- **Vision-Guided Navigation**: Uses GPT-4o vision model to navigate complex UI interactions
- **Smart Task Planning**: Automatically breaks down complex tasks into executable steps
- **Robust Text Input**: Multiple fallback methods for reliable text entry
- **Adaptive Execution**: Combines direct commands with vision for optimal performance

## Requirements

- Python 3.8+
- Android device with USB debugging enabled
- OpenAI API key (for GPT-4o vision model)
- scrcpy installed (for screen mirroring)
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
python simple_android_vision_agent.py
```

Enter tasks using natural language, for example:
- "open twitter and search for AI news"
- "open chrome and search for medicinal properties of marijuana"
- "open gmail and compose an email to example@gmail.com"
- "open youtube and search for funny cat videos"

## How It Works

The Android Vision Agent uses a two-phase approach to execute tasks:

1. **Task Planning Phase**:
   - A language model (GPT-3.5 Turbo) analyzes the task
   - Determines if direct app launching is possible
   - Identifies additional steps needed after app launch
   - Creates a structured execution plan

2. **Execution Phase**:
   - **Stage 1**: Direct actions (app launching) when possible
   - **Stage 2**: Vision-guided interactions for complex tasks
   - The vision model (GPT-4o) analyzes screenshots to determine precise interactions
   - Executes actions with robust error handling and recovery

## Key Components

- **Task Planner**: Breaks down complex tasks into manageable steps
- **Direct Action Handler**: Executes known actions without vision guidance
- **Vision-Guided Controller**: Uses screenshots and GPT-4o for complex interactions
- **Multi-Stage Pipeline**: Manages transitions between direct and vision-guided stages

## Example Flows

**Simple Task**: "open twitter"
```
1. Task planner identifies this as a direct action
2. Agent launches Twitter app directly
3. Task marked as complete
```

**Complex Task**: "open chrome and search for medicinal properties of marijuana"
```
1. Task planner identifies this as a multi-stage task
2. Stage 1: Direct launch of Chrome app
3. Stage 2: Vision-guided process to:
   - Find and click search bar
   - Input search text
   - Submit search
   - Verify results
```

## Limitations

- Requires physical access to the Android device
- Some apps may have security measures preventing automation
- Performance depends on OpenAI API responsiveness
- Screen recording not supported in some secure apps

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - See LICENSE file for details.