# Android Vision Agent

A powerful AI-driven automation tool for Android devices that combines direct actions with XML-based UI analysis for precise control. Now with multi-step planning and cost-efficient operation.

## Features

- **Fast Direct Actions**: Instantly launches apps and performs common tasks without screenshots
- **XML-Based UI Analysis**: Uses UI hierarchy data for precise element targeting without coordinates
- **Multi-Step Planning**: Plans several steps at once to reduce API calls and improve performance
- **Cost-Efficient Operation**: Uses gpt-4o-mini and smart caching for lower API costs
- **Smart Task Planning**: Automatically breaks down complex tasks into executable steps
- **Element-Based Interaction**: Targets UI elements directly by ID, text or description
- **Adaptive Execution**: Combines direct commands with UI analysis for optimal performance

## Requirements

- Python 3.8+
- Android device with USB debugging enabled
- OpenAI API key
- scrcpy installed (optional for screen mirroring)
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
python android_vision_agent.py
```

Or use the provided shell script:
```
chmod +x run.sh  # Make it executable first time
./run.sh
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
   - **Stage 2**: XML-based LLM guidance for complex interactions
   - The LLM analyzes UI hierarchy XML data to:
     - Plan multiple steps at once for efficiency
     - Identify UI elements by resourceId, text, or content-description
     - Target exact elements rather than screen coordinates
     - Execute interactions with precision

## Key Improvements

- **Multi-Step Planning**: Plans multiple steps at once to reduce API calls and cost
  - Plans up to 5 actions in a single API call
  - Handles repetitive actions (like scrolling) with repetition counts
  - Adaptive verification only when needed

- **XML Preprocessing & Caching**:
  - Simplifies XML before sending to the LLM for efficient processing
  - Caches UI state hashes to avoid redundant API calls
  - Identifies when UI hasn't significantly changed

- **Cost-Efficient Design**:
  - Uses gpt-4o-mini instead of more expensive models
  - Reduces token usage with optimized prompts
  - Only refreshes UI analysis when necessary

- **No More Screenshot Guessing**: Instead of analyzing screenshots and guessing coordinates, the agent now:
  - Gets the exact UI hierarchy XML representation
  - Identifies elements by their unique IDs, text, or descriptions
  - Clicks and interacts with precise UI elements
  - Handles complex interfaces reliably

## Example Flows

**Simple Task**: "open twitter"
```
1. Task planner identifies this as a direct action
2. Agent launches Twitter app directly
3. Task marked as complete
```

**Complex Task**: "open gmail and scroll till you find email from John"
```
1. Task planner identifies this as a multi-stage task
2. Stage 1: Direct launch of Gmail app
3. Stage 2: Multi-step planning:
   - Plan identifies that this requires multiple scrolls
   - Plans 5 scrolling actions in a single API call
   - Executes all 5 scrolls
   - Checks UI to see if email is found
   - If not, plans additional steps
   - Continues until email is found or maximum steps reached
```

## Performance Optimization

For best performance:
- Use a USB 3.0 connection instead of wireless debugging
- Keep your device screen on and unlocked 
- Close unnecessary background apps on your phone
- Ensure your phone has sufficient storage space available

## Limitations

- Requires physical access to the Android device
- Some apps may have security measures preventing automation
- Performance depends on OpenAI API responsiveness
- Some apps may not expose proper element IDs

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - See LICENSE file for details.

## Detailed Documentation

For more detailed usage instructions, see [USAGE.md](USAGE.md).