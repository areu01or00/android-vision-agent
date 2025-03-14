# Android AI Agent Usage Guide

This guide shows you how to use the Android AI Agent with its LLM-based task planning and vision-guided automation.

## Getting Started

1. Connect your Android device via USB
2. Enable USB debugging on your device
3. Make sure your API key is in the `.env` file (OpenAI or OpenRouter)
4. Activate your virtual environment:
   ```
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
5. Run the agent:
   ```
   python android_ai_agent.py
   ```
6. When prompted, select your LLM provider (OpenAI or OpenRouter)

## Task Formats

The Android AI Agent supports both simple and complex tasks:

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

## Search Tasks

The agent has been enhanced to handle search tasks more effectively:

```
search for climate change in chrome
open twitter and search for latest news
find information about quantum computing
```

For search tasks, the agent will:
1. Identify the search field
2. Type the search query
3. Either tap on a search suggestion or press Enter
4. Verify that search results are displayed before marking the task as complete

## Available Actions

The agent can perform the following actions:

- **tap**: Tap at specific coordinates on the screen
- **type**: Input text into a field
- **scroll**: Scroll in a specified direction (up, down, left, right)
- **swipe**: Perform a swipe gesture from one point to another
- **wait**: Wait for a specified amount of time
- **go_home**: Return to the home screen
- **press_back**: Press the back button
- **recent_apps**: Open the recent apps screen
- **press_enter**: Press the Enter key (useful for search submissions)

## How Tasks Are Processed

The agent uses a sophisticated approach:

1. **Task Analysis Phase**:
   - Analyzes your task request
   - Determines if it requires launching an app
   - Identifies any task-specific context (search, email composition, etc.)

2. **Execution Phase**:
   - For simple tasks: Uses direct app launching
   - For complex tasks: Combines direct app launching with vision-guided steps
   - For search tasks: Ensures proper verification of search results

## Task Examples and What Happens

### Example 1: "open twitter"
```
📋 Task Analysis:
  - requires_app: True
  - app: Twitter
  
📱 Launching twitter (com.twitter.android)
✅ Successfully launched twitter
```

### Example 2: "open chrome and search for medicinal properties of marijuana"
```
📋 Task Analysis:
  - requires_app: True
  - app: Chrome
  
📱 Launching chrome (com.android.chrome)
✅ Successfully launched chrome

📱 Iteration 1/15
🔍 Determining next action...
📱 Tapping at coordinates: 540, 200 (50.0%, 12.5%)
⌨️ Typing text: "medicinal properties of marijuana"
⌨️ Pressing Enter key
✅ Task completed: open chrome and search for medicinal properties of marijuana
```

## App-Specific Features

The agent now includes specialized handling for common apps:

### Chrome
- Opening new tabs
- Opening incognito tabs
- Searching for information
- Navigating to URLs

### Gmail
- Composing new emails
- Finding the compose button
- Filling in recipient, subject, and body fields

### Twitter
- Creating new tweets
- Finding the compose tweet button
- Searching for tweets or accounts

## Tips for Best Results

1. **Be Specific**: Clearly state which app you want to use
2. **Use Natural Language**: The agent understands phrases like "open X and do Y"
3. **For Search Tasks**: Include the search query clearly in your request
4. **Watch the Output**: The agent provides detailed progress information
5. **Feedback**: After a task completes, provide feedback on whether it worked

## Troubleshooting

If you encounter issues:

1. **App Not Found**: Make sure the app is installed on your device
2. **Connection Issues**: Verify USB debugging is enabled and authorized
3. **Vision Analysis Failures**: Sometimes retry with clearer instructions
4. **Text Input Problems**: The agent now uses a more reliable method for text input

For more detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Advanced Features

- **Context Awareness**: The vision model is informed about completed steps
- **Adaptive Delays**: Different waits based on action type
- **Error Recovery**: Detects and breaks out of repetitive action loops
- **Task Analysis**: Shows reasoning for each action taken
- **Search Verification**: Ensures search tasks are properly completed with results displayed