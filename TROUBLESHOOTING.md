# Troubleshooting Android AI Agent

This guide addresses common issues you might encounter when using the Android AI Agent and provides solutions to help you resolve them.

## Connection Issues

### ADB Device Not Found

**Problem**: The agent cannot find or connect to your Android device.

**Solutions**:
1. Ensure your Android device is connected via USB.
2. Check that USB debugging is enabled in Developer Options.
3. Run `adb devices` to verify your device is recognized.
4. Try a different USB cable or port.
5. Restart the ADB server:
   ```
   adb kill-server
   adb start-server
   ```
6. On your Android device, revoke and re-authorize USB debugging permissions.

### Multiple Devices Connected

**Problem**: Multiple Android devices are connected, and ADB doesn't know which one to use.

**Solution**:
1. Run `adb devices` to see all connected devices.
2. Create or edit the `.env` file to specify the device serial:
   ```
   ANDROID_DEVICE_SERIAL=your_device_serial_here
   ```
3. Alternatively, disconnect the devices you're not using.

## Authentication Problems

### API Key Issues

**Problem**: The agent fails due to authentication errors with the API (OpenAI or OpenRouter).

**Solutions**:
1. Verify your API key is correct in the `.env` file.
2. Ensure your account has access to the required models (GPT-4o for OpenAI).
3. Check your account has sufficient credits.
4. Test your API key with a simple API call:
   ```python
   import openai
   client = openai.OpenAI(api_key="your_api_key_here")
   response = client.chat.completions.create(
       model="gpt-4o", 
       messages=[{"role": "user", "content": "Hello"}]
   )
   print(response)
   ```

## App-Specific Issues

### App Authentication

**Problem**: The agent can't get past login screens in apps.

**Solutions**:
1. Log into the app manually before using the agent.
2. For apps with biometric authentication, be ready to authenticate manually when prompted.
3. For apps with CAPTCHA, complete that step manually before continuing.

### App Not Found

**Problem**: The agent can't find or open a specific app.

**Solutions**:
1. Verify the app is installed on your device.
2. Check the exact name of the app as it appears on your home screen.
3. Try opening the app manually, then using the agent for further actions.

## Interaction Issues

### Clicks Not Working

**Problem**: The agent attempts to click elements but nothing happens.

**Solutions**:
1. Ensure the UI element is actually visible and clickable.
2. Try increasing wait times between actions by modifying `DEFAULT_WAIT_TIME` in the code.
3. Restart the app and try again with a simpler command.
4. Check the screenshot to see if the UI element is being correctly identified.

### Text Input Problems

**Problem**: The agent can't input text correctly.

**Solutions**:
1. Ensure the keyboard is showing on the screen.
2. The agent now uses a more reliable text input method that avoids shell interpretation issues.
3. If you're still experiencing issues, try breaking complex text into shorter segments.
4. For special characters, the agent now handles escaping automatically.

### Search Tasks Not Completing

**Problem**: The agent types a search query but doesn't complete the search.

**Solutions**:
1. The agent now verifies search results are displayed before marking a task as complete.
2. If the search isn't completing, try specifying the search query more clearly in your task.
3. Check if the app's search interface has changed or requires a specific interaction pattern.
4. The agent now includes a `press_enter` action specifically for completing searches.

## Vision Model Issues

### Vision Model Not Available

**Problem**: The agent can't access the vision model (GPT-4o or equivalent).

**Solutions**:
1. Verify your account has access to the required vision model.
2. Check if your API key has the necessary permissions.
3. Look for any errors related to model availability in the logs.
4. Try switching to a different LLM provider if available.

### Poor Vision Analysis

**Problem**: The agent misinterprets what's on the screen.

**Solutions**:
1. Ensure your Android device screen is clear and visible.
2. Try with apps that have more standard UI elements.
3. Use more specific commands to guide the agent.
4. Break complex tasks into smaller steps.

## General Problems

### Agent Seems Stuck

**Problem**: The agent appears to be stuck or unresponsive.

**Solutions**:
1. Press Ctrl+C to stop the current process.
2. Restart the agent with `python android_ai_agent.py`.
3. The agent now has improved detection for repetitive actions and will suggest alternative approaches.
4. Check the device screen to see what's happening.

### High API Costs

**Problem**: Using the agent is consuming a lot of API credits.

**Solutions**:
1. Use more specific commands to reduce the number of vision analyses needed.
2. Break complex tasks into smaller, direct commands.
3. Modify the code to reduce the frequency of screenshots or vision analysis.
4. Consider using a more cost-effective LLM provider.

## Getting Help

If you're still experiencing issues:

1. Run the agent with debug logging enabled
2. Check the logs for specific error messages.
3. Open an issue on GitHub with:
   - A clear description of the problem
   - Steps to reproduce the issue
   - Screenshots of the Android screen (if relevant)
   - The command you tried to run
   - The error message or unexpected behavior

## Advanced Troubleshooting

### Modifying Wait Times

If the agent is moving too quickly or too slowly:

```python
# In android_ai_agent.py
DEFAULT_WAIT_TIME = 2.0  # Increase or decrease as needed
```

### Customizing System Prompts

If you want to modify how the agent handles specific tasks, you can edit the system prompts:

```python
# In android_ai_agent.py
system_prompt = """
# Android AI Agent System

You are an AI assistant that helps users control their Android device...
"""
```

### Debugging Search Task Verification

If search tasks aren't being properly verified:

1. Check the `verify_search_results` method in the code
2. Look for the search query in the screen text output
3. Verify that the agent is correctly identifying search result indicators
4. Ensure the agent is pressing Enter or tapping a search suggestion after typing