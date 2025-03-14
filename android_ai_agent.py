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

# Debug environment variables removed

class SimpleAndroidAgent:
    def __init__(self, llm_provider="openai"):
        """Initialize the Simple Android Agent.
        
        Args:
            llm_provider (str): The LLM provider to use ('openai' or 'openrouter')
        """
        self.adb_path = "adb"  # Assume adb is in PATH
        self.scrcpy_process = None
        self.screenshot_dir = "screenshots"
        self.llm_provider = llm_provider
        self.recent_actions = []  # Store recent actions to detect loops
        self.same_action_count = 0  # Counter for repeated identical actions
        
        # Initialize the LLM client based on provider
        if llm_provider == "openai":
            self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            
            # Initialize separate models for vision and planning
            self.vision_model = os.environ.get("OPENAI_MODEL_1")
            if not self.vision_model:
                self.vision_model = "gpt-4o"  # Default vision model
                
            self.planning_model = os.environ.get("OPENAI_MODEL_2")
            if not self.planning_model:
                self.planning_model = "gpt-4-turbo"  # Default planning model
                
            print(f"Using OpenAI with vision model: {self.vision_model}")
            print(f"Using OpenAI with planning model: {self.planning_model}")
            
        else:  # openrouter
            # OpenRouter is compatible with OpenAI's client with a different base URL
            self.openai_client = OpenAI(
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1"
            )
            
            # Initialize separate models for vision and planning
            self.vision_model = os.environ.get("OPENROUTER_MODEL_1")
            if not self.vision_model:
                self.vision_model = "microsoft/phi-4-multimodal-instruct"  # Default vision model
                
            # Debug code removed
                
            # Directly set the planning model from environment or use default
            self.planning_model = os.environ.get("OPENROUTER_MODEL_2", "meta-llama/llama-3-70b-instruct")
                
            print(f"Using OpenRouter with vision model: {self.vision_model}")
            print(f"Using OpenRouter with planning model: {self.planning_model}")
            
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
    
    async def get_view_hierarchy(self):
        """Extract the XML view hierarchy from the current screen using uiautomator.
        
        Returns:
            str: XML content of the view hierarchy, or None if an error occurred
        """
        try:
            # Create a timestamp for the file
            timestamp = int(time.time())
            xml_path = f"hierarchies/hierarchy_{timestamp}.xml"
            os.makedirs("hierarchies", exist_ok=True)
            
            # Dump the view hierarchy to a file on the device
            dump_cmd = [self.adb_path, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"]
            dump_process = await asyncio.create_subprocess_exec(
                *dump_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            dump_stdout, dump_stderr = await dump_process.communicate()
            
            if dump_process.returncode != 0:
                print(f"Error dumping view hierarchy: {dump_stderr.decode()}")
                return None
                
            # Pull the file to the local machine
            pull_cmd = [self.adb_path, "pull", "/sdcard/window_dump.xml", xml_path]
            pull_process = await asyncio.create_subprocess_exec(
                *pull_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            pull_stdout, pull_stderr = await pull_process.communicate()
            
            if pull_process.returncode != 0:
                print(f"Error pulling view hierarchy: {pull_stderr.decode()}")
                return None
                
            # Read the XML file
            with open(xml_path, "r") as f:
                xml_content = f.read()
                
            print(f"Successfully extracted view hierarchy to {xml_path}")
            return xml_content
            
        except Exception as e:
            print(f"Error getting view hierarchy: {e}")
            return None
            
    def cleanup_old_hierarchies(self):
        """Remove old view hierarchy files to save space."""
        hierarchies = sorted(glob.glob(f"hierarchies/hierarchy_*.xml"))
        while len(hierarchies) > 5:  # Keep only the 5 most recent hierarchies
            oldest = hierarchies.pop(0)
            os.remove(oldest)
            print(f"Removed old hierarchy: {oldest}")
    
    def cleanup_old_screenshots(self):
        """Remove old screenshots to save space."""
        screenshots = sorted(glob.glob(f"{self.screenshot_dir}/screenshot_*.png"))
        while len(screenshots) > 10:  # Keep only the 10 most recent screenshots
            oldest = screenshots.pop(0)
            os.remove(oldest)
            print(f"Removed old screenshot: {oldest}")
    
    async def extract_text_from_screen(self, screenshot_path):
        """Extract text from screenshot using vision-capable LLM."""
        try:
            # Resize and encode image to base64
            base64_image = self.resize_image(screenshot_path)
            
            # Configure request parameters - no JSON response needed for this method
            kwargs = {
                "model": self.vision_model,
                "messages": [
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
                "max_tokens": 500
            }
            
            # Make the API call
            response = self.openai_client.chat.completions.create(**kwargs)
            
            # This method just wants the raw text, no JSON parsing needed
            extracted_text = response.choices[0].message.content
            return extracted_text
        except Exception as e:
            print(f"Error extracting text: {e}")
            return ""
    
    async def analyze_screen_with_llm(self, screenshot_path, question):
        """Use a vision-capable LLM to analyze the screen and answer a question."""
        try:
            # Resize and encode image to base64
            base64_image = self.resize_image(screenshot_path)
            
            # Configure request parameters - no JSON response needed for this method
            kwargs = {
                "model": self.vision_model,
                "messages": [
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
                "max_tokens": 500
            }
            
            # Make the API call
            response = self.openai_client.chat.completions.create(**kwargs)
            
            # This method just wants the raw answer, no JSON parsing needed
            analysis = response.choices[0].message.content
            return analysis
        except Exception as e:
            print(f"Error analyzing screen with LLM: {e}")
            return f"Error analyzing screen: {str(e)}"
    
    async def analyze_screen_context(self, screenshot_path):
        """Use a hybrid approach to analyze the screen context:
        1. Vision model extracts raw visual information
        2. Planning model processes this information for better reasoning
        
        This combines visual understanding with powerful reasoning.
        """
        try:
            # STEP 1: Use vision model to extract raw visual information
            base64_image = self.resize_image(screenshot_path)
            
            # Configure request for vision model to extract raw visual information
            vision_kwargs = {
                "model": self.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": """Describe this Android screen capture in detail:
                            
Please identify and describe:
1. ALL visible text elements
2. ALL visible UI elements, buttons, and controls
3. ALL visible images, icons and their apparent purpose
4. The overall layout and arrangement

Focus on providing a COMPREHENSIVE, FACTUAL description with NO interpretation.
DO NOT make any assumptions about what actions should be taken.
"""},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 1200
            }
            
            # Make the API call to vision model
            vision_response = self.openai_client.chat.completions.create(**vision_kwargs)
            visual_description = vision_response.choices[0].message.content
            
            print("Visual information extracted, passing to planning model for reasoning...")
            
            # STEP 2: Use planning model to reason about the extracted information
            planning_kwargs = {
                "model": self.planning_model,
                "messages": [
                    {"role": "system", "content": """You are an expert Android UI analyzer.
Your task is to analyze a detailed description of an Android screen and draw conclusions about:
1. Which app is open
2. What screen/view is being shown
3. What key UI elements are present
4. What actions are possible from this state

Use this information to create a structured analysis that will help guide automated interaction with the device."""},
                    {"role": "user", "content": f"""Here is a detailed visual description of an Android screen:

{visual_description}

Based on this description, please identify:
1. Which app appears to be open
2. Which specific screen/state the app is in
3. Important UI elements visible
4. Possible actions from this screen

Return a JSON object with:
{{
    "app": "Name of the app that appears to be open",
    "screen": "Specific screen within the app (e.g., 'home', 'search', 'profile')",
    "key_elements": ["List of important UI elements visible"],
    "possible_actions": ["List of actions that seem possible from this screen"]
}}"""}
                ],
                "max_tokens": 800
            }
            
            # Only add response_format for OpenAI
            if self.llm_provider == "openai":
                planning_kwargs["response_format"] = {"type": "json_object"}
            
            # Make the API call to planning model
            planning_response = self.openai_client.chat.completions.create(**planning_kwargs)
            response_text = planning_response.choices[0].message.content
            
            # Parse the response from the planning model
            try:
                # First try direct parsing
                context = json.loads(response_text)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON
                try:
                    # Look for JSON-like content between curly braces
                    json_text = response_text[response_text.find('{'):response_text.rfind('}')+1]
                    if json_text:
                        context = json.loads(json_text)
                    else:
                        raise ValueError("No JSON found in response")
                except (json.JSONDecodeError, ValueError):
                    # If all parsing fails, create a simple context object
                    print(f"Could not parse JSON from context response, using fallback text processing")
                    
                    # Create a basic context object with information extracted from text
                    context = {
                        "app": "unknown",
                        "screen": "unknown",
                        "key_elements": ["Text response (not JSON)"],
                        "possible_actions": ["Use the 'screenshot' command to see the current screen"]
                    }
                    
                    # Try to extract app name and screen if mentioned
                    if "app:" in response_text.lower():
                        app_line = response_text.lower().split("app:")[1].split("\n")[0]
                        context["app"] = app_line.strip()
                    if "screen:" in response_text.lower():
                        screen_line = response_text.lower().split("screen:")[1].split("\n")[0]
                        context["screen"] = screen_line.strip()
            
            return context
        except Exception as e:
            print(f"Error analyzing screen context: {e}")
            return {
                "app": "unknown",
                "screen": "unknown",
                "key_elements": [],
                "possible_actions": []
            }
            
    async def analyze_screen_with_hierarchy(self, screenshot_path):
        """Analyze screen using both visual information and the UI hierarchy XML with hybrid approach.
        
        This uses:
        1. Vision model to extract raw visual information
        2. XML hierarchy for structured UI data
        3. Planning model to combine both for better reasoning
        
        Args:
            screenshot_path (str): Path to the screenshot image
            
        Returns:
            dict: Enhanced screen analysis with precise element information
        """
        try:
            # Get the XML hierarchy
            xml_hierarchy = await self.get_view_hierarchy()
            
            # If we couldn't get the hierarchy, fall back to regular screen analysis
            if not xml_hierarchy:
                print("Couldn't extract view hierarchy, falling back to vision-only analysis")
                return await self.analyze_screen_context(screenshot_path)
            
            # STEP 1: Use vision model to extract raw visual information
            base64_image = self.resize_image(screenshot_path)
            
            # Get basic visual description using vision model
            vision_kwargs = {
                "model": self.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": """Describe this Android screen capture in detail:
                            
Please identify and describe:
1. ALL visible text elements
2. ALL visible UI elements, buttons, and controls
3. ALL visible images, icons and their apparent purpose
4. The overall layout and arrangement

Focus on providing a COMPREHENSIVE, FACTUAL description with NO interpretation.
DO NOT make any assumptions about what actions should be taken.
"""},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 1200
            }
            
            # Make the API call to vision model
            vision_response = self.openai_client.chat.completions.create(**vision_kwargs)
            visual_description = vision_response.choices[0].message.content
            
            print("Visual information extracted, passing to planning model with XML data...")
            
            # STEP 2: Use planning model to combine visual and XML data
            system_prompt = """You are an expert Android UI analyzer with access to both visual and structural information.
You have two sources of information:
1. A detailed description of the current Android screen from visual analysis
2. The XML view hierarchy from the Android UI Automator

The XML hierarchy provides precise information about each UI element, including:
- bounds (coordinates in the format [left,top][right,bottom])
- text content
- content-desc (accessibility descriptions)
- resource-id (identifier for the element)
- class (type of UI component)
- clickable/scrollable/long-clickable (interactivity properties)

Your task is to combine visual understanding with the structured XML data to provide a detailed analysis.

For each important UI element, include its:
- Text or description
- Type (button, text field, etc.)
- Exact bounds as percentages of screen width/height
- Interactivity (clickable, scrollable, etc.)
- Best coordinates to tap it (center of element as percentages)

IMPORTANT: Your output MUST be a properly formatted JSON object as specified.
"""
            
            # Configure request parameters
            planning_kwargs = {
                "model": self.planning_model,  # Use the planning model for advanced reasoning
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""Here is a detailed visual description of the Android screen:

{visual_description}

And here is the XML view hierarchy:

{xml_hierarchy}

Analyze both sources of information to create a comprehensive understanding of the UI.

Return your analysis as a JSON object with the following structure:
{{
    "app": "Name of the app that appears to be open",
    "screen": "Specific screen/view within the app",
    "ui_elements": [
        {{
            "text": "Text content or description",
            "type": "Type of element (button, text field, etc.)",
            "bounds": {{"left": X1, "top": Y1, "right": X2, "bottom": Y2}},
            "center": {{"x_percent": X, "y_percent": Y}},
            "clickable": true/false,
            "important": true/false
        }},
        ...
    ],
    "input_fields": [
        {{
            "description": "What this field is for",
            "bounds": {{"left": X1, "top": Y1, "right": X2, "bottom": Y2}},
            "center": {{"x_percent": X, "y_percent": Y}}
        }},
        ...
    ],
    "recommended_actions": [
        {{
            "action": "Description of possible action",
            "target": {{"x_percent": X, "y_percent": Y}}
        }},
        ...
    ]
}}"""}
                ],
                "max_tokens": 3000  # Allow more tokens for detailed analysis
            }
            
            # Only add response_format for OpenAI
            if self.llm_provider == "openai":
                planning_kwargs["response_format"] = {"type": "json_object"}
            
            # Make the API call
            planning_response = self.openai_client.chat.completions.create(**planning_kwargs)
            response_text = planning_response.choices[0].message.content
            
            # Parse the JSON response
            try:
                # First try direct parsing
                enhanced_context = json.loads(response_text)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON
                try:
                    # Look for JSON-like content between curly braces
                    json_text = response_text[response_text.find('{'):response_text.rfind('}')+1]
                    if json_text:
                        enhanced_context = json.loads(json_text)
                    else:
                        raise ValueError("No JSON found in response")
                except (json.JSONDecodeError, ValueError):
                    print(f"Could not parse JSON from enhanced context, using fallback analysis")
                    # Fall back to regular screen analysis
                    return await self.analyze_screen_context(screenshot_path)
            
            # Update our understanding of the current app
            if "app" in enhanced_context and enhanced_context["app"] != "unknown":
                self.current_app = enhanced_context["app"].lower()
                
            # Cleanup old hierarchy files
            self.cleanup_old_hierarchies()
                
            return enhanced_context
            
        except Exception as e:
            print(f"Error in enhanced screen analysis: {e}")
            # Fall back to regular screen analysis
            return await self.analyze_screen_context(screenshot_path)
    
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
            # Configure request parameters
            kwargs = {
                "model": self.planning_model,
                "messages": [
                    {"role": "system", "content": """You are an AI assistant that analyzes Android tasks.
Your job is to determine if a task requires launching a specific app, and if so, which one."""},
                    {"role": "user", "content": f"""Analyze this Android task: "{task}"
                    
Does this task require launching a specific app? If so, which app?
Return a JSON object with these fields:
- requires_app_launch: boolean
- app_name: string (empty if no app needed)
- task_after_launch: string (what to do after launching the app)"""}
                ],
                "max_tokens": 500
            }
            
            # Only add response_format for OpenAI
            if self.llm_provider == "openai":
                kwargs["response_format"] = {"type": "json_object"}
            
            # Make the API call
            response = self.openai_client.chat.completions.create(**kwargs)
            response_text = response.choices[0].message.content
            
            # For OpenRouter, handle possible non-JSON responses
            if self.llm_provider == "openrouter":
                try:
                    # First try direct parsing
                    analysis = json.loads(response_text)
                except json.JSONDecodeError:
                    # If that fails, try to extract JSON
                    try:
                        # Look for JSON-like content between curly braces
                        json_text = response_text[response_text.find('{'):response_text.rfind('}')+1]
                        if json_text:
                            analysis = json.loads(json_text)
                        else:
                            raise ValueError("No JSON found in response")
                    except (json.JSONDecodeError, ValueError):
                        # If all parsing fails, try to interpret the response
                        print(f"Could not parse JSON from task analysis: {response_text[:100]}...")
                        
                        # Look for app mentions in the text
                        app_name = ""
                        requires_app = False
                        
                        # Common app keywords
                        app_keywords = ["twitter", "x", "gmail", "chrome", "youtube", "maps", "photos", "settings", "camera", "phone", "messages"]
                        
                        for app in app_keywords:
                            if app in response_text.lower():
                                app_name = app
                                requires_app = True
                                break
                                
                        # Check for "yes", "launch", etc. to determine if an app launch is needed
                        if "yes" in response_text.lower() or "launch" in response_text.lower() or "open" in response_text.lower():
                            requires_app = True
                        
                        # Create a fallback analysis
                        analysis = {
                            "requires_app_launch": requires_app,
                            "app_name": app_name,
                            "task_after_launch": task
                        }
            else:
                # For OpenAI, directly parse the JSON response
                analysis = json.loads(response_text)
            
            return analysis
        except Exception as e:
            print(f"Error analyzing task: {e}")
            return {
                "requires_app_launch": False,
                "app_name": "",
                "task_after_launch": task
            }
    
    async def run_task(self, task):
        """Run a task on the Android device using a hybrid vision-planning approach."""
        print(f"\nStarting task: {task}")
        print("Using hybrid vision-planning approach for better task completion")
        
        # Reset action tracking for new task
        self.recent_actions = []
        self.same_action_count = 0
        
        # Check if this is a search task
        is_search_task = False
        search_term = None
        if "search" in task.lower():
            search_parts = task.lower().split("search")
            if len(search_parts) > 1:
                search_term = search_parts[1].strip()
                # Remove common filler words from the beginning
                for word in ["for", "about", "the", "a"]:
                    if search_term.startswith(word + " "):
                        search_term = search_term[len(word):].strip()
                is_search_task = bool(search_term)
                print(f"Detected search task for term: '{search_term}'")
        
        # First, analyze if we need to launch an app
        print("Analyzing task to determine if an app needs to be launched...")
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
                
                # If this is a search task and we just launched the app, execute search sequence
                if is_search_task and search_term:
                    print(f"Executing search sequence for '{search_term}' in {app_name}...")
                    await asyncio.sleep(3)  # Wait for app to load
                    search_success = await self.search_text(search_term)
                    if search_success:
                        # Take a screenshot to verify results
                        screenshot_path = await self.capture_screen()
                        print(f"Search executed, now analyzing results")
                        analysis = await self.analyze_screen_with_llm(screenshot_path, 
                                                                      f"Did the search for '{search_term}' complete successfully? What results do you see?")
                        return f"Search complete: {analysis}"
            
        # For search tasks that don't need app launch, execute search sequence directly
        if is_search_task and search_term and not task_analysis.get("requires_app_launch", False):
            print(f"Executing direct search sequence for '{search_term}'...")
            search_success = await self.search_text(search_term)
            if search_success:
                # Take a screenshot to verify results
                screenshot_path = await self.capture_screen()
                print(f"Search executed, now analyzing results")
                analysis = await self.analyze_screen_with_llm(screenshot_path, 
                                                             f"Did the search for '{search_term}' complete successfully? What results do you see?")
                return f"Search complete: {analysis}"
            
        # Main task execution loop
        print("\nBeginning main task execution loop...")
        max_steps = 20  # Prevent infinite loops
        steps_taken = 0
        task_complete = False
        result = ""
        
        while steps_taken < max_steps and not task_complete:
            print(f"\n--- Step {steps_taken + 1}/{max_steps} ---")
            
            # Take a screenshot
            screenshot_path = await self.capture_screen()
            if not screenshot_path:
                return "Failed to capture screen"
            
            print(f"Captured screenshot: {screenshot_path}")
            
            # Use enhanced screen analysis with XML hierarchy
            print("Analyzing screen with hybrid approach (vision + XML + planning)...")
            enhanced_context = await self.analyze_screen_with_hierarchy(screenshot_path)
            print(f"\nScreen Analysis: app='{enhanced_context.get('app', 'Unknown')}', screen='{enhanced_context.get('screen', 'Unknown')}'")
            
            # Check if the enhanced context has recommended actions
            if 'recommended_actions' in enhanced_context and enhanced_context['recommended_actions']:
                print("\nRecommended Actions from analysis:")
                for i, rec_action in enumerate(enhanced_context['recommended_actions']):
                    print(f"  {i+1}. {rec_action.get('action', 'Unknown action')}")
            
            # Determine next action using hybrid approach (vision extracts, planning decides)
            print(f"Determining next action for task: {task}...")
            action = await self.determine_action(task, screenshot_path, enhanced_context)
            
            print(f"\nAction Plan:")
            print(f"  Analysis: {action.get('analysis', 'No analysis provided')}")
            print(f"  Action: {action.get('action', 'unknown')}")
            print(f"  Reasoning: {action.get('reasoning', 'No reasoning provided')}")
            
            # Check for repetitive actions
            action_key = self._get_action_key(action)
            if self.recent_actions and action_key == self.recent_actions[-1]:
                self.same_action_count += 1
                if self.same_action_count >= 3:
                    print(f"WARNING: Detected repetitive actions ({self.same_action_count} times). Trying alternative approach.")
                    
                    # Modify action based on the type to break the loop
                    if action.get("action") == "type":
                        # If stuck typing, try tapping the search button
                        print("Breaking out of typing loop by tapping search/enter button")
                        action = {
                            "analysis": "Breaking out of typing loop by tapping search/enter button",
                            "action": "tap",
                            "x_percent": 90,  # Bottom right corner where enter/search typically is
                            "y_percent": 90,
                            "is_task_complete": False,
                            "reasoning": "Tapping search/enter button after typing text"
                        }
                    elif action.get("action") == "tap":
                        # If stuck tapping, try scrolling to see more content
                        print("Breaking out of tapping loop by scrolling")
                        action = {
                            "analysis": "Breaking out of tapping loop by scrolling",
                            "action": "scroll",
                            "direction": "down",
                            "is_task_complete": False,
                            "reasoning": "Scrolling to see more content"
                        }
                    
                    # Reset counter after intervention
                    self.same_action_count = 0
            else:
                self.same_action_count = 0
            
            # Update recent actions (keep only last 3)
            self.recent_actions.append(action_key)
            if len(self.recent_actions) > 3:
                self.recent_actions.pop(0)
            
            # Execute the action
            print("Executing action...")
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
    
    def _get_action_key(self, action):
        """Generate a key to identify an action for detecting repetitive patterns."""
        action_type = action.get("action", "unknown")
        
        if action_type == "tap":
            # Consider taps at very similar coordinates as the same action
            try:
                x = float(action.get("x_percent", 0))
                y = float(action.get("y_percent", 0))
            except (TypeError, ValueError):
                x = 0
                y = 0
            return f"tap_{round(x/5)*5}_{round(y/5)*5}"  # Round to nearest 5%
            
        elif action_type == "type":
            # Consider typing the same text as the same action
            text = str(action.get("text", ""))
            # Make this more sensitive - if text contains similar words, consider it the same action
            # This helps catch cases where the agent is repeatedly typing similar search terms
            text_normalized = text.lower().strip()
            return f"type_{text_normalized}"
            
        elif action_type == "scroll":
            # Consider scrolling in the same direction as the same action
            direction = str(action.get("direction", "unknown"))
            return f"scroll_{direction}"
            
        elif action_type == "wait":
            return "wait"
            
        return action_type
    
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
                        print("Analyzing current screen context with enhanced XML data...")
                        enhanced_context = await self.analyze_screen_with_hierarchy(screenshot_path)
                        
                        print("\n📱 Enhanced Screen Analysis:")
                        print(f"App: {enhanced_context.get('app', 'Unknown')}")
                        print(f"Screen: {enhanced_context.get('screen', 'Unknown')}")
                        
                        # Display UI elements if available
                        if 'ui_elements' in enhanced_context and enhanced_context['ui_elements']:
                            print("\nUI Elements:")
                            for i, element in enumerate(enhanced_context['ui_elements'][:10]):  # Limit display
                                element_type = element.get('type', 'element')
                                element_text = element.get('text', 'Unnamed')
                                clickable = "👆 CLICKABLE" if element.get('clickable') else ""
                                center_x = element.get('center', {}).get('x_percent', 0)
                                center_y = element.get('center', {}).get('y_percent', 0)
                                print(f"  {i+1}. {element_text} ({element_type}) at {center_x}%, {center_y}% {clickable}")
                        
                        # Display input fields if available
                        if 'input_fields' in enhanced_context and enhanced_context['input_fields']:
                            print("\nInput Fields:")
                            for i, field in enumerate(enhanced_context['input_fields']):
                                description = field.get('description', 'Input field')
                                center_x = field.get('center', {}).get('x_percent', 0)
                                center_y = field.get('center', {}).get('y_percent', 0)
                                print(f"  {i+1}. {description} at {center_x}%, {center_y}%")
                        
                        # Display recommended actions if available
                        if 'recommended_actions' in enhanced_context and enhanced_context['recommended_actions']:
                            print("\nRecommended Actions:")
                            for i, action in enumerate(enhanced_context['recommended_actions']):
                                action_desc = action.get('action', 'Action')
                                target_x = action.get('target', {}).get('x_percent', 0)
                                target_y = action.get('target', {}).get('y_percent', 0)
                                print(f"  {i+1}. {action_desc} at {target_x}%, {target_y}%")
                        
                        # Fallback to displaying key elements and possible actions if the enhanced format doesn't have UI elements
                        if 'key_elements' in enhanced_context and enhanced_context['key_elements'] and not enhanced_context.get('ui_elements'):
                            print("\nKey Elements:")
                            for element in enhanced_context.get('key_elements', []):
                                print(f"  - {element}")
                                
                        if 'possible_actions' in enhanced_context and enhanced_context['possible_actions'] and not enhanced_context.get('recommended_actions'):
                            print("\nPossible Actions:")
                            for action in enhanced_context.get('possible_actions', []):
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
                    print("Sorry about that. Let me help you troubleshoot:")
                    
                    if "not completed within the maximum" in result:
                        print("The task hit the maximum number of steps (20). This usually happens when:")
                        print("1. The agent gets stuck in a loop (like repeatedly typing in a search bar)")
                        print("2. The task is too complex for the current step limit")
                        print("\nSuggestions:")
                        print("- Try breaking your task into smaller steps (e.g., 'launch zomato' then 'search for mcdonalds')")
                        print("- If search isn't working, try tapping on the search field first with 'tap <x> <y>'")
                    
                    print("\nYou can type 'context' to analyze the current screen state.")
                    print("Or use 'screenshot' to take a screenshot for your reference.")
        
        except KeyboardInterrupt:
            print("\nSession interrupted.")
        finally:
            self.stop_scrcpy()
            print("Session ended.")

    async def search_text(self, text):
        """Handle a complete search sequence - tap field, type text, tap search button."""
        print(f"\nExecuting search sequence for: {text}")
        
        # 1. First tap the search field (usually at the top of the screen)
        search_field_action = {
            "action": "tap",
            "x_percent": 50,  # Middle of top area where search fields typically are
            "y_percent": 10
        }
        await self.execute_action(search_field_action)
        await asyncio.sleep(1)  # Wait for field to focus
        
        # 2. Type the search text
        type_action = {
            "action": "type",
            "text": text
        }
        await self.execute_action(type_action)
        await asyncio.sleep(1)  # Wait for typing to complete
        
        # 3. Tap the search/enter button (usually bottom right of keyboard)
        search_button_action = {
            "action": "tap",
            "x_percent": 90,  # Bottom right corner where search/enter typically is
            "y_percent": 90
        }
        await self.execute_action(search_button_action)
        await asyncio.sleep(2)  # Wait for search results
        
        return True

    async def determine_action(self, task, screenshot_path, enhanced_context=None):
        """Use a hybrid approach to determine the next action:
        1. Vision model extracts raw visual information
        2. Planning model determines the best action based on visual data and task
        
        Args:
            task (str): The user's task description
            screenshot_path (str): Path to the screenshot image
            enhanced_context (dict, optional): Enhanced context from analyze_screen_with_hierarchy
            
        Returns:
            dict: Action plan with analysis and next action
        """
        try:
            # STEP 1: Use vision model to extract raw visual information
            base64_image = self.resize_image(screenshot_path)
            
            # Configure request for vision model to extract raw visual information
            vision_kwargs = {
                "model": self.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": """Describe this Android screen capture in detail:
                            
Please identify and describe:
1. ALL visible text elements
2. ALL visible UI elements, buttons, and controls
3. ALL visible images, icons and their apparent purpose
4. The overall layout and arrangement

Focus on providing a COMPREHENSIVE, FACTUAL description with NO interpretation.
DO NOT make any assumptions about what actions should be taken.
"""},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 1200
            }
            
            # Make the API call to vision model
            vision_response = self.openai_client.chat.completions.create(**vision_kwargs)
            visual_description = vision_response.choices[0].message.content
            
            print("Visual information extracted, passing to planning model for action determination...")
            
            # Create system prompt for planning model
            system_prompt = """You are an AI assistant controlling an Android device.
Your task is to analyze a detailed screen description and determine the best next action to take.

You have the following actions available:
1. tap(x_percent, y_percent): Tap on the screen at specified percentages of width and height
2. type(text): Type the specified text
3. scroll(direction): Scroll in the specified direction (up or down)
4. wait(seconds): Wait for the specified number of seconds
5. done: Indicate that the task is complete

IMPORTANT GUIDELINES FOR MULTI-FIELD FORMS (including email composition):
- NEVER try to type all information into a single field
- For forms (like email composition), follow this sequence:
  1. TAP the first field (recipient/to)
  2. TYPE only what belongs in that field
  3. TAP the next field
  4. TYPE only what belongs in that field
  5. Continue field by field
- For email specifically:
  - First find and tap the compose button (usually bottom-right corner)
  - Fill "To" field with ONLY the recipient's email address
  - Tap to move to subject field
  - Enter ONLY the subject
  - Tap to move to body field
  - Enter ONLY the message body
  - Find and tap the send button (usually top-right corner)

IMPORTANT GUIDELINES FOR SEARCHES:
- When you see a search bar, FIRST tap on it to focus it
- IMMEDIATELY after typing text in a search field, ALWAYS tap the search/enter button - this is CRITICAL
- Search/Enter buttons are almost always at coordinates 90% x, 90% y (bottom right of keyboard)
- Text field may show random suggestions like "Search 'pastries'" - these are just placeholders
- IGNORE placeholders - just tap the field, type your text, then tap search/enter
- Don't type the same text multiple times - if you've typed it once, just tap search/enter
- If typing the same text 3+ times without results, try tapping elsewhere then try a different approach

SEARCH ACTION SEQUENCE:
1. TAP on search field (usually near top of screen)
2. TYPE the search text
3. TAP on search/enter button (90% x, 90% y)

You will respond with a JSON object that has these fields:
- analysis: Brief description of what you see on the screen and your reasoning
- action: One of ["tap", "type", "scroll", "wait", "done"]
- x_percent: (For tap) X-coordinate as percentage (0-100)
- y_percent: (For tap) Y-coordinate as percentage (0-100)
- text: (For type) Text to type
- direction: (For scroll) Direction to scroll ("up" or "down")
- wait_time: (For wait) Number of seconds to wait
- is_task_complete: boolean - true if the task is complete, false otherwise
- reasoning: Your reasoning for choosing this action
"""
            
            # Add XML hierarchy data to the user prompt if available
            user_prompt = f"""Task: {task}

Here is a detailed description of the current Android screen:

{visual_description}

Based on this description and the task, determine the best next action to take.
"""

            # Add enhanced context XML data if available
            if enhanced_context:
                user_prompt += "\n\nAdditional UI element information from XML analysis:\n"
                
                # Add UI elements information
                if "ui_elements" in enhanced_context and enhanced_context["ui_elements"]:
                    user_prompt += "\nUI ELEMENTS:\n"
                    for i, element in enumerate(enhanced_context["ui_elements"][:10]):  # Limit to prevent prompt too long
                        center_x = element.get("center", {}).get("x_percent", 0)
                        center_y = element.get("center", {}).get("y_percent", 0)
                        user_prompt += f"{i+1}. {element.get('text', 'Unnamed')} ({element.get('type', 'element')}): tap at {center_x}%, {center_y}%"
                        if element.get("clickable") == True:
                            user_prompt += " [CLICKABLE]"
                        user_prompt += "\n"
                
                # Add input fields information
                if "input_fields" in enhanced_context and enhanced_context["input_fields"]:
                    user_prompt += "\nINPUT FIELDS:\n"
                    for i, field in enumerate(enhanced_context["input_fields"]):
                        center_x = field.get("center", {}).get("x_percent", 0)
                        center_y = field.get("center", {}).get("y_percent", 0)
                        user_prompt += f"{i+1}. {field.get('description', 'Input field')}: tap at {center_x}%, {center_y}%\n"
                
                # Add recommended actions
                if "recommended_actions" in enhanced_context and enhanced_context["recommended_actions"]:
                    user_prompt += "\nRECOMMENDED ACTIONS:\n"
                    for i, rec_action in enumerate(enhanced_context["recommended_actions"]):
                        target_x = rec_action.get("target", {}).get("x_percent", 0)
                        target_y = rec_action.get("target", {}).get("y_percent", 0)
                        user_prompt += f"{i+1}. {rec_action.get('action', 'Action')}: tap at {target_x}%, {target_y}%\n"
                
                user_prompt += "\nUSE THESE EXACT COORDINATES when deciding where to tap, as they come from the actual UI structure of the app."
            
            # STEP 2: Use planning model to determine next action
            planning_kwargs = {
                "model": self.planning_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 1500
            }
            
            # Only add response_format for OpenAI
            if self.llm_provider == "openai":
                planning_kwargs["response_format"] = {"type": "json_object"}
            
            # Make the API call to planning model
            planning_response = self.openai_client.chat.completions.create(**planning_kwargs)
            response_text = planning_response.choices[0].message.content
            
            # Parse the response for action determination
            try:
                # First try direct parsing
                action_plan = json.loads(response_text)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON using a more lenient approach
                try:
                    # Look for JSON-like content between curly braces
                    json_text = response_text[response_text.find('{'):response_text.rfind('}')+1]
                    if json_text:
                        action_plan = json.loads(json_text)
                    else:
                        raise ValueError("No JSON found in response")
                except (json.JSONDecodeError, ValueError):
                    # If all parsing fails, create a fallback action
                    print(f"Could not parse JSON from action response, using fallback text processing")
                    
                    # Attempt to interpret the response as best as possible
                    action_type = "wait"
                    if "tap" in response_text.lower():
                        action_type = "tap"
                        # Default to center of screen if we can't extract coordinates
                        x_percent = 50
                        y_percent = 50
                    elif "type" in response_text.lower():
                        action_type = "type"
                        # Try to find quoted text to type
                        text_match = response_text.find('"') 
                        if text_match != -1:
                            text_end = response_text.find('"', text_match+1)
                            if text_end != -1:
                                text_to_type = response_text[text_match+1:text_end]
                            else:
                                text_to_type = ""
                        else:
                            text_to_type = ""
                    elif "scroll" in response_text.lower():
                        action_type = "scroll"
                        direction = "down" if "down" in response_text.lower() else "up"
                        
                    # Create a best-effort action plan
                    action_plan = {
                        "analysis": "Extracted from text response",
                        "action": action_type,
                        "is_task_complete": "complete" in response_text.lower() or "done" in response_text.lower(),
                        "reasoning": "Fallback action determined from text response"
                    }
                    
                    # Add action-specific fields
                    if action_type == "tap":
                        action_plan["x_percent"] = x_percent
                        action_plan["y_percent"] = y_percent
                    elif action_type == "type":
                        action_plan["text"] = text_to_type
                    elif action_type == "scroll":
                        action_plan["direction"] = direction
                    elif action_type == "wait":
                        action_plan["wait_time"] = 2
            
            # Ensure numeric values are actually numbers, not strings
            if action_plan.get("action") == "tap":
                try:
                    action_plan["x_percent"] = float(action_plan.get("x_percent", 50))
                    action_plan["y_percent"] = float(action_plan.get("y_percent", 50))
                except (ValueError, TypeError):
                    action_plan["x_percent"] = 50
                    action_plan["y_percent"] = 50
                    
            elif action_plan.get("action") == "wait":
                try:
                    action_plan["wait_time"] = float(action_plan.get("wait_time", 2))
                except (ValueError, TypeError):
                    action_plan["wait_time"] = 2
            
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
        """Execute the specified action using adb commands."""
        try:
            action_type = action.get("action")
            
            if action_type == "tap":
                x_percent = action.get("x_percent", 50)
                y_percent = action.get("y_percent", 50)
                
                # Get the screen dimensions
                dimensions_output = subprocess.check_output([self.adb_path, "shell", "wm", "size"]).decode().strip()
                dimensions = dimensions_output.split(":")[-1].strip()
                width, height = map(int, dimensions.split("x"))
                
                # Calculate actual pixel coordinates
                x = int(width * x_percent / 100)
                y = int(height * y_percent / 100)
                
                print(f"Tapped at coordinates: {x}, {y} (from {x_percent}%, {y_percent}%)")
                subprocess.run([self.adb_path, "shell", "input", "tap", str(x), str(y)])
                return True
                
            elif action_type == "type":
                text = action.get("text", "")
                print(f"Typed text: {text}")
                
                # Replace spaces with %s for adb input text command
                text_escaped = text.replace(" ", "%s")
                subprocess.run([self.adb_path, "shell", "input", "text", text_escaped])
                
                # Check if this might be a search operation - if so, automatically tap enter
                if any(term in text.lower() for term in ["search", "find", "look"]) or len(text.split()) <= 3:
                    await asyncio.sleep(0.5)  # Brief pause before hitting enter
                    print("Search text detected - automatically tapping Enter key")
                    # Tap the enter key (or search button)
                    dimensions_output = subprocess.check_output([self.adb_path, "shell", "wm", "size"]).decode().strip()
                    dimensions = dimensions_output.split(":")[-1].strip()
                    width, height = map(int, dimensions.split("x"))
                    # Calculate actual pixel coordinates - enter button at bottom right
                    x = int(width * 0.9)
                    y = int(height * 0.9)
                    subprocess.run([self.adb_path, "shell", "input", "tap", str(x), str(y)])
                
                return True
                
            elif action_type == "scroll":
                direction = action.get("direction", "down")
                print(f"Scrolling {direction}")
                
                # Get the screen dimensions
                dimensions_output = subprocess.check_output([self.adb_path, "shell", "wm", "size"]).decode().strip()
                dimensions = dimensions_output.split(":")[-1].strip()
                width, height = map(int, dimensions.split("x"))
                
                # Calculate swipe coordinates
                x_start = width // 2
                x_end = width // 2
                
                if direction == "down":
                    y_start = height * 2 // 3
                    y_end = height // 3
                else:  # up
                    y_start = height // 3
                    y_end = height * 2 // 3
                
                subprocess.run([
                    self.adb_path, "shell", "input", "swipe",
                    str(x_start), str(y_start), str(x_end), str(y_end), "300"
                ])
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

async def main():
    # Check for required API keys
    missing_keys = []
    if "OPENAI_API_KEY" not in os.environ:
        missing_keys.append("OPENAI_API_KEY")
    if "OPENROUTER_API_KEY" not in os.environ:
        missing_keys.append("OPENROUTER_API_KEY")
    
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
    
    # Prompt for LLM provider choice
    print("\n===== LLM Provider Selection =====")
    print("1. OpenAI (default)")
    print("2. OpenRouter")
    llm_choice = input("Please choose your LLM provider (1/2): ").strip()
    
    # Set the LLM provider based on user choice
    llm_provider = "openai"  # Default
    if llm_choice == "2":
        llm_provider = "openrouter"
    
    print(f"\nStarting the Simple Android Agent with {llm_provider.upper()} as the LLM provider...\n")
    
    agent = SimpleAndroidAgent(llm_provider=llm_provider)
    await agent.interactive_session()

if __name__ == "__main__":
    asyncio.run(main())
