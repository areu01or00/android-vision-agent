# Android AI Agent

A powerful AI-driven automation tool for Android devices that uses a hybrid approach combining direct commands with visual and structural UI analysis.

## Features

- **Dual-Model Architecture**: Separate specialized models for vision tasks and planning/reasoning tasks
- **Hybrid Command-Vision Approach**: Combines direct ADB commands with intelligent vision analysis
- **XML View Hierarchy Analysis**: Extracts precise UI structure for more accurate interaction
- **Flexible LLM Provider Support**: Works with both OpenAI and OpenRouter API providers
- **Intelligent Screen Analysis**: Automatically identifies apps, screen states, and UI elements
- **Smart Task Planning**: Breaks down complex tasks into executable steps
- **Robust Error Recovery**: Automatically detects and breaks out of repetitive action loops
- **Detailed Session Logs**: Comprehensive logging for debugging and analysis
- **Screen Recording**: Automatic screen recording during agent sessions

## Requirements

- Python 3.8+
- Android device with USB debugging enabled
- OpenAI API key or OpenRouter API key
- adb command-line tools installed and in PATH
- scrcpy installed for screen mirroring (optional, for debugging)
- PIL/Pillow Python library (for image processing)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/YourUsername/android-ai-agent.git
   cd android-ai-agent
   ```

2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with your API keys:
   ```
   # OpenAI API Keys
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_MODEL_1=gpt-4o
   OPENAI_MODEL_2=gpt-4-turbo
   
   # OpenRouter API Keys (alternative to OpenAI)
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   OPENROUTER_MODEL_1=microsoft/phi-4-multimodal-instruct
   OPENROUTER_MODEL_2=meta-llama/llama-3-70b-instruct
   ```

4. Connect your Android device via USB and enable USB debugging

## Usage

Run the agent:
```
python android_ai_agent.py
```

When prompted, select your LLM provider (OpenAI or OpenRouter).

Enter tasks using natural language, for example:
- "open twitter and search for AI news"
- "open gmail and compose an email"
- "open youtube and search for funny cat videos"
- "find the weather in New York"

You can also use direct commands:
- `context` - Analyze the current screen context
- `screenshot` - Take a screenshot
- `launch [app]` - Launch a specific app

## Architecture

The Android AI Agent uses a sophisticated hybrid approach:

### 1. Dual-Model Architecture

- **Vision Model** (`vision_model`): Specialized for visual understanding
  - Default: `gpt-4o` (OpenAI) or `microsoft/phi-4-multimodal-instruct` (OpenRouter)
  - Used for: Extracting text from screenshots, analyzing visual content
  
- **Planning Model** (`planning_model`): Specialized for reasoning and decision making
  - Default: `gpt-4-turbo` (OpenAI) or `meta-llama/llama-3-70b-instruct` (OpenRouter)
  - Used for: Analyzing tasks, determining actions, processing XML hierarchy

### 2. Hybrid Command-Vision Approach

1. **Task Analysis Phase**:
   - Analyzes user task using planning model
   - Determines if app launch is required
   - Creates execution plan

2. **Hybrid Execution Phase**:
   - **Step 1**: Vision model extracts visual information from screen
   - **Step 2**: Planning model reasons about this information to make decisions
   - **Step 3**: Direct commands execute appropriate actions

3. **XML View Hierarchy Analysis**:
   - Extracts precise UI structure via uiautomator
   - Provides exact coordinates, bounds, and properties of UI elements
   - Enables more precise interaction with the Android interface

## Key Components

- **Task Analyzer**: Determines if a specific app is needed for the task
- **Screen Context Analyzer**: Uses hybrid approach to identify app, screen state, and UI elements
- **Action Determiner**: Decides the next action based on task and current screen state
- **XML Hierarchy Extractor**: Provides structural data about the UI
- **Loop Detection**: Identifies and breaks repetitive action patterns

## Example Flow

Here's how the agent processes a typical task:

1. User inputs task: "open Twitter and search for Rahul Gandhi"
2. Task analyzer determines Twitter app needs to be launched
3. Agent launches Twitter app via direct ADB command
4. Screen context analyzer identifies the current screen using vision + planning models
5. Action determiner decides to tap on the search field
6. Agent inputs search query and submits
7. Agent analyzes results and reports completion

## Customization

You can customize the models used by modifying the environment variables in your `.env` file:

- `OPENAI_MODEL_1`: Vision model for OpenAI (default: gpt-4o)
- `OPENAI_MODEL_2`: Planning model for OpenAI (default: gpt-4-turbo)
- `OPENROUTER_MODEL_1`: Vision model for OpenRouter (default: microsoft/phi-4-multimodal-instruct)
- `OPENROUTER_MODEL_2`: Planning model for OpenRouter (default: meta-llama/llama-3-70b-instruct)

## Limitations

- Requires physical access to the Android device
- Some apps may have security measures preventing automation
- Performance depends on API responsiveness
- Device must be unlocked and debuggable

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[Your License Here] 
