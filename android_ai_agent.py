import asyncio
import os
import subprocess
import time
import json
import glob
import base64
from PIL import Image
from io import BytesIO
from openai import OpenAI
from dotenv import load_dotenv
import sys

# Load environment variables from .env file
load_dotenv()

class SimpleAndroidAgent:
    def __init__(self):
        """Initialize the Simple Android Agent."""
        self.adb_path = "adb"  # Assume adb is in PATH
        self.scrcpy_process = None
        self.screenshot_dir = "screenshots"
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.current_app = None
        
        # Ensure screenshot directory exists
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
    def resize_image(self, image_path, max_size=(768, 1024), quality=85):
        """Resize an image to reduce its size for better API processing.
        
        Args:
            image_path (str): Path to the image
            max_size (tuple): Maximum width and height
            quality (int): JPEG quality for saving
            
        Returns:
            str: Base64 encoded string of the resized image
        """
        try:
            with Image.open(image_path) as img:
                # Calculate new dimensions while maintaining aspect ratio
                width, height = img.size
                if width > max_size[0] or height > max_size[1]:
                    ratio = min(max_size[0] / width, max_size[1] / height)
                    new_size = (int(width * ratio), int(height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Convert to RGB if in RGBA mode
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                    
                # Save to BytesIO object
                buffered = BytesIO()
                img.save(buffered, format="JPEG", quality=quality, optimize=True)
                
                # Get base64 encoded string
                img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
                print(f"Resized image from {width}x{height} to {img.size[0]}x{img.size[1]} - Reduced size for API")
                return img_str
        except Exception as e:
            print(f"Error resizing image: {e}")
            # If there's an error, fall back to the original image
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
    
    async def start_scrcpy(self, device_id=None):
        """Start scrcpy with the specified device."""
        # Create a directory for recordings if it doesn't exist
        os.makedirs("recordings", exist_ok=True)
        
        # Use --no-display with recording to a file
        timestamp = int(time.time())
        recording_path = f"recordings/recording_{timestamp}.mp4"
        cmd = ["scrcpy", "--no-display", "--record", recording_path]
        
        if device_id:
            cmd.extend(["-s", device_id])
            
        # Add options for better performance
        cmd.extend(["--max-fps", "15"])  # Lower FPS for performance
        
        try:
            print("Starting scrcpy in background (no display with recording)...")
            self.scrcpy_process = subprocess.Popen(cmd)
            await asyncio.sleep(2)  # Wait for scrcpy to start
            
            # Check if scrcpy process is running
            if self.scrcpy_process.poll() is None:
                print("scrcpy started successfully in background")
                return True
            else:
                print("scrcpy failed to start")
                return False
                
        except Exception as e:
            print(f"Failed to start scrcpy: {e}")
            return False
    
    def stop_scrcpy(self):
        """Stop the scrcpy process."""
        if self.scrcpy_process:
            print("Stopping scrcpy...")
            self.scrcpy_process.terminate()
            self.scrcpy_process = None
    
    async def capture_screen(self):
        """Capture the current screen of the device using ADB."""
        timestamp = int(time.time())
        screenshot_path = f"{self.screenshot_dir}/screenshot_{timestamp}.png"
        
        try:
            # Use ADB to take a screenshot on the device
            adb_cmd = [self.adb_path, "exec-out", "screencap", "-p"]
            
            # Run the command and capture the output
            process = await asyncio.create_subprocess_exec(
                *adb_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                print(f"Error capturing screenshot: {stderr.decode()}")
                return None
            
            # Save the screenshot to a file
            with open(screenshot_path, "wb") as f:
                f.write(stdout)
                
            print(f"Saved screenshot to {screenshot_path}")
            return screenshot_path
            
        except Exception as e:
            print(f"Error capturing screenshot: {e}")
            return None
    
    def cleanup_old_screenshots(self):
        """Remove old screenshots to save space."""
        screenshots = sorted(glob.glob(f"{self.screenshot_dir}/screenshot_*.png"))
        while len(screenshots) > 10:  # Keep only the 10 most recent screenshots
            oldest = screenshots.pop(0)
            os.remove(oldest)
            print(f"Removed old screenshot: {oldest}")
    
    async def extract_text_from_screen(self, screenshot_path):
        """Extract text from screenshot using GPT-4o vision capability."""
        try:
            # Resize and encode image to base64
            base64_image = self.resize_image(screenshot_path)
            
            # Ask GPT-4o to extract text
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract all visible text from this Android screen capture. Return only the text, formatted neatly."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            extracted_text = response.choices[0].message.content
            return extracted_text
        except Exception as e:
            print(f"Error extracting text: {e}")
            return ""
    
    async def analyze_screen_with_llm(self, screenshot_path, question):
        """Use OpenAI's vision model to analyze the screen and answer a question."""
        try:
            # Resize and encode image to base64
            base64_image = self.resize_image(screenshot_path)
            
            # Create message with image and question
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Analyze this Android screen capture and answer: {question}"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            analysis = response.choices[0].message.content
            return analysis
        except Exception as e:
            print(f"Error analyzing screen with LLM: {e}")
            return f"Error analyzing screen: {str(e)}"
    
    async def determine_action(self, task, screenshot_path):
        """Use GPT-4o to determine what action to take based on the task and current screen."""
        try:
            # Resize and encode image to base64
            base64_image = self.resize_image(screenshot_path)
            
            # Create system prompt that instructs GPT-4o on available actions
            system_prompt = """You are an AI assistant controlling an Android device.
Your task is to analyze the screen and determine the next action to take.
You have the following actions available:
1. tap(x_percent, y_percent): Tap on the screen at specified percentages of width and height
2. type(text): Type the specified text
3. scroll(direction): Scroll in the specified direction (up or down)
4. wait(seconds): Wait for the specified number of seconds
5. done: Indicate that the task is complete

Respond with a JSON object that has these fields:
- analysis: Brief description of what you see on the screen
- action: One of ["tap", "type", "scroll", "wait", "done"]
- x_percent: (For tap) X-coordinate as percentage (0-100)
- y_percent: (For tap) Y-coordinate as percentage (0-100)
- text: (For type) Text to type
- direction: (For scroll) Direction to scroll ("up" or "down")
- wait_time: (For wait) Number of seconds to wait
- is_task_complete: boolean - true if the task is complete, false otherwise
- reasoning: Your reasoning for choosing this action

For example: {"analysis": "I see the home screen", "action": "tap", "x_percent": 50, "y_percent": 30, "is_task_complete": false, "reasoning": "Tapping on the app icon"}
"""
            
            # Use GPT-4o to analyze the screen and determine action
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Task: {task}\nAnalyze this Android screen and determine the best next action to complete the task."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=800
            )
            
            action_plan = json.loads(response.choices[0].message.content)
            return action_plan
        except Exception as e:
            print(f"Error determining action: {e}")
            return {
                "analysis": f"Error determining action: {str(e)}",
                "action": "wait",
                "wait_time": 1,
                "is_task_complete": False,
                "reasoning": "Error occurred, waiting before retry"
            }
    
    async def execute_action(self, action):
        """Execute the determined action using ADB commands."""
        action_type = action.get("action", "")
        
        try:
            if action_type == "tap":
                # Get the coordinates as percentages
                x_percent = action.get("x_percent", 50)
                y_percent = action.get("y_percent", 50)
                
                # Get device screen size
                size_output = subprocess.check_output([self.adb_path, "shell", "wm", "size"]).decode()
                width, height = map(int, size_output.split(": ")[1].strip().split("x"))
                
                # Convert percentages to actual coordinates
                x = int(width * x_percent / 100)
                y = int(height * y_percent / 100)
                
                # Execute tap
                subprocess.run([self.adb_path, "shell", "input", "tap", str(x), str(y)])
                print(f"Tapped at coordinates: {x}, {y} (from {x_percent}%, {y_percent}%)")
                return True
                
            elif action_type == "type":
                text = action.get("text", "")
                if text:
                    subprocess.run([self.adb_path, "shell", "input", "text", text])
                    print(f"Typed text: {text}")
                    return True
                return False
                
            elif action_type == "scroll":
                direction = action.get("direction", "down")
                
                # Get device screen size
                size_output = subprocess.check_output([self.adb_path, "shell", "wm", "size"]).decode()
                width, height = map(int, size_output.split(": ")[1].strip().split("x"))
                
                center_x = width // 2
                
                if direction.lower() == "down":
                    # Scroll down by swiping from center-bottom to center-top
                    start_y = int(height * 0.7)
                    end_y = int(height * 0.3)
                else:
                    # Scroll up by swiping from center-top to center-bottom
                    start_y = int(height * 0.3)
                    end_y = int(height * 0.7)
                
                subprocess.run([
                    self.adb_path, "shell", "input", "swipe", 
                    str(center_x), str(start_y), str(center_x), str(end_y)
                ])
                print(f"Scrolled {direction}")
                return True
                
            elif action_type == "wait":
                wait_time = action.get("wait_time", 1)
                print(f"Waiting for {wait_time} seconds")
                await asyncio.sleep(wait_time)
                return True
                
            elif action_type == "done":
                print("Action indicates task is complete")
                return True
            
            else:
                print(f"Unknown action type: {action_type}")
                return False
        
        except Exception as e:
            print(f"Error executing action: {e}")
            return False
            
    async def analyze_screen_context(self, screenshot_path):
        """Use GPT-4o to analyze the current screen context and understand the UI state."""
        try:
            # Resize and encode image to base64
            base64_image = self.resize_image(screenshot_path)
            
            # Ask GPT-4o for context analysis
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": """Analyze this Android screen capture to understand the context.
                            
Please identify:
1. Which app is currently open
2. Which screen or state the app is in
3. Important text or UI elements visible
4. Possible actions from this screen

Return a JSON object with:
{
    "app": "Name of the app that appears to be open",
    "screen": "Specific screen within the app (e.g., 'home', 'compose', 'settings')",
    "key_elements": ["List of important UI elements visible"],
    "possible_actions": ["List of actions that seem possible from this screen"]
}"""},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=800
            )
            
            context = json.loads(response.choices[0].message.content)
            return context
        except Exception as e:
            print(f"Error analyzing screen context: {e}")
            return {
                "app": "unknown",
                "screen": "unknown",
                "key_elements": [],
                "possible_actions": []
            }
    
    async def launch_app(self, app_name):
        """Launch an app on the device using adb."""
        app_mappings = {
            "twitter": "com.twitter.android",
            "x": "com.twitter.android",
            "gmail": "com.google.android.gm",
            "chrome": "com.android.chrome",
            "youtube": "com.google.android.youtube",
            "maps": "com.google.android.apps.maps",
            "photos": "com.google.android.apps.photos",
            "settings": "com.android.settings",
            "zomato": "com.application.zomato",
        }
        
        package_name = app_mappings.get(app_name.lower())
        if not package_name:
            # Try to find the package name by querying installed packages
            try:
                result = subprocess.check_output([self.adb_path, "shell", "pm", "list", "packages"]).decode()
                packages = [line.split(":", 1)[1].strip() for line in result.splitlines()]
                
                # Filter packages that might match the app name
                matches = [pkg for pkg in packages if app_name.lower() in pkg.lower()]
                
                if matches:
                    package_name = matches[0]
                    print(f"Found package for {app_name}: {package_name}")
                else:
                    print(f"Unknown app: {app_name}")
                    return False
            except Exception as e:
                print(f"Error finding package: {e}")
                return False
        
        try:
            print(f"Launching {app_name} ({package_name})")
            subprocess.run([self.adb_path, "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"])
            self.current_app = app_name.lower()
            await asyncio.sleep(3)  # Wait for app to launch
            return True
        except Exception as e:
            print(f"Error launching app: {e}")
            return False
    
    async def analyze_task(self, task):
        """Analyze if the task requires launching an app and which one."""
        try:
            # Use GPT-4 to analyze task requirements
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": """You are an AI assistant that analyzes Android tasks.
Your job is to determine if a task requires launching a specific app, and if so, which one."""},
                    {"role": "user", "content": f"""Analyze this Android task: "{task}"
                    
Does this task require launching a specific app? If so, which app?
Return a JSON object with these fields:
- requires_app_launch: boolean
- app_name: string (empty if no app needed)
- task_after_launch: string (what to do after launching the app)"""}
                ],
                response_format={"type": "json_object"},
                max_tokens=500
            )
            
            analysis = json.loads(response.choices[0].message.content)
            return analysis
        except Exception as e:
            print(f"Error analyzing task: {e}")
            return {
                "requires_app_launch": False,
                "app_name": "",
                "task_after_launch": task
            }
    
    async def run_task(self, task):
        """Run a task on the Android device."""
        print(f"\nStarting task: {task}")
        
        # First, analyze if we need to launch an app
        task_analysis = await self.analyze_task(task)
        
        # Launch app if needed
        if task_analysis.get("requires_app_launch", False):
            app_name = task_analysis.get("app_name", "")
            
            if app_name:
                print(f"Task requires launching {app_name}")
                launch_success = await self.launch_app(app_name)
                if not launch_success:
                    return f"Failed to launch {app_name}"
                task = task_analysis.get("task_after_launch", task)
            
        # Main task execution loop
        max_steps = 20  # Prevent infinite loops
        steps_taken = 0
        task_complete = False
        result = ""
        
        while steps_taken < max_steps and not task_complete:
            # Take a screenshot
            screenshot_path = await self.capture_screen()
            if not screenshot_path:
                return "Failed to capture screen"
            
            print(f"Captured screenshot: {screenshot_path}")
            
            # Determine next action
            action = await self.determine_action(task, screenshot_path)
            print(f"\nAnalysis: {action.get('analysis', 'No analysis provided')}")
            print(f"Action: {action.get('action', 'unknown')} - {action.get('reasoning', 'No reasoning provided')}")
            
            # Execute the action
            success = await self.execute_action(action)
            if not success:
                print("Failed to execute action")
            
            # Check if the task is complete
            task_complete = action.get("is_task_complete", False)
            if task_complete:
                result = action.get("analysis", "Task completed")
                print(f"Task complete: {result}")
            
            steps_taken += 1
            if steps_taken >= max_steps:
                print("Reached maximum number of steps")
                result = "Task not completed within the maximum number of steps"
            
            # Wait a bit between actions
            await asyncio.sleep(1)
        
        self.cleanup_old_screenshots()
        return result
    
    async def interactive_session(self):
        """Run an interactive session with the Android agent."""
        print("\n===== Simple Android Agent =====")
        print("Type 'exit' to end the session")
        print("Type 'context' to analyze the current screen context")
        print("Type 'help' for more commands")
        
        try:
            # Start scrcpy in background mode
            await self.start_scrcpy()
            
            # Main interaction loop
            while True:
                user_input = input("\nEnter task (or command): ")
                
                if user_input.lower() in ["exit", "quit", "bye"]:
                    break
                    
                elif user_input.lower() == "help":
                    print("\nAvailable commands:")
                    print("  exit - End the session")
                    print("  context - Analyze the current screen")
                    print("  screenshot - Take a screenshot")
                    print("  launch [app] - Launch an app")
                    print("  Any other input will be treated as a task to execute")
                    continue
                    
                elif user_input.lower() == "context":
                    # Take a screenshot
                    screenshot_path = await self.capture_screen()
                    
                    if screenshot_path and os.path.exists(screenshot_path):
                        print("Analyzing current screen context...")
                        context = await self.analyze_screen_context(screenshot_path)
                        print("\n📱 Screen Context Analysis:")
                        print(f"App: {context.get('app', 'Unknown')}")
                        print(f"Screen: {context.get('screen', 'Unknown')}")
                        print("\nKey Elements:")
                        for element in context.get('key_elements', []):
                            print(f"  - {element}")
                        print("\nPossible Actions:")
                        for action in context.get('possible_actions', []):
                            print(f"  - {action}")
                    else:
                        print("Failed to take screenshot for context analysis")
                    continue
                    
                elif user_input.lower().startswith("screenshot"):
                    screenshot_path = await self.capture_screen()
                    
                    if screenshot_path and os.path.exists(screenshot_path):
                        print(f"Screenshot taken: {screenshot_path}")
                    else:
                        print("Failed to take screenshot")
                    continue
                    
                elif user_input.lower().startswith("launch "):
                    app_name = user_input[7:].strip()
                    success = await self.launch_app(app_name)
                    if success:
                        print(f"Successfully launched {app_name}")
                    else:
                        print(f"Failed to launch {app_name}")
                    continue
                
                # Treat as a task to execute
                print(f"\n🤖 Working on: {user_input}...")
                result = await self.run_task(user_input)
                
                print("\n✅ Task completed!")
                print(f"Result: {result}")
                
                feedback = input("\nDid that work as expected? (y/n): ")
                if feedback.lower() == "n":
                    print("Sorry about that. I'll try to do better next time.")
                    print("You can type 'context' to analyze the current screen state.")
        
        except KeyboardInterrupt:
            print("\nSession interrupted.")
        finally:
            self.stop_scrcpy()
            print("Session ended.")

async def main():
    # Check for required API keys
    missing_keys = []
    if "OPENAI_API_KEY" not in os.environ:
        missing_keys.append("OPENAI_API_KEY")
    
    if missing_keys:
        print("Error: The following environment variables are missing:")
        for key in missing_keys:
            print(f"  - {key}")
        print("\nPlease set these variables in your environment or in a .env file.")
        return
    
    # Check for required dependencies
    try:
        # Check for PIL
        from PIL import Image
        print("PIL/Pillow library found.")
    except ImportError:
        print("Error: The PIL/Pillow library is required but not installed.")
        print("Please install it with: pip install Pillow")
        choice = input("Would you like to install it now? (y/n): ")
        if choice.lower() == 'y':
            subprocess.call([sys.executable, "-m", "pip", "install", "Pillow"])
            print("Pillow installed. Please restart the script.")
        return
    
    # Check for ADB
    try:
        subprocess.run(["adb", "version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("ADB found and working.")
    except FileNotFoundError:
        print("Error: ADB not found in PATH. Please install Android Debug Bridge.")
        return
    
    # Check for connected devices
    result = subprocess.run(["adb", "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if "device" not in result.stdout or result.stdout.count("\n") < 3:  # Header line + at least one device + empty line
        print("Error: No Android devices connected. Please connect a device and enable USB debugging.")
        return
    
    print("\nAll dependencies and requirements verified!")
    print("Starting the Simple Android Agent...\n")
    
    agent = SimpleAndroidAgent()
    await agent.interactive_session()

if __name__ == "__main__":
    asyncio.run(main())