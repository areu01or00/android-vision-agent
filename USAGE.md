# Android Vision Agent Usage Guide

This guide shows you how to use the improved Android Vision Agent with its LLM-based task planning and vision-guided automation.

## Getting Started

1. Connect your Android device via USB
2. Enable USB debugging on your device
3. Make sure your OpenAI API key is in the `.env` file
4. Activate your virtual environment:
   ```
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
5. Run the agent:
   ```
   python simple_android_vision_agent.py
   ```

## Task Formats

The Android Vision Agent now supports both simple and complex tasks:

### Simple App Launch
```
open twitter
launch chrome
start gmail
```
These are executed directly without taking screenshots.

### Complex Multi-Step Tasks
```
open twitter and search for AI news
open chrome and search for medicinal properties of marijuana
open gmail and compose an email to example@gmail.com
```
These are broken down into stages:
1. Direct app launch
2. Vision-guided completion of the remaining steps

## How Tasks Are Processed

The agent now uses a two-phase approach:

1. **Planning Phase** (Using GPT-3.5-Turbo):
   - Analyzes your task request
   - Determines if it can be directly executed
   - Breaks it down into stages
   - Passes context between stages

2. **Execution Phase**:
   - For simple tasks: Uses direct app launching
   - For complex tasks: Combines direct app launching with vision-guided steps

## Task Examples and What Happens

### Example 1: "open twitter"
```
📋 Task Plan:
  - has_app_launch: True
  - app_name: Twitter
  - requires_vision_after_launch: False
  
📱 Stage 1/1: Launching twitter (com.twitter.android) directly
✅ Successfully launched twitter
```

### Example 2: "open chrome and search for medicinal properties of marijuana"
```
📋 Task Plan:
  - has_app_launch: True
  - app_name: Chrome
  - requires_vision_after_launch: True
  - post_launch_steps: Search for 'medicinal properties of marijuana' in the Chrome browser

📱 Stage 1/2: Launching chrome (com.android.chrome) directly
✅ Successfully launched chrome
📸 Stage 2/2: Using vision guidance for: Search for 'medicinal properties of marijuana' in the Chrome browser
```

## Tips for Best Results

1. **Be Specific**: Clearly state which app you want to use
2. **Use Natural Language**: The agent understands phrases like "open X and do Y"
3. **Patience with Complex UIs**: Some apps have complex interfaces that may require more steps
4. **Watch the Output**: The agent now provides detailed progress information
5. **Feedback**: After a task completes, provide feedback on whether it worked

## Troubleshooting

If you encounter issues:

1. **App Not Found**: Make sure the app is installed on your device
2. **Connection Issues**: Verify USB debugging is enabled and authorized
3. **Vision Analysis Failures**: Sometimes retry with clearer instructions
4. **Text Input Problems**: The agent tries multiple methods, but some secure fields may be restricted

## Advanced Features

- **Context Awareness**: The vision model is informed about completed steps
- **Adaptive Delays**: Different waits based on action type
- **Error Recovery**: Tries multiple methods for text input
- **Task Analysis**: Shows reasoning for each action taken