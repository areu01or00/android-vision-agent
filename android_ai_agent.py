import asyncio
import os
import subprocess
import time
import json
import glob
import base64
import re
from PIL import Image
from io import BytesIO
from openai import OpenAI
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
import hashlib

# Load environment variables
load_dotenv()

class AndroidAgent:
    def __init__(self, llm_provider="openai"):
        """Initialize the Android Agent with specified LLM provider."""
        self.adb_path = "adb"
        self.scrcpy_process = None
        self.screenshot_dir = "screenshots"
        self.llm_provider = llm_provider
        self.ui_state_cache = {}
        
        # Initialize the LLM client based on provider
        if llm_provider == "openai":
            self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            self.vision_model = os.environ.get("OPENAI_MODEL_1", "gpt-4o")
            self.planning_model = os.environ.get("OPENAI_MODEL_2", "gpt-4-turbo")
            print(f"Using OpenAI with models: {self.vision_model}, {self.planning_model}")
        else:  # openrouter
            self.openai_client = OpenAI(
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1"
            )
            self.vision_model = os.environ.get("OPENROUTER_MODEL_1", "anthropic/claude-3-opus-20240229")
            self.planning_model = os.environ.get("OPENROUTER_MODEL_2", "meta-llama/llama-3-70b-instruct")
            print(f"Using OpenRouter with models: {self.vision_model}, {self.planning_model}")
        
        # Create necessary directories
        os.makedirs(self.screenshot_dir, exist_ok=True)
        os.makedirs("hierarchies", exist_ok=True)
    
    def _encode_image(self, image_path):
        """Encode image to base64 with resizing for API efficiency."""
        try:
            with Image.open(image_path) as img:
                # Resize if too large
                width, height = img.size
                max_size = (768, 1024)
                if width > max_size[0] or height > max_size[1]:
                    ratio = min(max_size[0] / width, max_size[1] / height)
                    new_size = (int(width * ratio), int(height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Convert to RGB if needed
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                # Save to BytesIO
                buffered = BytesIO()
                img.save(buffered, format="JPEG", quality=85, optimize=True)
                return base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Exception as e:
            print(f"Error encoding image: {e}")
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
    
    async def start_scrcpy(self):
        """Start scrcpy to record the screen."""
        try:
            os.makedirs("recordings", exist_ok=True)
            timestamp = int(time.time())
            recording_path = f"recordings/recording_{timestamp}.mp4"
            cmd = ["scrcpy", "--no-display", "--record", recording_path, "--max-fps", "15"]
            
            self.scrcpy_process = subprocess.Popen(cmd)
            await asyncio.sleep(2)
            return self.scrcpy_process.poll() is None
        except Exception as e:
            print(f"Failed to start scrcpy: {e}")
            return False
    
    def stop_scrcpy(self):
        """Stop the scrcpy process."""
        if self.scrcpy_process:
            self.scrcpy_process.terminate()
            self.scrcpy_process = None
    
    async def capture_screen(self):
        """Capture the current screen using ADB."""
        try:
            timestamp = int(time.time())
            screenshot_path = f"{self.screenshot_dir}/screenshot_{timestamp}.png"
            
            process = await asyncio.create_subprocess_exec(
                self.adb_path, "exec-out", "screencap", "-p",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                print(f"Error capturing screenshot: {stderr.decode()}")
                return None
            
            with open(screenshot_path, "wb") as f:
                f.write(stdout)
            
            return screenshot_path
        except Exception as e:
            print(f"Error capturing screenshot: {e}")
            return None
    
    async def get_xml_hierarchy(self):
        """Extract XML view hierarchy using uiautomator."""
        try:
            timestamp = int(time.time())
            xml_path = f"hierarchies/hierarchy_{timestamp}.xml"
            
            # Dump hierarchy
            dump_cmd = [self.adb_path, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"]
            dump_process = await asyncio.create_subprocess_exec(*dump_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await dump_process.communicate()
            
            if dump_process.returncode != 0:
                return None
            
            # Pull the file
            pull_cmd = [self.adb_path, "pull", "/sdcard/window_dump.xml", xml_path]
            pull_process = await asyncio.create_subprocess_exec(*pull_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await pull_process.communicate()
            
            if pull_process.returncode != 0:
                return None
            
            with open(xml_path, "r") as f:
                return f.read()
        except Exception as e:
            print(f"Error getting XML hierarchy: {e}")
            return None
    
    def cleanup_old_files(self):
        """Remove old files to save space."""
        # Clean up hierarchies
        hierarchies = sorted(glob.glob("hierarchies/hierarchy_*.xml"))
        while len(hierarchies) > 5:
            os.remove(hierarchies.pop(0))
        
        # Clean up screenshots
        screenshots = sorted(glob.glob(f"{self.screenshot_dir}/screenshot_*.png"))
        while len(screenshots) > 10:
            os.remove(screenshots.pop(0))
    
    async def _get_screen_dimensions(self):
        """Get the screen dimensions of the device."""
        try:
            dimensions = subprocess.check_output(["adb", "shell", "wm", "size"]).decode('utf-8').strip()
            width, height = map(int, dimensions.split(': ')[1].split('x'))
            return width, height
        except Exception as e:
            print(f"Error getting screen dimensions: {e}")
            return 1080, 1920  # Default fallback values
    
    async def get_screen_context(self):
        """Get screen context using XML-first approach with screenshot fallback."""
        try:
            # Initialize context
            context = {"app_info": {}, "ui_elements": [], "screen_text": ""}
            
            # Get screen dimensions
            width, height = await self._get_screen_dimensions()
            
            # Get XML hierarchy
            xml_content = await self.get_xml_hierarchy()
            if xml_content:
                # Parse XML
                root = ET.fromstring(xml_content)
                
                # Extract app info
                context["app_info"] = {
                    "package": root.get('package', 'Unknown'),
                    "activity": root.get('activity', 'Unknown'),
                    "app_name": root.get('package', 'Unknown').split('.')[-1].capitalize()
                }
                
                # Extract UI elements
                for node in root.findall('.//*'):
                    element = {
                        "text": node.get('text', ''),
                        "content_desc": node.get('content-desc', ''),
                        "class": node.get('class', ''),
                        "resource_id": node.get('resource-id', ''),
                        "clickable": node.get('clickable', 'false') == 'true',
                        "bounds": node.get('bounds', '')
                    }
                    
                    # Parse bounds if available
                    if element["bounds"]:
                        bounds_match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', element["bounds"])
                        if bounds_match:
                            x1, y1, x2, y2 = map(int, bounds_match.groups())
                            element["center_x"] = (x1 + x2) // 2
                            element["center_y"] = (y1 + y2) // 2
                            
                            # Add percentage coordinates
                            element["center_x_percent"] = round((element["center_x"] / width) * 100, 1)
                            element["center_y_percent"] = round((element["center_y"] / height) * 100, 1)
                    
                    # Only add elements with text, content description, or interactivity
                    if (element["text"] or element["content_desc"] or 
                        element["clickable"] or "edit" in element["class"].lower()):
                        context["ui_elements"].append(element)
                
                # Extract screen text
                text_elements = []
                for node in root.findall('.//*'):
                    text = node.get('text', '').strip()
                    content_desc = node.get('content-desc', '').strip()
                    if text:
                        text_elements.append(text)
                    if content_desc:
                        text_elements.append(content_desc)
                context["screen_text"] = " ".join(text_elements)
            
            # If XML didn't provide enough info, use screenshot
            if not context["ui_elements"]:
                screenshot_path = await self.capture_screen()
                if screenshot_path:
                    # Use vision model to extract text
                    base64_image = self._encode_image(screenshot_path)
                    response = self.openai_client.chat.completions.create(
                        model=self.vision_model,
                        messages=[
                            {"role": "user", "content": [
                                {"type": "text", "text": "Extract all visible text from this Android screen."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                            ]}
                        ],
                        max_tokens=500
                    )
                    context["screen_text"] = response.choices[0].message.content
            
            return context
        except Exception as e:
            print(f"Error getting screen context: {e}")
            return {"app_info": {}, "ui_elements": [], "screen_text": ""}
    
    async def launch_app(self, app_name):
        """Launch an app by name using ADB."""
        print(f"Launching {app_name}...")
        
        # Common app package mapping
        app_packages = {
            "twitter": "com.twitter.android",
            "x": "com.twitter.android",
            "gmail": "com.google.android.gm",
            "chrome": "com.android.chrome",
            "youtube": "com.google.android.youtube",
            "maps": "com.google.android.apps.maps",
            "settings": "com.android.settings",
            "camera": "com.android.camera",
            "photos": "com.google.android.apps.photos",
            "messages": "com.android.messaging",
            "phone": "com.android.dialer",
            "calendar": "com.google.android.calendar",
            "clock": "com.google.android.deskclock",
            "play store": "com.android.vending",
            "whatsapp": "com.whatsapp",
            "instagram": "com.instagram.android",
            "facebook": "com.facebook.katana"
        }
        
        # Find package name
        app_name_lower = app_name.lower()
        package_name = None
        
        for name, pkg in app_packages.items():
            if name in app_name_lower or app_name_lower in name:
                package_name = pkg
                break
        
        if not package_name:
            try:
                # Try to find package using grep
                packages_output = subprocess.check_output(
                    ["adb", "shell", "pm", "list", "packages", "|", "grep", "-i", app_name_lower]
                ).decode('utf-8').strip()
                
                if packages_output:
                    package_name = packages_output.split('\n')[0].replace('package:', '')
                else:
                    return False
            except:
                return False
        
        try:
            # Launch app using monkey
            launch_cmd = [
                "adb", "shell", "monkey", 
                "-p", package_name, 
                "-c", "android.intent.category.LAUNCHER", 
                "1"
            ]
            
            result = subprocess.run(launch_cmd, capture_output=True, text=True)
            success = "Events injected: 1" in result.stdout or "Events injected: 1" in result.stderr
            
            if success:
                await asyncio.sleep(2)  # Wait for app to start
                return True
            return False
        except Exception as e:
            print(f"Error launching app: {e}")
            return False
    
    async def analyze_task(self, task):
        """Analyze if a task requires launching an app."""
        task_lower = task.lower()
        
        # Check for explicit app launch patterns
        app_patterns = [
            r"open\s+([a-zA-Z0-9\s]+?)(?:\s+and|\s+to|\s+app|\s*$)",
            r"launch\s+([a-zA-Z0-9\s]+?)(?:\s+and|\s+to|\s+app|\s*$)",
            r"start\s+([a-zA-Z0-9\s]+?)(?:\s+and|\s+to|\s+app|\s*$)",
            r"use\s+([a-zA-Z0-9\s]+?)(?:\s+and|\s+to|\s+app|\s*$)"
        ]
        
        # Common app keywords
        app_keywords = {
            "twitter": ["twitter", "tweet", "x app"],
            "gmail": ["gmail", "email", "mail"],
            "chrome": ["chrome", "browser", "web"],
            "youtube": ["youtube", "video"],
            "maps": ["maps", "directions", "navigate"],
            "camera": ["camera", "photo", "picture"],
            "settings": ["settings", "preferences"]
        }
        
        # Check patterns
        for pattern in app_patterns:
            match = re.search(pattern, task_lower)
            if match:
                # Extract just the app name, not the entire task
                app_name = match.group(1).strip()
                # Further clean up by taking just the first word if multiple words
                app_name = app_name.split()[0]
                return {"requires_app": True, "app": app_name}
        
        # Check keywords
        for app, keywords in app_keywords.items():
            if any(keyword in task_lower for keyword in keywords):
                return {"requires_app": True, "app": app}
        
        return {"requires_app": False, "app": None}
    
    async def determine_action(self, task, screen_context):
        """Determine the next action based on task and screen context."""
        try:
            # Enhance the system prompt with more specific guidance for Android interactions
            system_prompt = """You are an AI assistant controlling an Android device.
Determine the best next action based on the task and screen context.

CRITICAL INSTRUCTIONS:
- YOU MUST TAKE A CONCRETE ACTION AT EACH STEP - DO NOT JUST ANALYZE
- ALWAYS choose one of the available actions (tap, type, scroll, etc.)
- NEVER skip taking an action - the user is waiting for you to control their device
- For multi-step tasks, execute ONE STEP at a time, then wait for the next iteration
- ALWAYS include x_percent and y_percent for tap actions
- ONLY mark a task as complete when you have ACTUALLY COMPLETED the entire task
- After typing a search query, you MUST tap on a search result or press enter to execute the search
- VERIFY that your action had the intended effect before moving to the next step
- For search tasks, the task is only complete after you've tapped on a search result or pressed enter AND the search results are displayed

IMPORTANT GUIDELINES:
1. Break down complex tasks into individual steps and determine the NEXT SINGLE ACTION to take.
2. For tap actions, x_percent and y_percent MUST be between 0 and 100.
3. Be adaptive and try different approaches if the same action is repeated multiple times.
4. When dealing with menus or options that might not be visible, infer their likely positions based on common Android UI patterns.
5. For Chrome, the menu button (three dots) is typically in the top-right corner (around 95% x, 5-8% y).
6. For apps with floating action buttons (like Gmail, Twitter), these are usually in the bottom-right corner.
7. If you need to open a menu to access certain functionality, explicitly state this in your reasoning.
8. If a UI element is not visible but likely exists, make an educated guess about its position.
9. When a task involves multiple steps, focus on completing one step at a time.
10. If you're unsure about an element's position, try to find similar elements or use common UI patterns.
11. After typing text, look for a search button, keyboard enter key, or suggestion to tap to complete the search.
12. If you encounter an error or unexpected screen, try pressing back or going home and starting again.
13. For search tasks, mark the task as complete only after the search results for your query are visible.
14. For navigation tasks, mark the task as complete only after the destination is reached and verified.
15. For input tasks, mark the task as complete only after the input is submitted and confirmed.

SEARCH TASK COMPLETION CHECKLIST:
1. Open the app (e.g., Chrome, YouTube)
2. Tap on the search bar
3. Type the search query
4. Tap on a search suggestion OR press enter/search key
5. Verify search results are displayed for the correct query
6. ONLY THEN mark the task as complete

COMMON UI PATTERNS:
- Menu buttons are typically in the top-right corner (90-98% x, 5-15% y)
- Back buttons are in the bottom navigation or top-left corner
- Floating action buttons ("+") are usually in the bottom-right corner (85-95% x, 85-95% y)
- Navigation drawers open from the left edge (tap hamburger menu or swipe from left edge)
- Tab bars are at the top or bottom of the screen
- Settings are usually accessed through a menu or gear icon
- Search bars are typically at the top of the screen (40-60% x, 5-15% y)
- Keyboard enter/search keys are usually in the bottom-right of the keyboard
- Suggestions appear below search bars and can be tapped to complete the search

SPECIFIC APP GUIDANCE:
- Chrome: 
  * To open an incognito tab: tap menu (three dots, top-right ~95% x, 8% y), then tap "New Incognito tab" in the menu (~70% x, 20% y)
  * To search: tap address bar (center-top), type query, tap suggestion or press enter, verify results appear
  * To navigate tabs: tap tab switcher button (square icon, top-right) then tap desired tab
  * To refresh: swipe down from top or tap refresh icon near address bar

- Gmail: 
  * To compose an email: tap floating action button (bottom-right)
  * To open an email: tap on the email in the list
  * To reply: tap reply button at the bottom of an open email
  * To navigate folders: tap the hamburger menu (top-left) then select folder

- Twitter/X: 
  * To create a tweet: tap floating action button (bottom-right)
  * To view profile: tap profile icon (usually bottom-right or top-left)
  * To search: tap search icon (usually bottom navigation) then enter query
  * To view notifications: tap bell icon (usually in bottom navigation)

- Maps:
  * To search: tap search bar at top, enter location, tap suggestion or search button
  * To get directions: tap directions button after selecting a location
  * To change view: use two fingers to zoom in/out, or tap layers button

- Camera:
  * To take photo: tap large circular button at bottom
  * To switch cameras: tap switch camera icon (usually top of screen)
  * To access gallery: tap small thumbnail of last photo (usually bottom corner)

ERROR RECOVERY STRATEGIES:
- If a tap doesn't produce expected result: try slightly different coordinates
- If typing doesn't work: tap the input field first, then try typing
- If an app seems frozen: try waiting a few seconds, then press back
- If you can't find a UI element: try scrolling in the most likely direction
- If completely stuck: go home and restart the task from the beginning

EXAMPLE ACTIONS FOR COMMON TASKS:
1. Opening Chrome incognito tab:
   - Action 1: tap at (95%, 8%) to open Chrome menu
   - Action 2: tap at (70%, 20%) to select "New Incognito tab"

2. Searching in Chrome:
   - Action 1: tap at (50%, 10%) to focus address bar
   - Action 2: type "search query"
   - Action 3: tap at (50%, 15%) to select suggestion OR press enter
   - Action 4: verify search results are displayed (is_task_complete = true)

3. Composing email in Gmail:
   - Action 1: tap at (90%, 90%) to tap compose button
   - Action 2: tap at (50%, 30%) to focus recipient field
   - Action 3: type "recipient@email.com"

Respond with a JSON object containing:
- "action": One of ["tap", "type", "scroll", "swipe", "go_home", "press_back", "wait", "press_enter"]
- "x_percent", "y_percent": For tap actions (0-100)
- "text": For type actions
- "direction": For scroll/swipe actions
- "wait_time": For wait actions
- "is_task_complete": Boolean (only true when the ENTIRE task is complete)
- "reasoning": Your reasoning for this action, including any UI patterns you're using"""

            # Prepare user prompt with enhanced context
            user_prompt = f"Task: {task}\n\nScreen Context:\n"
            
            # Add app info
            if screen_context["app_info"]:
                user_prompt += f"App: {screen_context['app_info'].get('app_name', 'Unknown')}\n"
                user_prompt += f"Package: {screen_context['app_info'].get('package', 'Unknown')}\n"
            
            # Add UI elements (limited to 15)
            if screen_context["ui_elements"]:
                user_prompt += "UI Elements:\n"
                for i, elem in enumerate(screen_context["ui_elements"][:15]):
                    user_prompt += f"Element {i+1}: "
                    if elem.get("text"):
                        user_prompt += f"Text: \"{elem.get('text')}\" "
                    if elem.get("content_desc"):
                        user_prompt += f"Desc: \"{elem.get('content_desc')}\" "
                    user_prompt += f"Class: {elem.get('class')} "
                    user_prompt += f"Clickable: {elem.get('clickable')}"
                    if "center_x_percent" in elem and "center_y_percent" in elem:
                        user_prompt += f" Position: ({elem['center_x_percent']}%, {elem['center_y_percent']}%)"
                    elif "center_x" in elem and "center_y" in elem:
                        user_prompt += f" Position: ({elem['center_x']}, {elem['center_y']})"
                    user_prompt += "\n"
            
            # Add screen text
            if screen_context["screen_text"]:
                user_prompt += f"\nScreen Text: {screen_context['screen_text']}\n"
            
            # Add task-specific context to help the LLM
            task_lower = task.lower()
            if "chrome" in task_lower and ("incognito" in task_lower or "private" in task_lower):
                user_prompt += """
Task Context: Opening an incognito tab in Chrome typically requires:
1. Finding the Chrome menu button (three dots, usually in the top-right corner)
2. Tapping the menu button to open the menu
3. Finding and tapping the "New Incognito tab" option in the menu

If the menu button is not visible in the UI elements, it's typically located at around 95% x, 5-8% y position.
The "New Incognito tab" option is usually in the top portion of the menu that appears.
"""
            elif "gmail" in task_lower and "compose" in task_lower:
                user_prompt += """
Task Context: Composing an email in Gmail typically requires:
1. Finding the compose button (usually a floating action button with a plus or pencil icon in the bottom-right)
2. Tapping the compose button
3. Filling in the recipient, subject, and body fields

If the compose button is not visible in the UI elements, it's typically located at around 90% x, 90% y position.
"""
            elif "twitter" in task_lower and "tweet" in task_lower:
                user_prompt += """
Task Context: Creating a tweet typically requires:
1. Finding the compose tweet button (usually a floating action button with a plus or feather icon)
2. Tapping the compose button
3. Typing the tweet content

If the compose button is not visible in the UI elements, it's typically located at around 90% x, 90% y position.
"""
            elif "search" in task_lower:
                # Extract the search query
                search_parts = task_lower.split("search")
                if len(search_parts) > 1:
                    search_query = search_parts[1].strip()
                    user_prompt += f"""
Task Context: Searching for "{search_query}" typically requires:
1. Tapping on the search bar (usually at the top of the screen)
2. Typing the search query "{search_query}"
3. Tapping on a search suggestion OR pressing the enter/search key
4. Verifying that search results for "{search_query}" are displayed

IMPORTANT: After typing the query, you MUST either:
- Tap on a search suggestion (if visible)
- Press the enter/search key (use action "press_enter")
- Tap the search button (if visible)

The task is only complete when search results for "{search_query}" are visible on the screen.
"""
                    
                    # Check if we just typed the query and need to execute the search
                    if self.last_actions and self.last_actions[-1].get("action") == "type" and search_query.lower() in self.last_actions[-1].get("text", "").lower():
                        user_prompt += """
NEXT STEP: You just typed the search query. Now you need to execute the search by either:
1. Tapping on a search suggestion (preferred if visible)
2. Pressing the enter/search key (use action "press_enter")
3. Tapping the search button (if visible)

DO NOT mark the task as complete until search results are visible.
"""
            
            # Add information about the current iteration and previous actions
            if hasattr(self, 'current_iteration') and hasattr(self, 'last_actions'):
                user_prompt += f"\nCurrent Iteration: {self.current_iteration}/15\n"
                
                if self.last_actions:
                    user_prompt += "Previous Actions:\n"
                    for i, action in enumerate(self.last_actions[-3:]):  # Show last 3 actions
                        user_prompt += f"Action {i+1}: {action.get('action', 'unknown')}"
                        if action.get('action') == 'tap':
                            user_prompt += f" at ({action.get('x_percent', 0):.1f}%, {action.get('y_percent', 0):.1f}%)"
                        elif action.get('action') == 'type':
                            user_prompt += f" text: \"{action.get('text', '')}\""
                        elif action.get('action') in ['scroll', 'swipe']:
                            user_prompt += f" direction: {action.get('direction', 'unknown')}"
                        user_prompt += f" - {action.get('reasoning', 'No reasoning')[:50]}...\n"
                    
                    # If we've been repeating the same action, suggest trying a different approach
                    if len(self.last_actions) >= 3:
                        same_action = all(a.get('action') == self.last_actions[0].get('action') for a in self.last_actions[-3:])
                        if same_action:
                            user_prompt += "\nNOTE: The same action has been repeated multiple times without success. Consider trying a different approach or position.\n"
                            
                            # Add specific suggestions based on the repeated action
                            if self.last_actions[0].get('action') == 'tap':
                                user_prompt += """
Suggestions for breaking the tap loop:
1. Try tapping at different positions (e.g., if trying to tap a menu button in the top-right, try slightly different coordinates)
2. Try scrolling to reveal more UI elements
3. Try a different action like pressing back or going to the home screen
4. If trying to tap a menu button, try different corners of the screen
"""
                            elif self.last_actions[0].get('action') == 'scroll':
                                user_prompt += """
Suggestions for breaking the scroll loop:
1. Try tapping in the center of the screen
2. Try scrolling in a different direction
3. Try a different action like pressing back or going to the home screen
"""
            
            user_prompt += "\nDetermine the NEXT SINGLE ACTION to take to progress toward completing the task."
            
            # Make API call
            planning_kwargs = {
                "model": self.planning_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 800
            }
            
            # Add response_format for OpenAI
            if self.llm_provider == "openai":
                planning_kwargs["response_format"] = {"type": "json_object"}
            
            response = self.openai_client.chat.completions.create(**planning_kwargs)
            response_text = response.choices[0].message.content
            
            # Debug: Print raw response
            print(f"Debug - Raw response: {response_text[:100]}...")
            
            # Parse response
            try:
                action_plan = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract JSON from text
                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
                if json_match:
                    try:
                        action_plan = json.loads(json_match.group(1))
                    except:
                        action_plan = self._extract_action_from_text(response_text)
                else:
                    action_plan = self._extract_action_from_text(response_text)
            
            # Ensure numeric values and validate ranges
            for key in ["x_percent", "y_percent", "wait_time"]:
                if key in action_plan and isinstance(action_plan[key], str):
                    try:
                        action_plan[key] = float(action_plan[key])
                    except:
                        action_plan[key] = 50 if key in ["x_percent", "y_percent"] else 1
            
            # Ensure percentages are within valid range (0-100)
            if "x_percent" in action_plan:
                action_plan["x_percent"] = min(max(float(action_plan["x_percent"]), 0), 100)
            if "y_percent" in action_plan:
                action_plan["y_percent"] = min(max(float(action_plan["y_percent"]), 0), 100)
            
            # Print the action plan
            print(f"Action: {action_plan.get('action', 'unknown')}")
            if "x_percent" in action_plan and "y_percent" in action_plan:
                print(f"Position: ({action_plan.get('x_percent'):.1f}%, {action_plan.get('y_percent'):.1f}%)")
            if "text" in action_plan and action_plan["text"]:
                print(f"Text: {action_plan.get('text')}")
            print(f"Reasoning: {action_plan.get('reasoning', 'No reasoning provided')}")
            
            return action_plan
        except Exception as e:
            print(f"Error determining action: {e}")
            return {
                "action": "tap",
                "x_percent": 50,
                "y_percent": 50,
                "text": "",
                "direction": "",
                "wait_time": 0,
                "is_task_complete": False,
                "reasoning": f"Fallback due to error: {str(e)}"
            }
    
    def _extract_action_from_text(self, text):
        """Extract action information from text when JSON parsing fails."""
        action_plan = {
            "action": "tap",
            "x_percent": 50,
            "y_percent": 50,
            "text": "",
            "direction": "",
            "wait_time": 0,
            "is_task_complete": False,
            "reasoning": "Extracted from text"
        }
        
        # Extract action type
        action_match = re.search(r'action["\s:]+([a-z_]+)', text, re.IGNORECASE)
        if action_match:
            action_plan["action"] = action_match.group(1).lower()
        
        # Extract coordinates
        x_match = re.search(r'x_percent["\s:]+(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if x_match:
            try:
                x_percent = float(x_match.group(1))
                # Ensure value is within 0-100 range
                action_plan["x_percent"] = min(max(x_percent, 0), 100)
            except ValueError:
                action_plan["x_percent"] = 50
        
        y_match = re.search(r'y_percent["\s:]+(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if y_match:
            try:
                y_percent = float(y_match.group(1))
                # Ensure value is within 0-100 range
                action_plan["y_percent"] = min(max(y_percent, 0), 100)
            except ValueError:
                action_plan["y_percent"] = 50
        
        # Extract text for typing
        text_match = re.search(r'text["\s:]+["\']([^"\']+)["\']', text, re.IGNORECASE)
        if text_match:
            action_plan["text"] = text_match.group(1)
        
        # Extract direction
        direction_match = re.search(r'direction["\s:]+["\']?([a-z]+)["\']?', text, re.IGNORECASE)
        if direction_match:
            action_plan["direction"] = direction_match.group(1).lower()
        
        # Extract wait time
        wait_match = re.search(r'wait_time["\s:]+(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if wait_match:
            try:
                action_plan["wait_time"] = float(wait_match.group(1))
            except ValueError:
                action_plan["wait_time"] = 1
        
        # Extract task completion
        complete_match = re.search(r'is_task_complete["\s:]+([a-z]+)', text, re.IGNORECASE)
        if complete_match:
            action_plan["is_task_complete"] = complete_match.group(1).lower() == "true"
        
        return action_plan
    
    async def execute_action(self, action):
        """Execute the specified action on the device."""
        action_type = action.get("action", "").lower()
        
        if action_type == "tap":
            # Ensure percentages are within valid range (0-100)
            x_percent = min(max(float(action.get("x_percent", 50)), 0), 100)
            y_percent = min(max(float(action.get("y_percent", 50)), 0), 100)
            
            # Get screen dimensions
            dimensions = subprocess.check_output(["adb", "shell", "wm", "size"]).decode('utf-8').strip()
            width, height = map(int, dimensions.split(': ')[1].split('x'))
            
            x = int(width * x_percent / 100)
            y = int(height * y_percent / 100)
            
            print(f"📱 Tapping at coordinates: {x}, {y} ({x_percent:.1f}%, {y_percent:.1f}%)")
            subprocess.run(["adb", "shell", "input", "tap", str(x), str(y)])
            return True
            
        elif action_type == "type":
            text = action.get("text", "")
            print(f"⌨️ Typing text: \"{text}\"")
            
            # Check if we need to escape special characters
            escaped_text = text.replace("'", "\\'").replace('"', '\\"').replace(" ", "%s")
            subprocess.run(["adb", "shell", "input", "text", escaped_text])
            
            # Check if we should press enter after typing
            if action.get("press_enter", False) or "search" in text.lower():
                print("Pressing Enter key")
                await asyncio.sleep(0.5)
                subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_ENTER"])
            
            return True
            
        elif action_type == "scroll":
            direction = action.get("direction", "down").lower()
            
            print(f"📜 Scrolling {direction}")
            if direction == "down":
                subprocess.run(["adb", "shell", "input", "swipe", "500", "1500", "500", "500", "300"])
            elif direction == "up":
                subprocess.run(["adb", "shell", "input", "swipe", "500", "500", "500", "1500", "300"])
            elif direction == "left":
                subprocess.run(["adb", "shell", "input", "swipe", "100", "500", "900", "500", "300"])
            elif direction == "right":
                subprocess.run(["adb", "shell", "input", "swipe", "900", "500", "100", "500", "300"])
            return True
            
        elif action_type == "swipe":
            # Ensure percentages are within valid range (0-100)
            start_x = min(max(float(action.get("start_x_percent", 50)), 0), 100)
            start_y = min(max(float(action.get("start_y_percent", 50)), 0), 100)
            end_x = min(max(float(action.get("end_x_percent", 50)), 0), 100)
            end_y = min(max(float(action.get("end_y_percent", 50)), 0), 100)
            
            # Get screen dimensions
            dimensions = subprocess.check_output(["adb", "shell", "wm", "size"]).decode('utf-8').strip()
            width, height = map(int, dimensions.split(': ')[1].split('x'))
            
            # Convert percentages to actual coordinates
            start_x_px = int(width * start_x / 100)
            start_y_px = int(height * start_y / 100)
            end_x_px = int(width * end_x / 100)
            end_y_px = int(height * end_y / 100)
            
            print(f"🔄 Swiping from ({start_x:.1f}%, {start_y:.1f}%) to ({end_x:.1f}%, {end_y:.1f}%)")
            subprocess.run(["adb", "shell", "input", "swipe", 
                           str(start_x_px), str(start_y_px), 
                           str(end_x_px), str(end_y_px), "300"])
            return True
            
        elif action_type == "wait":
            wait_time = action.get("wait_time", 1)
            print(f"⏱️ Waiting for {wait_time} seconds")
            await asyncio.sleep(wait_time)
            return True
            
        elif action_type == "go_home" or action_type == "home":
            print("🏠 Going to home screen")
            subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_HOME"])
            return True
            
        elif action_type == "press_back" or action_type == "back":
            print("⬅️ Pressing back button")
            subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_BACK"])
            return True
            
        elif action_type == "recent_apps" or action_type == "recents":
            print("🔄 Opening recent apps")
            subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_APP_SWITCH"])
            return True
            
        elif action_type == "press_enter":
            print("⌨️ Pressing Enter key")
            subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_ENTER"])
            return True
            
        else:
            print(f"❌ Unknown action type: {action_type}")
            return False
    
    async def handle_specific_task(self, task):
        """Placeholder for specific task handling - always returns None to use general approach."""
        return None
    
    async def verify_search_results(self, query, screen_context):
        """Verify that search results for the given query are displayed."""
        # Check if the query appears in the screen text
        if query.lower() in screen_context["screen_text"].lower():
            return True
        
        # Check if any UI elements contain the query
        for elem in screen_context["ui_elements"]:
            if query.lower() in elem.get("text", "").lower() or query.lower() in elem.get("content_desc", "").lower():
                return True
        
        # Check for common search result indicators
        search_indicators = ["results", "search", "found", "showing", "related"]
        for indicator in search_indicators:
            if indicator in screen_context["screen_text"].lower():
                return True
        
        return False
    
    async def run_task(self, task):
        """Run a task on the Android device."""
        print(f"\n🤖 Running task: {task}")
        
        # Analyze if we need to launch an app
        task_analysis = await self.analyze_task(task)
        
        # Launch app if needed
        if task_analysis["requires_app"]:
            app_name = task_analysis["app"]
            print(f"📱 Task requires launching {app_name}")
            
            launch_success = await self.launch_app(app_name)
            
            if launch_success:
                print(f"✅ Successfully launched {app_name}")
                
                # If task is ONLY to open the app, we're done
                app_only_pattern = f"^(open|launch|start|use)\\s+{re.escape(app_name)}$"
                if re.search(app_only_pattern, task.lower()):
                    print(f"✅ Task completed: {task}")
                    return True
                
                # Otherwise, continue with the rest of the task
                print(f"Continuing with the rest of the task: {task}")
            else:
                print(f"❌ Failed to launch {app_name}")
        
        # Initialize tracking variables
        self.last_actions = []
        last_action = None
        repetitive_count = 0
        
        # Main task execution loop
        for iteration in range(15):
            self.current_iteration = iteration + 1
            print(f"\n📱 Iteration {self.current_iteration}/15")
            
            # Get screen context
            screen_context = await self.get_screen_context()
            
            # Determine next action
            action_plan = await self.determine_action(task, screen_context)
            
            # Store action for future reference
            self.last_actions.append(action_plan)
            if len(self.last_actions) > 5:  # Keep only the last 5 actions
                self.last_actions.pop(0)
            
            # Check if task is complete
            if action_plan.get("is_task_complete", False):
                # For search tasks, verify that the search was actually executed
                if "search" in task.lower():
                    # Extract the search query from the task
                    search_query = task.lower().split("search")[1].strip()
                    if action_plan.get("action") == "type":
                        print("⚠️ Search task requires executing the search, not just typing the query")
                        action_plan["is_task_complete"] = False
                    elif self.last_actions and self.last_actions[-1].get("action") == "type":
                        # If the last action was typing and this action is not a tap or enter, it's not complete
                        if action_plan.get("action") != "tap" and not action_plan.get("press_enter", False):
                            print("⚠️ Search task requires tapping a result or pressing enter after typing")
                            action_plan["is_task_complete"] = False
                    
                    # Verify search results are displayed
                    if not await self.verify_search_results(search_query, screen_context):
                        print(f"⚠️ Search results for '{search_query}' not yet displayed")
                        action_plan["is_task_complete"] = False
                
                if action_plan.get("is_task_complete", False):
                    print(f"✅ Task completed: {task}")
                    return True
            
            # Check for repetitive actions
            action = action_plan.get("action", "")
            if action == last_action:
                repetitive_count += 1
                print(f"⚠️ Repetitive action: {action} (count: {repetitive_count})")
                
                if repetitive_count >= 5:
                    print(f"⚠️ Breaking repetitive loop: {action}")
                    
                    # Try different strategies
                    if action == "tap":
                        await self.execute_action({"action": "scroll", "direction": "down"})
                    elif action == "scroll":
                        await self.execute_action({"action": "tap", "x_percent": 50, "y_percent": 50})
                    else:
                        await self.execute_action({"action": "go_home"})
                    
                    repetitive_count = 0
                    await asyncio.sleep(2)
                    continue
            else:
                repetitive_count = 0
                last_action = action
            
            # Execute action
            await self.execute_action(action_plan)
            await asyncio.sleep(1)
        
        print(f"⚠️ Reached maximum iterations without completing task")
        return False
    
    async def interactive_session(self):
        """Start an interactive session with the Android device."""
        print("\n===== Android Agent =====")
        print("Type 'exit' to end the session")
        print("Type 'help' for commands")
        
        # Start scrcpy
        await self.start_scrcpy()
        
        while True:
            user_input = input("\nEnter task or command: ")
            
            if user_input.lower() == 'exit':
                self.stop_scrcpy()
                print("Session ended.")
                break
                
            elif user_input.lower() == 'help':
                print("\nCommands:")
                print("  exit - End session")
                print("  help - Show commands")
                print("  context - Analyze screen")
                print("  screenshot - Take screenshot")
                print("  launch [app] - Launch app")
                print("  home - Go to home screen")
                print("  back - Press back button")
                
            elif user_input.lower() == 'context':
                context = await self.get_screen_context()
                print("\n=== SCREEN ANALYSIS ===")
                print(f"App: {context['app_info'].get('app_name', 'Unknown')}")
                print("\n--- UI ELEMENTS ---")
                for i, element in enumerate(context.get('ui_elements', [])[:10]):
                    print(f"{i+1}. {element.get('text', 'No text')} - {element.get('class', 'unknown')}")
                
            elif user_input.lower() == 'screenshot':
                screenshot_path = await self.capture_screen()
                print(f"Screenshot saved to {screenshot_path}")
                
            elif user_input.lower().startswith('launch '):
                app_name = user_input[7:].strip()
                await self.launch_app(app_name)
                
            elif user_input.lower() == 'home':
                await self.execute_action({"action": "go_home"})
                
            elif user_input.lower() == 'back':
                await self.execute_action({"action": "press_back"})
                
            else:
                result = await self.run_task(user_input)
                if not result:
                    print("\n❌ Task could not be completed.")

async def main():
    # Check for API keys
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENROUTER_API_KEY"):
        print("Error: No API keys found. Set OPENAI_API_KEY or OPENROUTER_API_KEY in .env file.")
        return
    
    # Ask user to select provider
    print("\nSelect LLM provider:")
    print("1. OpenAI (requires OPENAI_API_KEY)")
    print("2. OpenRouter (requires OPENROUTER_API_KEY)")
    
    provider_choice = input("Enter choice (1/2): ").strip()
    provider = "openai" if provider_choice == "1" else "openrouter"
    
    # Create agent and start session
    agent = AndroidAgent(llm_provider=provider)
    await agent.interactive_session()

if __name__ == "__main__":
    asyncio.run(main())
