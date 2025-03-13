import asyncio
import os
import subprocess
import time
import json
import re
import uiautomator2 as u2
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class AndroidVisionAgent:
    def __init__(self):
        """Initialize the Android Vision Agent."""
        self.device = None
        self.scrcpy_process = None
        self.openai_client = OpenAI()
        self.last_action_time = 0
        self.action_count = 0
        self.width = 0
        self.height = 0
        
        # Common package names for direct app launching
        self.common_packages = {
            # Social media
            "twitter": "com.twitter.android",
            "x": "com.twitter.android",
            "instagram": "com.instagram.android",
            "facebook": "com.facebook.katana",
            "messenger": "com.facebook.orca",
            "whatsapp": "com.whatsapp",
            "telegram": "org.telegram.messenger",
            "snapchat": "com.snapchat.android",
            "tiktok": "com.zhiliaoapp.musically",
            "linkedin": "com.linkedin.android",
            "pinterest": "com.pinterest",
            "reddit": "com.reddit.frontpage",
            
            # Google apps
            "gmail": "com.google.android.gm",
            "chrome": "com.android.chrome",
            "youtube": "com.google.android.youtube",
            "maps": "com.google.android.apps.maps",
            "google maps": "com.google.android.apps.maps",
            "photos": "com.google.android.apps.photos",
            "drive": "com.google.android.apps.docs",
            "google drive": "com.google.android.apps.docs",
            "play store": "com.android.vending",
            "google play": "com.android.vending",
            "meet": "com.google.android.apps.meetings",
            "google meet": "com.google.android.apps.meetings",
            
            # System apps
            "messages": "com.google.android.apps.messaging",
            "phone": "com.android.dialer",
            "dialer": "com.android.dialer",
            "contacts": "com.android.contacts",
            "settings": "com.android.settings",
            "calendar": "com.google.android.calendar",
            "camera": "com.android.camera",
            "calculator": "com.android.calculator2",
            "clock": "com.android.deskclock",
            "files": "com.android.documentsui",
            
            # Other popular apps
            "spotify": "com.spotify.music",
            "netflix": "com.netflix.mediaclient",
            "amazon": "com.amazon.mShop.android.shopping",
            "uber": "com.ubercab",
            "lyft": "me.lyft.android",
            "microsoft teams": "com.microsoft.teams",
            "teams": "com.microsoft.teams",
            "zoom": "us.zoom.videomeetings",
            "outlook": "com.microsoft.office.outlook",
            "slack": "com.slack"
        }
    
    async def connect_device(self):
        """Connect to an Android device."""
        try:
            # Try to get devices from adb
            result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            if len(lines) <= 1:
                print("No devices found. Make sure your device is connected and USB debugging is enabled.")
                return False
                
            # Extract device ID from the first connected device
            device_id = lines[1].split('\t')[0]
            print(f"Attempting to connect to device: {device_id}")
            
            # Connect to the device
            self.device = u2.connect(device_id)
            
            # Verify connection by checking if we can get window size
            try:
                self.width, self.height = self.device.window_size()
                print(f"Connected successfully. Screen size: {self.width}x{self.height}")
                
                # Try to get device info safely
                device_info = {}
                try:
                    device_info = self.device.info
                except:
                    # If info fails, try to get some basic info
                    try:
                        brand = self.device.shell("getprop ro.product.brand").strip()
                        model = self.device.shell("getprop ro.product.model").strip()
                        android_ver = self.device.shell("getprop ro.build.version.release").strip()
                        device_info = {"brand": brand, "model": model, "version": android_ver}
                    except:
                        pass
                
                if device_info:
                    print(f"Device: {device_info.get('brand', 'Unknown')} {device_info.get('model', 'Device')}, " +
                          f"Android version: {device_info.get('version', 'Unknown')}")
                    
                return True
            except Exception as inner_e:
                print(f"Connection error: {inner_e}")
                return False
                
        except Exception as e:
            print(f"Error connecting to device: {e}")
            return False
    
    async def start_scrcpy(self):
        """Start scrcpy for screen mirroring."""
        try:
            print("Starting scrcpy...")
            # Use basic command without options that might not be supported
            cmd = "scrcpy"
            self.scrcpy_process = subprocess.Popen(cmd, shell=True)
            await asyncio.sleep(2)
            if self.scrcpy_process.poll() is None:
                print("scrcpy started successfully")
                return True
            else:
                print("Failed to start scrcpy. Check if scrcpy is installed correctly.")
                return False
        except Exception as e:
            print(f"Error starting scrcpy: {e}")
            return False
    
    def stop_scrcpy(self):
        """Stop the scrcpy process."""
        if self.scrcpy_process:
            print("Stopping scrcpy...")
            self.scrcpy_process.terminate()
            self.scrcpy_process = None
    
    def parse_task(self, task):
        """Parse the user's task and determine if it can be handled directly."""
        task_lower = task.lower().strip()
        
        # Check for direct app opening first
        for app_name in self.common_packages:
            if f"open {app_name}" in task_lower or f"launch {app_name}" in task_lower or f"start {app_name}" in task_lower:
                # Check if this is a complex task with more actions
                if " and " in task_lower or " then " in task_lower:
                    # Complex task that needs XML analysis
                    continue
                
                # Simple app launch - return the package name directly
                return self.common_packages[app_name]
        
        # Also handle "open app X" pattern
        for pattern in [r'open (?:the )?(?:app )?(\\w+)', r'launch (?:the )?(?:app )?(\\w+)', r'start (?:the )?(?:app )?(\\w+)']:
            match = re.search(pattern, task_lower)
            if match:
                app_name = match.group(1).strip()
                if app_name in self.common_packages:
                    return self.common_packages[app_name]
        
        # If we get here, this requires XML analysis
        return None

    def get_ui_hierarchy_xml(self):
        """Get complete XML representation of current UI."""
        try:
            # Dump UI hierarchy to device
            subprocess.run(["adb", "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], 
                           capture_output=True, text=True)
            
            # Retrieve the file content
            result = subprocess.run(["adb", "shell", "cat", "/sdcard/window_dump.xml"],
                                   capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Error getting UI hierarchy: {result.stderr}")
                return None
                
            return result.stdout
        except Exception as e:
            print(f"Error getting UI hierarchy: {e}")
            return None
    
    def extract_ui_metadata(self, xml_content):
        """Extract metadata about the UI from XML for better LLM understanding."""
        try:
            # Parse the XML
            soup = BeautifulSoup(xml_content, 'lxml-xml')
            
            # Find package name (likely the current app)
            current_app = soup.find('node').get('package', 'unknown') if soup.find('node') else 'unknown'
            
            # Simplify package name
            current_app_name = current_app.split('.')[-1] if '.' in current_app else current_app
            for friendly_name, package in self.common_packages.items():
                if package == current_app:
                    current_app_name = friendly_name
                    break
            
            # Count elements by type
            text_elements = len(soup.find_all('node', {'class': lambda x: x and 'TextView' in x}))
            buttons = len(soup.find_all('node', {'class': lambda x: x and 'Button' in x}))
            edit_texts = len(soup.find_all('node', {'class': lambda x: x and 'EditText' in x}))
            
            # Get screen dimensions
            root_node = soup.find('node')
            if root_node:
                bounds = root_node.get('bounds', '[0,0][0,0]')
                width, height = 0, 0
                # Parse bounds which are in format [left,top][right,bottom]
                match = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if match:
                    width = int(match.group(3))
                    height = int(match.group(4))
            
            metadata = {
                "current_app": current_app,
                "current_app_name": current_app_name,
                "element_counts": {
                    "text_elements": text_elements,
                    "buttons": buttons,
                    "edit_texts": edit_texts
                },
                "screen_dimensions": {
                    "width": width,
                    "height": height
                }
            }
            
            return metadata
        except Exception as e:
            print(f"Error extracting UI metadata: {e}")
            return {
                "current_app": "unknown",
                "current_app_name": "unknown",
                "element_counts": {},
                "screen_dimensions": {"width": 0, "height": 0}
            }
    
    async def analyze_ui_with_llm(self, xml_content, task, context=None):
        """Have LLM analyze XML hierarchy and determine next action."""
        if not xml_content:
            print("No XML content to analyze")
            return None
        
        try:
            # Extract metadata to help the LLM understand the UI
            metadata = self.extract_ui_metadata(xml_content)
            
            # Create context description for the LLM
            context_info = ""
            if context and context.get("previous_actions"):
                context_info += "PREVIOUS ACTIONS:\n"
                for i, action in enumerate(context["previous_actions"]):
                    context_info += f"{i+1}. {action['description']}\n"
            
            system_prompt = """
            You are an expert Android automation assistant that can precisely control a device by analyzing UI XML hierarchies.
            
            You need to:
            1. Analyze the XML hierarchy representation of the current Android screen
            2. Identify the elements needed to complete the user's task
            3. Determine the EXACT next action to take
            
            IMPORTANT: Instead of using x,y coordinates, ALWAYS use element identifiers when possible.
            This ensures precise interaction with the right UI elements.
            
            The available actions are:
            - "click_element": Click a specific UI element using one of these identifiers (in order of preference):
              * resourceId (best and most reliable)
              * text (good if exact text match)
              * content-desc (good for accessibility elements)
              * class + index (if nothing else works)
            
            - "input_text": Type text into a field (first click the field, then input)
            
            - "scroll": Scroll in a direction (up, down, left, right)
            
            - "back": Press the back button
            
            - "wait": Wait for a specific condition
            
            Return ONLY valid JSON in this format:
            ```json
            {
              "current_screen": "Identify what screen user is on",
              "action": {
                "type": "click_element | input_text | scroll | back | wait",
                "target": {
                  "method": "resourceId | text | content-desc | class",
                  "value": "The exact identifier from the XML",
                  "fallback_index": 0 
                },
                "text": "Text to input if action is input_text",
                "direction": "up | down | left | right (for scroll action)",
                "duration": 5 (seconds to wait if action is wait)
              },
              "reasoning": "Detailed explanation of why this is the next step",
              "is_task_complete": false
            }
            ```
            
            Only set is_task_complete to true when the entire task is finished.
            
            Always use element identifiers from the XML, not made-up ones.
            """
            
            user_prompt = f"""
            TASK: {task}
            
            {context_info}
            
            CURRENT APP: {metadata["current_app_name"]} ({metadata["current_app"]})
            
            UI HIERARCHY XML:
            ```xml
            {xml_content}
            ```
            
            Based on this XML representation of the current UI, determine the next action to take.
            """
            
            # Call the OpenAI API
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",  # Using GPT-4 Turbo instead of GPT-4o for text analysis
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=1000
            )
            
            # Parse the response
            analysis = json.loads(response.choices[0].message.content)
            print(f"UI Analysis: {json.dumps(analysis, indent=2)}")
            
            return analysis
        except Exception as e:
            print(f"Error analyzing UI with LLM: {e}")
            return None

    async def execute_ui_action(self, action_data):
        """Execute action based on LLM guidance using element selectors instead of coordinates."""
        if not action_data or not action_data.get("action"):
            return "No action to execute"
        
        action = action_data["action"]
        action_type = action.get("type")
        reasoning = action_data.get("reasoning", "No reasoning provided")
        current_screen = action_data.get("current_screen", "Unknown screen")
        
        print(f"Current screen: {current_screen}")
        print(f"Executing action: {action_type}")
        print(f"Reasoning: {reasoning}")
        
        try:
            if action_type == "click_element":
                target = action.get("target", {})
                method = target.get("method")
                value = target.get("value")
                fallback_index = target.get("fallback_index", 0)
                
                if not method or not value:
                    return "Invalid click_element action: missing method or value"
                
                print(f"Clicking element: {method}='{value}'")
                
                # Map method to uiautomator2 selector
                selector = {}
                if method == "resourceId":
                    selector = {"resourceId": value}
                elif method == "text":
                    selector = {"text": value}
                elif method == "content-desc":
                    selector = {"description": value}
                elif method == "class":
                    selector = {"className": value, "instance": fallback_index}
                else:
                    return f"Unsupported selector method: {method}"
                
                # Try to find and click the element
                element = self.device(**selector)
                if element.exists:
                    element.click()
                    return f"Clicked element: {method}='{value}'"
                else:
                    print(f"⚠️ Element not found: {method}='{value}'")
                    return f"Element not found: {method}='{value}'"
            
            elif action_type == "input_text":
                target = action.get("target", {})
                method = target.get("method")
                value = target.get("value")
                fallback_index = target.get("fallback_index", 0)
                text = action.get("text", "")
                
                if not method or not value:
                    return "Invalid input_text action: missing method or value"
                if not text:
                    return "Invalid input_text action: missing text to input"
                
                print(f"Inputting text into: {method}='{value}'")
                print(f"Text: '{text}'")
                
                # Map method to uiautomator2 selector
                selector = {}
                if method == "resourceId":
                    selector = {"resourceId": value}
                elif method == "text":
                    selector = {"text": value}
                elif method == "content-desc":
                    selector = {"description": value}
                elif method == "class":
                    selector = {"className": value, "instance": fallback_index}
                else:
                    return f"Unsupported selector method: {method}"
                
                # Try to find the element and input text
                element = self.device(**selector)
                if element.exists:
                    # Clear existing text first
                    try:
                        element.clear_text()
                    except Exception as e_clear:
                        print(f"Couldn't clear text (may be normal): {e_clear}")
                    
                    # Set text
                    element.set_text(text)
                    return f"Entered text '{text}' into {method}='{value}'"
                else:
                    print(f"⚠️ Element not found for text input: {method}='{value}'")
                    return f"Element not found for text input: {method}='{value}'"
            
            elif action_type == "scroll":
                direction = action.get("direction", "down")
                
                if direction == "down":
                    self.device.swipe(self.width/2, self.height*0.7, self.width/2, self.height*0.3)
                elif direction == "up":
                    self.device.swipe(self.width/2, self.height*0.3, self.width/2, self.height*0.7)
                elif direction == "left":
                    self.device.swipe(self.width*0.7, self.height/2, self.width*0.3, self.height/2)
                elif direction == "right":
                    self.device.swipe(self.width*0.3, self.height/2, self.width*0.7, self.height/2)
                else:
                    return f"Invalid scroll direction: {direction}"
                
                return f"Scrolled {direction}"
            
            elif action_type == "back":
                print("Pressing back button")
                self.device.press("back")
                return "Pressed back button"
            
            elif action_type == "wait":
                duration = action.get("duration", 3)
                print(f"Waiting for {duration} seconds...")
                await asyncio.sleep(duration)
                return f"Waited for {duration} seconds"
            
            else:
                return f"Unknown action type: {action_type}"
        
        except Exception as e:
            error_msg = f"Action failed: {e}"
            print(error_msg)
            return error_msg
    
    async def plan_task(self, task):
        """Use the LLM to break down the task into steps and determine if direct actions are possible."""
        try:
            system_prompt = """
            You are an expert at planning Android automation tasks. Your job is to analyze a user's request and break it down into executable steps.
            
            For each task, determine:
            1. If it involves launching a specific app
            2. What steps should be taken after the app is launched
            3. Whether any parts can be executed directly without UI analysis
            
            Return ONLY valid JSON in this format:
            {
              "analysis": "Brief analysis of what the task involves",
              "has_app_launch": true/false,
              "app_name": "Name of the app to launch (only if has_app_launch is true)",
              "requires_ui_analysis_after_launch": true/false,
              "post_launch_steps": "Description of what needs to be done after app launch",
              "pure_ui_analysis_task": "Full task description if no direct actions possible"
            }
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # Using a smaller model for speed
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Task: {task}"}
                ],
                response_format={"type": "json_object"},
                max_tokens=500
            )
            
            # Parse the response
            plan = json.loads(response.choices[0].message.content)
            print("📋 Task Plan:")
            for key, value in plan.items():
                if key != "analysis":  # Show analysis at the end
                    print(f"  - {key}: {value}")
            print(f"  - Analysis: {plan.get('analysis', '')}")
            
            return plan
        except Exception as e:
            print(f"Error planning task: {e}")
            # Return a fallback plan that uses UI analysis for everything
            return {
                "analysis": "Failed to plan with LLM, using UI analysis",
                "has_app_launch": False,
                "requires_ui_analysis_after_launch": False,
                "pure_ui_analysis_task": task
            }
    
    async def run_task(self, task):
        """Execute a task using LLM planning and UI-guided automation."""
        print(f"Starting task: {task}")
        
        # Reset counters
        self.action_count = 0
        self.last_action_time = 0
        
        # First, check if we can directly launch an app
        app_to_launch = self.parse_task(task)
        direct_launch_success = False
        
        if app_to_launch:
            print(f"📱 Stage 1: Launching app directly ({app_to_launch})")
            try:
                self.device.app_start(app_to_launch)
                await asyncio.sleep(2)  # Wait for app to start
                direct_launch_success = True
                print(f"✅ Successfully launched app ({app_to_launch})")
            except Exception as e:
                print(f"⚠️ Direct app launch failed: {e}")
        
        # If we haven't done a direct launch, or for the next steps, use LLM planning + XML
        if not direct_launch_success:
            # Use LLM to plan the task
            plan = await self.plan_task(task)
            
            # If plan indicates we can launch an app directly
            if plan.get("has_app_launch", False) and plan.get("app_name"):
                app_name = plan["app_name"].lower()
                
                # Verify the app exists in our dictionary
                if app_name in self.common_packages:
                    package_name = self.common_packages[app_name]
                    
                    print(f"📱 Stage 1: Launching {app_name} ({package_name}) directly")
                    try:
                        self.device.app_start(package_name)
                        await asyncio.sleep(2)  # Wait for app to start
                        print(f"✅ Successfully launched {app_name}")
                        direct_launch_success = True
                    except Exception as e:
                        print(f"⚠️ Direct app launch failed: {e}")
        
        # Now use XML + LLM for any remaining actions
        print(f"🤖 Stage 2: Using XML + LLM for task execution")
        
        # Set up context tracking
        context = {
            "task": task,
            "previous_actions": []
        }
        
        # Execute steps with XML guidance
        steps_taken = 0
        max_steps = 15
        results = []
        
        if direct_launch_success:
            context["previous_actions"].append({
                "description": f"Launched app {app_to_launch.split('.')[-1] if direct_launch_success else 'unknown'}"
            })
            results.append(f"Launched app {app_to_launch.split('.')[-1] if direct_launch_success else 'unknown'}")
        
        while steps_taken < max_steps:
            steps_taken += 1
            
            try:
                # Get UI hierarchy XML
                print(f"\nStep {steps_taken}: Getting UI hierarchy...")
                xml_content = self.get_ui_hierarchy_xml()
                
                if not xml_content:
                    print("Failed to get UI hierarchy")
                    results.append("Failed to get UI hierarchy")
                    break
                
                # Analyze UI with LLM
                print("Analyzing UI with LLM...")
                analysis = await self.analyze_ui_with_llm(xml_content, task, context)
                
                if not analysis:
                    print("Failed to analyze UI")
                    results.append("Failed to analyze UI")
                    break
                
                # Execute action
                result = await self.execute_ui_action(analysis)
                results.append(result)
                
                # Update context with this action
                context["previous_actions"].append({
                    "description": result
                })
                
                # Check if task is complete
                if analysis.get("is_task_complete", False):
                    print("Task marked as complete by the LLM")
                    break
                
                # Wait a bit after action to let UI update
                await asyncio.sleep(1.5)
            
            except Exception as e:
                error_msg = f"Error in step {steps_taken}: {e}"
                print(error_msg)
                results.append(error_msg)
                break
        
        if steps_taken >= max_steps:
            results.append("Maximum steps reached, task may be incomplete")
        
        print("\n✅ Task execution finished!")
        print(f"Completed in {steps_taken} steps")
        return "\n".join(results)
    
    async def interactive_session(self):
        """Run an interactive session with the agent."""
        print("\n===== Android Vision Agent =====")
        print("Type 'exit' to end the session")
        
        try:
            # Connect to device
            connected = await self.connect_device()
            if not connected:
                print("Failed to connect to device. Exiting.")
                return
            
            # Start scrcpy (but continue even if it fails)
            scrcpy_started = await self.start_scrcpy()
            if not scrcpy_started:
                print("Warning: scrcpy failed to start. Continuing without screen mirroring.")
                user_input = input("Do you want to continue without screen mirroring? (y/n): ")
                if user_input.lower() != 'y':
                    print("Exiting.")
                    return
            
            # Main interaction loop
            while True:
                task = input("\nEnter task (or 'exit'): ")
                
                if task.lower() in ["exit", "quit", "bye"]:
                    break
                
                print(f"\n🤖 Working on: {task}...")
                result = await self.run_task(task)
                
                print("\n✅ Task completed!")
                print(f"Result: {result}")
                
                feedback = input("\nDid that work? (y/n): ")
                if feedback.lower() == "n":
                    print("I'll try to do better next time.")
        
        except KeyboardInterrupt:
            print("\nSession interrupted.")
        finally:
            self.stop_scrcpy()
            print("Session ended.")

async def main():
    if "OPENAI_API_KEY" not in os.environ:
        print("Error: OPENAI_API_KEY not set.")
        print("Please set it in your environment or in a .env file.")
        return
    
    agent = AndroidVisionAgent()
    await agent.interactive_session()

if __name__ == "__main__":
    asyncio.run(main())