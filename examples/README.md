# Android Vision Agent Examples

This directory contains example scripts and use cases for the Android Vision Agent.

## Example Tasks

Here are some example tasks you can try with the Android Vision Agent:

### Basic Navigation

- "Open Settings and turn on Wi-Fi"
- "Open Chrome and go to google.com"
- "Open Calculator and perform a calculation"

### Social Media

- "Open Twitter and check trending topics"
- "Open Instagram and view my profile"
- "Open Facebook and check notifications"

### Productivity

- "Open Gmail and check my inbox"
- "Open Calendar and create a new event"
- "Open Notes and create a new note"

### Entertainment

- "Open YouTube and search for music videos"
- "Open Spotify and play my favorite playlist"
- "Open Netflix and continue watching my show"

### Shopping

- "Open Amazon and search for headphones"
- "Open Zomato and order food"
- "Open Uber and book a ride"

## Running Examples

You can run examples using the main script:

```bash
python android_vision_agent.py
```

Or use the provided shell script:
```bash
chmod +x run.sh  # Make it executable first time
./run.sh
```

When prompted, enter one of the example tasks above.

Alternatively, you can use the example script to directly run a task:

```bash
python examples/run_example.py "open chrome and search for AI news"
```

## Creating Your Own Examples

Feel free to create your own examples and share them with the community. The vision-based approach allows the agent to work with virtually any app without requiring app-specific code.