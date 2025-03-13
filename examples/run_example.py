#!/usr/bin/env python3
"""
Example script to run the Android Vision Agent with a specific task.
"""

import asyncio
import sys
import os

# Add parent directory to path to import the AndroidVisionAgent class
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from android_vision_agent import AndroidVisionAgent

async def run_example(task):
    """Run the Android Vision Agent with a specific task."""
    agent = AndroidVisionAgent()
    
    # Connect to the device
    if not await agent.connect_device():
        print("Failed to connect to device")
        return False
        
    # Get device information
    print(f"Connected to device with screen size: {agent.width}x{agent.height}")
    
    # Execute the task
    try:
        await agent.run_task(task)
    except Exception as e:
        print(f"Error executing task: {e}")
    finally:
        # Clean up
        print("Example completed")

if __name__ == "__main__":
    # Check if a task was provided
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        # Default task
        task = "Open Settings and go to Wi-Fi settings"
        
    print(f"Running example task: {task}")
    asyncio.run(run_example(task))