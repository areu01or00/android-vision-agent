#!/usr/bin/env python3
"""
Example script to run the Android AI Agent with a specific task.
"""

import asyncio
import sys
import os

# Add parent directory to path to import the AndroidAIAgent class
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from android_ai_agent import AndroidAIAgent

async def run_example(task):
    """Run the Android AI Agent with a specific task."""
    agent = AndroidAIAgent()
    
    # Connect to the device
    if not await agent.connect_device():
        print("Failed to connect to device")
        return False
        
    # Initialize the AI agent
    if not await agent.initialize():
        print("Failed to initialize AI agent")
        return False
        
    # Start scrcpy
    try:
        await agent.start_scrcpy()
    except Exception as e:
        print(f"Failed to start scrcpy: {e}")
        print("Continuing without screen mirroring")
    
    # Execute the task
    try:
        await agent.execute_task(task)
    except Exception as e:
        print(f"Error executing task: {e}")
    finally:
        # Clean up
        agent.stop_scrcpy()
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