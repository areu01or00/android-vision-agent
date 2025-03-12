import asyncio
import os
import subprocess
import time
import json
from typing import Dict, Any, List, Callable
import uiautomator2 as u2
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv
import base64
import logging
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class AndroidAIAgent:
    def __init__(self, model="gpt-4o"):
        """Initialize the Android AI Agent with the specified OpenAI model."""
        self.model = model
        self.scrcpy_process = None
        self.device = None
        self.llm = None
        self.vision_model = None
        self.screenshot_dir = "screenshots"
        
        # Create screenshots directory if it doesn't exist
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
    async def initialize(self):
        """Initialize the AI agent, including vision capabilities."""
        # Set up vision model
        try:
            self.vision_model = ChatOpenAI(model=self.model)
            if self.vision_model:
                logger.info("Successfully initialized GPT-4o vision capabilities")
                # Use the vision model as our main LLM
                self.llm = self.vision_model
            else:
                logger.warning("Vision capabilities not available, fallback to text-only mode")
                # Initialize with standard GPT model
                self.llm = ChatOpenAI(model="gpt-3.5-turbo")
        except Exception as e:
            logger.error(f"Error initializing vision: {e}")
            # Try to initialize with standard model
            try:
                self.llm = ChatOpenAI(model="gpt-3.5-turbo")
                logger.info(f"Initialized text-only LLM: gpt-3.5-turbo")
            except Exception as e2:
                logger.error(f"Error initializing LLM: {e2}")
            
        return True
    
    async def connect_device(self):
        """Connect to the Android device."""
        try:
            # Connect to the device
            self.device = u2.connect()
            
            # Try to get window size as a simple test of connectivity
            try:
                width, height = self.device.window_size()
                logger.info(f"Connected successfully. Screen size: {width}x{height}")
                
                # Now carefully try to get device info
                try:
                    model = self.device.device_info.get('model', 'Unknown model')
                    version = self.device.device_info.get('version', 'Unknown version')
                    logger.info(f"Device: {model}, Android version: {version}")
                except:
                    logger.warning("Connected to device but couldn't retrieve full device info")
                
                return True
            except Exception as inner_e:
                logger.error(f"Connection test failed: {inner_e}")
                raise inner_e
                
        except Exception as e:
            logger.error(f"Error connecting to device: {e}")
            return False
        
    async def start_scrcpy(self):
        """Start scrcpy to mirror the Android screen."""
        logger.info("Starting scrcpy...")
        # Start scrcpy in a separate process
        cmd = ["scrcpy", "--window-title", "Android-AI-Control", "--window-width", "480", "--window-height", "900"]
        self.scrcpy_process = subprocess.Popen(cmd)
        
        # Wait a bit for scrcpy to start
        await asyncio.sleep(3)
        
        # Check if scrcpy is running
        if self.scrcpy_process.poll() is not None:
            raise Exception("Failed to start scrcpy. Make sure your device is connected and USB debugging is enabled.")
        
        logger.info("scrcpy started successfully")
        return True
    
    def stop_scrcpy(self):
        """Stop the scrcpy process."""
        if self.scrcpy_process:
            logger.info("Stopping scrcpy...")
            self.scrcpy_process.terminate()
            self.scrcpy_process.wait()
            self.scrcpy_process = None
            logger.info("scrcpy stopped")
    
    async def take_screenshot(self):
        """Take a screenshot and save it to the screenshots directory."""
        timestamp = int(time.time())
        filename = f"{self.screenshot_dir}/screenshot_{timestamp}.png"
        self.device.screenshot(filename)
        logger.info(f"Screenshot saved to {filename}")
        return filename
    
    async def analyze_screen_with_vision(self, screenshot_path, task_context=None):
        """Use GPT-4o vision to analyze the screen and suggest actions."""
        if not self.vision_model:
            logger.error("Vision model not available")
            return None
            
        # Read the image file and encode it as base64
        with open(screenshot_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Create the prompt with the image
        system_prompt = """
        You are an AI assistant that helps control an Android device by analyzing screenshots.
        
        When shown a screenshot of an Android app:
        1. Identify what app is open and what screen is shown
        2. Identify key UI elements (buttons, text fields, etc.)
        3. Suggest the next action to take based on the user's goal
        
        Provide your response in JSON format with these fields:
        - screen_analysis: Brief description of what's on screen
        - ui_elements: List of key interactive elements with their approximate positions
        - recommended_action: The specific action to take next (click, type, scroll, etc.)
        - action_params: Parameters for the action (coordinates, text to type, etc.)
        """
        
        user_prompt = f"""
        Here's a screenshot of an Android device.
        
        {f'Context: I want to {task_context}' if task_context else 'Please analyze what is on screen and suggest what to do next.'}
        
        Analyze the screen and tell me:
        1. What app and screen is shown
        2. What UI elements are visible and interactive
        3. What action I should take next to accomplish my goal
        
        For positions, use percentages of screen width/height (e.g., x_percent: 50, y_percent: 70).
        
        Format your response as JSON.
        """
        
        # Create the message with the image
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=[
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
            ])
        ]
        
        try:
            # Get the response from the vision model
            response = await self.vision_model.ainvoke(messages)
            
            # Try to parse the JSON from the response
            content = response.content
            
            # Extract JSON from the response
            try:
                # Try direct JSON parsing
                analysis = json.loads(content)
                return analysis
            except json.JSONDecodeError:
                # If direct parsing fails, try to extract JSON from the text
                try:
                    # Look for JSON between ``` markers
                    if "```json" in content:
                        json_str = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        json_str = content.split("```")[1].strip()
                    else:
                        # Try to find JSON objects
                        import re
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                        else:
                            logger.error("Could not extract JSON from response")
                            return None
                            
                    analysis = json.loads(json_str)
                    return analysis
                except Exception as e:
                    logger.error(f"Error extracting JSON from response: {e}")
                    return None
        except Exception as e:
            logger.error(f"Error analyzing screen with vision: {e}")
            return None
    
    async def execute_action(self, action, params):
        """Execute an action based on the vision model's recommendation."""
        logger.info(f"Executing action: {action} with params: {params}")
        
        if action == "click":
            # Get screen dimensions
            width, height = self.device.window_size()
            
            # Calculate absolute coordinates from percentages
            x_percent = params.get("x_percent", 50)
            y_percent = params.get("y_percent", 50)
            x = int(width * (x_percent / 100))
            y = int(height * (y_percent / 100))
            
            # Click at the specified position
            self.device.click(x, y)
            logger.info(f"Clicked at position ({x}, {y})")
            
        elif action == "input_text":
            text = params.get("text", "")
            if text:
                self.device.send_keys(text)
                logger.info(f"Input text: {text}")
                
        elif action == "scroll":
            direction = params.get("direction", "down")
            if direction == "down":
                self.device.swipe(0.5, 0.7, 0.5, 0.3)
            elif direction == "up":
                self.device.swipe(0.5, 0.3, 0.5, 0.7)
            elif direction == "left":
                self.device.swipe(0.7, 0.5, 0.3, 0.5)
            elif direction == "right":
                self.device.swipe(0.3, 0.5, 0.7, 0.5)
            logger.info(f"Scrolled {direction}")
            
        elif action == "wait":
            seconds = params.get("seconds", 2)
            logger.info(f"Waiting for {seconds} seconds")
            await asyncio.sleep(seconds)
            
        elif action == "back":
            self.device.press("back")
            logger.info("Pressed back button")
            
        elif action == "home":
            self.device.press("home")
            logger.info("Pressed home button")
            
        elif action == "open_app":
            app_name = params.get("app_name", "")
            if app_name:
                self.device.app_start(app_name)
                logger.info(f"Opened app: {app_name}")
                
        else:
            logger.warning(f"Unknown action: {action}")
    
    async def run_ai_agent(self):
        """Main method to run the AI agent."""
        # Connect to the device
        if not await self.connect_device():
            logger.error("Failed to connect to device")
            return False
            
        # Initialize the AI agent
        if not await self.initialize():
            logger.error("Failed to initialize AI agent")
            return False
            
        # Start scrcpy
        try:
            await self.start_scrcpy()
        except Exception as e:
            logger.warning(f"Failed to start scrcpy: {e}")
            logger.info("Continuing without screen mirroring")
        
        # Main interaction loop
        try:
            # Ask the user for a task
            task = input("Enter a task to perform (e.g., 'Open Twitter and search for news'): ")
            
            # Execute the task using vision-guided approach
            await self.execute_task(task)
                
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            # Clean up
            self.stop_scrcpy()
            logger.info("AI agent stopped")
    
    async def execute_task(self, task):
        """Execute a task using vision-guided approach."""
        logger.info(f"Executing task: {task}")
        
        # First, go to home screen
        self.device.press("home")
        await asyncio.sleep(1)
        
        # Take a screenshot
        screenshot_path = await self.take_screenshot()
        
        # Analyze the screen with vision
        analysis = await self.analyze_screen_with_vision(screenshot_path, task)
        
        if not analysis:
            logger.error("Failed to analyze screen")
            return
            
        # Log the analysis
        logger.info(f"Screen analysis: {analysis.get('screen_analysis', 'No analysis')}")
        
        # Execute the recommended action
        action = analysis.get("recommended_action")
        params = analysis.get("action_params", {})
        
        if action:
            await self.execute_action(action, params)
            await asyncio.sleep(2)  # Wait for the action to take effect
            
            # Continue with follow-up actions if needed
            max_steps = 10
            current_step = 1
            
            while current_step < max_steps:
                # Take another screenshot
                screenshot_path = await self.take_screenshot()
                
                # Analyze the screen again
                analysis = await self.analyze_screen_with_vision(screenshot_path, task)
                
                if not analysis:
                    logger.error("Failed to analyze screen")
                    break
                    
                # Log the analysis
                logger.info(f"Step {current_step} - Screen analysis: {analysis.get('screen_analysis', 'No analysis')}")
                
                # Check if the task is complete
                if "task complete" in analysis.get('screen_analysis', '').lower():
                    logger.info("Task completed successfully")
                    break
                    
                # Execute the next recommended action
                action = analysis.get("recommended_action")
                params = analysis.get("action_params", {})
                
                if action:
                    await self.execute_action(action, params)
                    await asyncio.sleep(2)  # Wait for the action to take effect
                else:
                    logger.warning("No recommended action")
                    break
                    
                current_step += 1
                
            if current_step >= max_steps:
                logger.warning("Reached maximum number of steps")
        else:
            logger.warning("No recommended action")

async def main():
    agent = AndroidAIAgent()
    await agent.run_ai_agent()

if __name__ == "__main__":
    asyncio.run(main())