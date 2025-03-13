import asyncio
import os
import subprocess
import time
import json
import re
import uiautomator2 as u2
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import hashlib
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
        self.ui_hash_cache = {}  # Cache for UI hashes -> actions
        self.last_ui_hash = None
        
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
        for pattern in [r'open (?:the )?(?:app )?(\w+)', r'launch (?:the )?(?:app )?(\w+)', r'start (?:the )?(?:app )?(\w+)']:
            match = re.search(pattern, task_lower)
            if match:
                app_name = match.group(1).strip()
                if app_name in self.common_packages:
                    return self.common_packages[app_name]
        
        # If we get here, this requires XML analysis
        return None

    def get_ui_hierarchy_xml(self):
        """Get complete XML representation of current UI using direct API methods."""
        try:
            print("Getting UI hierarchy via direct API method...")
            
            # Method 1: Try using the direct dump_hierarchy method
            try:
                hierarchy = self.device.dump_hierarchy()
                if hierarchy and len(hierarchy) > 100:  # Reasonability check
                    print("Successfully retrieved UI hierarchy using dump_hierarchy()")
                    return hierarchy
            except Exception as e1:
                print(f"Error with dump_hierarchy(): {e1}")
            
            # Method 2: Try using the XPath module
            try:
                print("Trying alternate method via XPath...")
                hierarchy = self.device.xpath.dump(pretty=True)
                if hierarchy and len(hierarchy) > 100:
                    print("Successfully retrieved UI hierarchy using xpath.dump()")
                    return hierarchy
            except Exception as e2:
                print(f"Error with xpath.dump(): {e2}")
            
            # Method 3: Try JSONRpc method (lower level)
            try:
                print("Trying JSONRpc method...")
                hierarchy = self.device.jsonrpc.dumpWindowHierarchy(True)
                if hierarchy and len(hierarchy) > 100:
                    print("Successfully retrieved UI hierarchy using jsonrpc.dumpWindowHierarchy()")
                    return hierarchy
            except Exception as e3:
                print(f"Error with jsonrpc.dumpWindowHierarchy(): {e3}")
                
            # Method 4: Try initializing the agent and then dumping
            try:
                print("Trying to initialize ATX agent...")
                subprocess.run(["python", "-m", "uiautomator2", "init", "--reinstall"], 
                              capture_output=True, text=True)
                time.sleep(2)
                
                # Try again after initialization
                hierarchy = self.device.dump_hierarchy()
                if hierarchy and len(hierarchy) > 100:
                    print("Successfully retrieved UI hierarchy after initialization")
                    return hierarchy
            except Exception as e4:
                print(f"Error with ATX agent initialization: {e4}")
            
            # All methods failed
            print("All methods to get UI hierarchy failed")
            return None
            
        except Exception as e:
            print(f"Error getting UI hierarchy: {e}")
            return None
    
    def compute_ui_hash(self, xml_content):
        """Compute a hash of the UI hierarchy to detect changes and enable caching."""
        try:
            # Parse the XML
            soup = BeautifulSoup(xml_content, 'lxml-xml')
            
            # Find all interactive elements (buttons, text fields, etc.)
            interactive_elements = soup.find_all(['node'], {'clickable': 'true'})
            interactive_elements += soup.find_all(['node'], {'class': lambda x: x and ('Button' in x or 'EditText' in x)})
            
            # Extract key properties (bounds, text, resourceId)
            key_properties = []
            for elem in interactive_elements:
                props = {
                    'bounds': elem.get('bounds', ''),
                    'text': elem.get('text', ''),
                    'resourceId': elem.get('resource-id', '')
                }
                key_properties.append(json.dumps(props))
            
            # Create a stable representation and hash it
            sorted_props = sorted(key_properties)
            hash_input = '|'.join(sorted_props)
            hash_obj = hashlib.md5(hash_input.encode())
            return hash_obj.hexdigest()
        except Exception as e:
            print(f"Error computing UI hash: {e}")
            return None
        
    def preprocess_xml(self, xml_content):
        """Preprocess XML to make it more efficient for the LLM to process."""
        try:
            # Parse the XML
            soup = BeautifulSoup(xml_content, 'lxml-xml')
            
            # Simplify text nodes by truncating long text
            for node in soup.find_all('node'):
                if node.has_attr('text') and len(node['text']) > 50:
                    node['text'] = node['text'][:50] + "..."
                    
            # Remove deeply nested non-interactive elements to reduce size
            def simplify_node(node, depth=0):
                if depth > 5:  # Don't go too deep
                    return
                    
                children = list(node.find_all('node', recursive=False))
                for child in children:
                    # Keep if it's interactive or has text
                    is_interactive = (
                        child.get('clickable') == 'true' or 
                        (child.get('class') and ('Button' in child['class'] or 'Text' in child['class'] or 'EditText' in child['class']))
                    )
                    has_text = child.get('text') and child['text'].strip()
                    
                    if not (is_interactive or has_text) and not child.find('node'):
                        child.decompose()  # Remove if not useful
                    else:
                        simplify_node(child, depth+1)
            
            # Apply simplification to top-level nodes
            for node in soup.find_all('node', recursive=False):
                simplify_node(node)
                
            return str(soup)
        except Exception as e:
            print(f"Error preprocessing XML: {e}")
            return xml_content  # Return original if processing fails
    
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
    
    async def analyze_ui_with_multi_step_planning(self, xml_content, task, context=None):
        """Have LLM analyze XML hierarchy and plan multiple steps."""
        if not xml_content:
            print("No XML content to analyze")
            return None
        
        try:
            # Compute hash of UI to detect if we've seen this state before
            ui_hash = self.compute_ui_hash(xml_content)
            
            # Check if we've seen this UI state before
            if ui_hash and ui_hash in self.ui_hash_cache:
                cached_plan = self.ui_hash_cache[ui_hash]
                print("⚡ Using cached multi-step plan for similar UI state")
                return cached_plan
            
            # Check if UI is similar to the last UI (for repetitive actions like scrolling)
            minor_change = False
            if self.last_ui_hash and ui_hash:
                # For now, assume all states require fresh planning
                # In a more sophisticated implementation, this could detect minor changes
                # like scrolling and reuse the previous plan
                self.last_ui_hash = ui_hash
            
            # Extract metadata to help the LLM understand the UI
            metadata = self.extract_ui_metadata(xml_content)
            
            # Preprocess XML to make it more digestible for the LLM
            processed_xml = self.preprocess_xml(xml_content)
            
            # Create context description for the LLM
            context_info = ""
            if context and context.get("previous_actions"):
                context_info += "PREVIOUS ACTIONS:\n"
                for i, action in enumerate(context["previous_actions"]):
                    context_info += f"{i+1}. {action['description']}\n"
            
            # Determine how many steps to plan based on complexity
            max_steps_to_plan = 3
            if "scroll" in task.lower():
                max_steps_to_plan = 5  # More steps for scrolling tasks
                
            system_prompt = f"""
            You are an expert Android automation assistant that can precisely control a device by analyzing UI XML hierarchies.
            
            Your task is to:
            1. Analyze the XML hierarchy representation of the current Android screen
            2. Plan the next {max_steps_to_plan} actions to complete the user's task efficiently
            3. Be specific about each action with exact element identifiers
            
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
            
            For repetitive actions like scrolling multiple times, combine them into a single action with a count.
            
            Return ONLY valid JSON in this format:
            ```json
            {{
              "current_screen": "Identify what screen user is on",
              "multi_step_plan": [
                {{
                  "action": {{
                    "type": "click_element | input_text | scroll | back | wait",
                    "target": {{
                      "method": "resourceId | text | content-desc | class",
                      "value": "The exact identifier from the XML",
                      "fallback_index": 0 
                    }},
                    "text": "Text to input if action is input_text",
                    "direction": "up | down | left | right (for scroll action)",
                    "duration": 5 (seconds to wait if action is wait),
                    "repeat_count": 1 (number of times to repeat this action, default 1)
                  }},
                  "description": "Human-readable description of this step",
                  "expected_outcome": "What should happen after this action"
                }}
                // ... more steps up to {max_steps_to_plan}
              ],
              "reasoning": "Detailed explanation of this plan",
              "is_task_complete": false,
              "requires_verification_after": true/false (whether to check UI after executing)
            }}
            ```
            
            Only set is_task_complete to true when the entire task is finished.
            If requires_verification_after is true, UI will be checked after executing the steps.
            For scrolling or repetitive actions, set requires_verification_after to true after multiple steps.
            
            Always use element identifiers from the XML, not made-up ones.
            """
            
            user_prompt = f"""
            TASK: {task}
            
            {context_info}
            
            CURRENT APP: {metadata["current_app_name"]} ({metadata["current_app"]})
            
            UI HIERARCHY XML:
            ```xml
            {processed_xml}
            ```
            
            Based on this XML representation of the current UI, plan the next {max_steps_to_plan} actions to take.
            """
            
            # Call the OpenAI API with gpt-4o-mini (more efficient for XML analysis)
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Using GPT-4o-mini for efficiency
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=2000,
                temperature=0.2  # Lower temperature for more deterministic responses
            )
            
            # Parse the response
            multi_step_plan = json.loads(response.choices[0].message.content)
            print(f"Multi-step plan: {json.dumps(multi_step_plan, indent=2)}")
            
            # Cache this plan for this UI state
            if ui_hash:
                self.ui_hash_cache[ui_hash] = multi_step_plan
                self.last_ui_hash = ui_hash
            
            return multi_step_plan
        except Exception as e:
            print(f"Error analyzing UI with LLM: {e}")
            return None

    async def execute_ui_action(self, action_data):
        """Execute action based on LLM guidance using element selectors instead of coordinates."""
        if not action_data or not isinstance(action_data, dict):
            return "No action to execute"
        
        action_type = action_data.get("type")
        target = action_data.get("target", {})
        method = target.get("method")
        value = target.get("value")
        fallback_index = target.get("fallback_index", 0)
        repeat_count = action_data.get("repeat_count", 1)
        
        try:
            for i in range(repeat_count):
                if i > 0:
                    print(f"Repeating action {i+1}/{repeat_count}...")
                    
                if action_type == "click_element":
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
                        result = f"Clicked element: {method}='{value}'"
                    else:
                        print(f"⚠️ Element not found: {method}='{value}'")
                        result = f"Element not found: {method}='{value}'"
                
                elif action_type == "input_text":
                    text = action_data.get("text", "")
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
                        result = f"Entered text '{text}' into {method}='{value}'"
                    else:
                        print(f"⚠️ Element not found for text input: {method}='{value}'")
                        result = f"Element not found for text input: {method}='{value}'"
                
                elif action_type == "scroll":
                    direction = action_data.get("direction", "down")
                    
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
                    
                    result = f"Scrolled {direction}"
                
                elif action_type == "back":
                    print("Pressing back button")
                    self.device.press("back")
                    result = "Pressed back button"
                
                elif action_type == "wait":
                    duration = action_data.get("duration", 3)
                    print(f"Waiting for {duration} seconds...")
                    await asyncio.sleep(duration)
                    result = f"Waited for {duration} seconds"
                
                else:
                    return f"Unknown action type: {action_type}"
                
                # Short pause between repetitions of the same action
                if i < repeat_count - 1:
                    await asyncio.sleep(0.5)
                
            return result
        
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
        app_name = "unknown"
        
        if app_to_launch:
            print(f"📱 Stage 1: Launching {app_to_launch} directly")
            try:
                self.device.app_start(app_to_launch)
                await asyncio.sleep(2)  # Wait for app to start
                direct_launch_success = True
                app_name = app_to_launch.split('.')[-1]
                print(f"✅ Successfully launched {app_name}")
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
        planning_cycles = 0
        max_planning_cycles = 5
        total_steps_taken = 0
        max_total_steps = 20
        results = []
        
        if direct_launch_success:
            context["previous_actions"].append({
                "description": f"Launched app {app_name}"
            })
            results.append(f"Launched app {app_name}")
        
        task_complete = False
        
        while planning_cycles < max_planning_cycles and total_steps_taken < max_total_steps and not task_complete:
            planning_cycles += 1
            
            try:
                # Get UI hierarchy XML
                print(f"\nPlanning cycle {planning_cycles}: Getting UI hierarchy...")
                xml_content = self.get_ui_hierarchy_xml()
                
                if not xml_content:
                    print("Failed to get UI hierarchy")
                    results.append("Failed to get UI hierarchy")
                    break
                
                # Analyze UI with LLM and get multi-step plan
                print("Analyzing UI with LLM for multi-step planning...")
                multi_step_plan = await self.analyze_ui_with_multi_step_planning(xml_content, task, context)
                
                if not multi_step_plan:
                    print("Failed to analyze UI")
                    results.append("Failed to analyze UI")
                    break
                
                # Execute each action in the multi-step plan
                step_count = 0
                for step in multi_step_plan.get("multi_step_plan", []):
                    step_count += 1
                    total_steps_taken += 1
                    
                    if total_steps_taken > max_total_steps:
                        print(f"Reached maximum total steps limit ({max_total_steps})")
                        break
                    
                    print(f"\nStep {total_steps_taken}: {step.get('description', 'Executing action')}")
                    action_data = step.get("action", {})
                    
                    # Execute action
                    result = await self.execute_ui_action(action_data)
                    results.append(result)
                    
                    # Update context with this action
                    context["previous_actions"].append({
                        "description": result
                    })
                    
                    # Wait a bit after action to let UI update
                    await asyncio.sleep(1)
                
                # Check if task is complete
                if multi_step_plan.get("is_task_complete", False):
                    print("Task marked as complete by the LLM")
                    task_complete = True
                    break
                
                # Check if we need to verify after executing the plan
                requires_verification = multi_step_plan.get("requires_verification_after", True)
                
                if not requires_verification and not task_complete:
                    # If no verification needed and more steps planned, execute them without checking UI again
                    continue
                
                # Wait a bit longer after all steps to let UI update fully
                await asyncio.sleep(1.5)
            
            except Exception as e:
                error_msg = f"Error in planning cycle {planning_cycles}: {e}"
                print(error_msg)
                results.append(error_msg)
                break
        
        if total_steps_taken >= max_total_steps:
            results.append("Maximum steps reached, task may be incomplete")
        
        print("\n✅ Task execution finished!")
        print(f"Completed in {total_steps_taken} steps")
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
            
            # Try to initialize UIAutomator2 at startup
            try:
                print("\nAttempting to initialize UIAutomator2 services...")
                init_result = subprocess.run(["python", "-m", "uiautomator2", "init"], 
                              capture_output=True, text=True)
                if "Success" in init_result.stdout:
                    print("✅ UIAutomator2 initialization successful")
                else:
                    print("⚠️ UIAutomator2 initialization may not have succeeded, but we'll continue")
            except Exception as e:
                print(f"Error initializing UIAutomator2: {e}")
                print("Continuing anyway...")
            
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