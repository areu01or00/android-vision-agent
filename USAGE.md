# Android Vision Agent Usage Guide

This guide shows you how to use the improved Android Vision Agent with its LLM-based task planning and XML-based UI automation.

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
   python android_vision_agent.py
   ```
   
   Or use the provided shell script:
   ```
   chmod +x run.sh  # Make it executable first time
   ./run.sh
   ```

## Task Formats

The Android Vision Agent now supports both simple and complex tasks:

### Simple App Launch
```
open twitter
launch chrome
start gmail
```
These are executed directly without UI analysis.

### Complex Multi-Step Tasks
```
open twitter and search for AI news
open chrome and search for medicinal properties of marijuana
open gmail and compose an email to example@gmail.com
```
These are broken down into stages:
1. Direct app launch
2. XML-based UI guidance for the remaining steps

## How Tasks Are Processed

The agent now uses a two-phase approach:

1. **Planning Phase** (Using GPT-3.5-Turbo):
   - Analyzes your task request
   - Determines if it can be directly executed
   - Breaks it down into stages
   - Passes context between stages

2. **Execution Phase**:
   - For simple tasks: Uses direct app launching
   - For complex tasks: 
     - Launches the app directly
     - Gets UI XML hierarchy data from the device
     - Uses LLM to identify which elements to interact with
     - Precisely targets UI elements by ID, text, or description
     - Handles form inputs, buttons, and navigation with element precision

## Advantages of the XML-Based Approach

The new XML-based approach provides several key benefits:

1. **Precise Element Targeting**: Instead of guessing screen coordinates, the agent targets exact UI elements by:
   - ResourceID (most precise)
   - Text content
   - Content description
   - Class and index

2. **More Reliable Interactions**: The agent clicks exactly what you want it to click, not just coordinates

3. **Better Form Handling**: Proper text entry into the right fields, with automatic field clearing

4. **Faster Execution**: No need to process images, just XML text analysis

5. **More Adaptable**: Works across different screen sizes and densities

## Task Examples and What Happens

### Example 1: "open twitter"
```
📋 Task Plan:
  - has_app_launch: True
  - app_name: Twitter
  - requires_ui_analysis_after_launch: False
  
📱 Stage 1: Launching app directly (com.twitter.android)
✅ Successfully launched app (com.twitter.android)
```

### Example 2: "open chrome and search for medicinal properties of marijuana"
```
📋 Task Plan:
  - has_app_launch: True
  - app_name: Chrome
  - requires_ui_analysis_after_launch: True
  - post_launch_steps: Search for 'medicinal properties of marijuana' in the Chrome browser

📱 Stage 1: Launching chrome (com.android.chrome) directly
✅ Successfully launched chrome
🤖 Stage 2: Using XML + LLM for task execution

Step 1: Getting UI hierarchy...
Analyzing UI with LLM...
UI Analysis: {
  "current_screen": "Chrome Home Screen",
  "action": {
    "type": "click_element",
    "target": {
      "method": "resourceId",
      "value": "com.android.chrome:id/search_box_text"
    }
  },
  "reasoning": "The search box is visible at the top of the Chrome home screen. Clicking it will allow us to enter the search query.",
  "is_task_complete": false
}
Current screen: Chrome Home Screen
Executing action: click_element
Reasoning: The search box is visible at the top of the Chrome home screen. Clicking it will allow us to enter the search query.
Clicking element: resourceId='com.android.chrome:id/search_box_text'
```

## Tips for Best Results

1. **Be Specific**: Clearly state which app you want to use
2. **Use Natural Language**: The agent understands phrases like "open X and do Y"
3. **Watch the Output**: The agent now provides detailed progress information
4. **Feedback**: After a task completes, provide feedback on whether it worked

## Troubleshooting

If you encounter issues:

1. **App Not Found**: Make sure the app is installed on your device
2. **Connection Issues**: Verify USB debugging is enabled and authorized
3. **Element Not Found**: Some apps may not expose proper element IDs or have dynamically generated IDs
4. **Text Input Problems**: Some secure fields may be restricted

## Advanced Features

- **Context Awareness**: The LLM is informed about completed steps
- **Element Fallbacks**: If an element can't be found by ID, falls back to text or description
- **Error Recovery**: More robust handling of elements that can't be found
- **Task Analysis**: Shows reasoning for each action taken