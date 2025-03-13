import asyncio
import os
import subprocess
import time
import json
import base64
import glob
import re
import uiautomator2 as u2
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
        self.min_screenshot_interval = 2.0  # Minimum seconds between screenshots
        self.screenshot_count = 0
        self.max_saved_screenshots = 5  # Only keep this many recent screenshots
        
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
            import subprocess
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
                width, height = self.device.window_size()
                print(f"Connected successfully. Screen size: {width}x{height}")
                
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
        
        # Check for direct app opening first - make this much simpler
        for app_name in self.common_packages:
            if f"open {app_name}" in task_lower or f"launch {app_name}" in task_lower or f"start {app_name}" in task_lower:
                # Check if this is a complex task with more actions
                if " and " in task_lower or " then " in task_lower:
                    # Complex task that needs vision guidance
                    continue
                
                # Simple app launch - handle directly
                return {
                    "type": "launch_app",
                    "app_name": app_name,
                    "package_name": self.common_packages[app_name]
                }
        
        # Also handle "open app X" pattern
        for pattern in [r'open (?:the )?(?:app )?(\w+)', r'launch (?:the )?(?:app )?(\w+)', r'start (?:the )?(?:app )?(\w+)']:
            match = re.search(pattern, task_lower)
            if match:
                app_name = match.group(1).strip()
                if app_name in self.common_packages:
                    return {
                        "type": "launch_app",
                        "app_name": app_name,
                        "package_name": self.common_packages[app_name]
                    }
        
        # If we get here, this requires vision guidance
        return None
    
    async def take_screenshot(self):
        """Take a screenshot and return the path."""
        # Check if we need to wait before taking another screenshot
        current_time = time.time()
        time_since_last = current_time - self.last_action_time
        
        if time_since_last < self.min_screenshot_interval:
            wait_time = self.min_screenshot_interval - time_since_last
            print(f"Waiting {wait_time:.1f}s before taking next screenshot...")
            await asyncio.sleep(wait_time)
        
        # Take the screenshot
        filename = f"screenshot_{int(time.time())}.png"
        try:
            self.device.screenshot(filename)
            self.last_action_time = time.time()
            self.screenshot_count += 1
            
            # Clean up old screenshots after threshold
            if self.screenshot_count % 3 == 0:  # Every 3 screenshots
                self.cleanup_old_screenshots()
                
            return filename
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            return None
    
    def cleanup_old_screenshots(self):
        """Remove older screenshots to avoid disk space issues."""
        try:
            # Get all screenshot files
            screenshot_files = glob.glob("screenshot_*.png")
            
            # Sort by creation time (oldest first)
            screenshot_files.sort(key=lambda x: os.path.getctime(x))
            
            # Delete oldest files if there are too many
            if len(screenshot_files) > self.max_saved_screenshots:
                files_to_delete = screenshot_files[:-self.max_saved_screenshots]
                for file in files_to_delete:
                    try:
                        os.remove(file)
                        print(f"Removed old screenshot: {file}")
                    except Exception as e:
                        print(f"Error removing file {file}: {e}")
        except Exception as e:
            print(f"Error during screenshot cleanup: {e}")
    
    def is_complex_task(self, task):
        """Determine if a task requires multiple steps beyond app launch."""
        task_lower = task.lower()
        
        # Check for phrases that indicate complex tasks
        complex_indicators = [
            " and ", " then ", " after ", " followed ", 
            "search", "compose", "send", "write", "click", "tap",
            "scroll", "find", "look", "input", "type", "enter"
        ]
        
        return any(indicator in task_lower for indicator in complex_indicators)

    def extract_post_launch_task(self, full_task, app_name):
        """Extract the part of the task that comes after launching the app."""
        task_lower = full_task.lower()
        
        # Try to find where the post-launch instructions begin
        launch_patterns = [
            f"open {app_name} and ", 
            f"launch {app_name} and ",
            f"start {app_name} and ",
            f"open {app_name} then ",
            f"launch {app_name} then "
        ]
        
        for pattern in launch_patterns:
            if pattern in task_lower:
                # Return everything after the pattern
                return task_lower.split(pattern, 1)[1]
        
        # Fallback - just remove the app launch part generically
        for prefix in [f"open {app_name}", f"launch {app_name}", f"start {app_name}"]:
            if prefix in task_lower:
                remaining = task_lower.replace(prefix, "", 1).strip()
                # Remove connecting words at the beginning
                for connector in ["and", "then", "to"]:
                    if remaining.startswith(connector):
                        remaining = remaining[len(connector):].strip()
                return remaining
        
        # If we can't extract a clear post-launch task, return the original
        return full_task
    
    async def wait_after_action(self, action):
        """Wait an appropriate amount of time after executing an action."""
        if action in ["click", "back", "launch_app"]:
            await asyncio.sleep(2.5)  # Longer delay for navigation
        elif action == "input_text":
            await asyncio.sleep(1.5)  # Medium delay after text input
        else:
            await asyncio.sleep(1.0)  # Basic delay

    async def analyze_screenshot_with_context(self, screenshot_path, task, context="", previous_stages=None, task_analysis=None):
        """Analyze screenshot with awareness of task context and previous stages."""
        if not os.path.exists(screenshot_path):
            print(f"Screenshot not found: {screenshot_path}")
            return None
        
        try:
            # Convert screenshot to base64
            with open(screenshot_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")
            
            # Build context information to help the vision model
            context_info = ""
            if context:
                context_info += f"\nCONTEXT: {context}\n"
            
            if task_analysis:
                context_info += f"\nTASK ANALYSIS: {task_analysis}\n"
            
            if previous_stages and any(stage.get("completed", False) for stage in previous_stages):
                context_info += "\nCOMPLETED STEPS:\n"
                for i, stage in enumerate(previous_stages):
                    if stage.get("completed", False):
                        if stage["type"] == "direct_action" and stage["action"] == "launch_app":
                            context_info += f"- Successfully launched {stage['app_name']}\n"
                        elif stage["type"] == "vision_guided":
                            context_info += f"- Completed vision-guided stage: {stage['description']}\n"
            
            system_prompt = """
            You are an expert at analyzing Android screenshots and determining exactly what actions to take.
            
            For each screenshot, you need to:
            1. Identify what app is currently visible
            2. Determine the exact next action to take to complete the user's task
            3. Provide precise coordinates (as percentages) where to click or interact
            
            The available actions are:
            - "click": Click at a specific position
            - "input_text": Type text (requires position to click first)
            - "scroll": Scroll down for more content
            - "back": Press the back button
            - "home": Press the home button
            - "wait": For explicitly waiting for content to load (new screens, etc.)
            
            IMPORTANT GUIDELINES:
            
            1. FOCUS ON THE SPECIFIC TASK PORTION described, not the entire original task
            2. The app may already be launched - focus on the REMAINING actions needed
            3. For search tasks, you need to:
               - First click the search field or icon (usually magnifying glass)
               - Then use input_text to enter the search query
               - Then possibly click a search button or suggestion
            
            4. For typing tasks:
               - First click precisely on the input field 
               - Then use input_text with the exact text needed
               - Include any submit/send button actions afterward
               
            5. Pay attention to the CONTEXT information, which provides:
               - What app has already been launched
               - What specific task portion you need to complete
               - What steps have already been completed
            
            Return ONLY valid JSON in this format:
            {
              "app_name": "The visible app (e.g., Gmail, Chrome, Home Screen)",
              "action": "click, input_text, scroll, back, home, or wait",
              "position": {"x_percent": 50, "y_percent": 50},
              "text": "Text to input if action is input_text",
              "parameters": {"app_name": "App name if needed", "time": 3},
              "reasoning": "Brief explanation of why you chose this action",
              "is_task_complete": false
            }
            
            Only set is_task_complete to true when you're confident the entire CURRENT TASK PORTION has been completed successfully.
            """
            
            user_prompt = f"""
            Task: {task}
            {context_info}
            
            Analyze this Android screenshot and determine the next action to take to complete this specific task or task portion.
            Be very precise about the position to click (x_percent, y_percent).
            For text input, you MUST provide both the position to click AND the text to enter.
            """
            
            # Call the OpenAI API
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]}
                ],
                response_format={"type": "json_object"},
                max_tokens=1000
            )
            
            # Parse the response
            analysis = json.loads(response.choices[0].message.content)
            print(f"Analysis: {json.dumps(analysis, indent=2)}")
            
            return analysis
        except Exception as e:
            print(f"Error analyzing screenshot: {e}")
            return None
            
    async def run_vision_guided_stage(self, task_description, context="", previous_stages=None, task_analysis=None):
        """Run the vision-guided part of a complex task."""
        steps_taken = 0
        max_steps = 15
        results = []
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        while steps_taken < max_steps:
            steps_taken += 1
            
            try:
                # Take screenshot
                print(f"\nVision Step {steps_taken}: Taking screenshot...")
                screenshot = await self.take_screenshot()
                
                if not screenshot:
                    results.append("Failed to take screenshot")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        results.append("Too many consecutive errors. Aborting task.")
                        break
                    continue
                
                # Analyze screenshot with enhanced context awareness
                print(f"Analyzing screenshot to determine next action...")
                analysis = await self.analyze_screenshot_with_context(
                    screenshot, 
                    task_description, 
                    context=context,
                    previous_stages=previous_stages,
                    task_analysis=task_analysis
                )
                
                if not analysis:
                    results.append("Failed to analyze screenshot")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        results.append("Too many consecutive errors. Aborting task.")
                        break
                    continue
                
                # Execute action
                action = analysis.get("action", "unknown")
                print(f"Executing action: {action}")
                result = await self.execute_action(analysis)
                results.append(result)
                
                # Reset consecutive errors counter on success
                consecutive_errors = 0
                
                # Check if task is complete
                if analysis.get("is_task_complete", False):
                    print("Task stage marked as complete by the vision model")
                    break
                
                # Use adaptive delay based on the action
                await self.wait_after_action(action)
            
            except Exception as e:
                error_msg = f"Error in vision step {steps_taken}: {e}"
                print(error_msg)
                results.append(error_msg)
                
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    results.append("Too many consecutive errors. Aborting this stage.")
                    break
        
        if steps_taken >= max_steps:
            results.append("Maximum steps reached, task may be incomplete")
        
        return "\n".join(results)

    async def execute_action(self, action_data):
        """Execute the recommended action from the vision analysis."""
        if not action_data:
            return "No action to execute"
        
        action = action_data.get("action", "")
        position = action_data.get("position", {})
        text = action_data.get("text", "")
        parameters = action_data.get("parameters", {})
        reasoning = action_data.get("reasoning", "")
        
        print(f"Reasoning: {reasoning}")
        
        try:
            if action == "click":
                width, height = self.device.window_size()
                x = int(width * position.get("x_percent", 50) / 100)
                y = int(height * position.get("y_percent", 50) / 100)
                print(f"Clicking at ({x}, {y})")
                self.device.click(x, y)
                return f"Clicked at ({x}, {y})"
            
            elif action == "input_text":
                # First click to focus if position provided
                if position:
                    width, height = self.device.window_size()
                    x = int(width * position.get("x_percent", 50) / 100)
                    y = int(height * position.get("y_percent", 50) / 100)
                    print(f"Clicking to focus at ({x}, {y})")
                    self.device.click(x, y)
                    await asyncio.sleep(1.5)  # Wait longer for keyboard to appear
                
                if text:
                    print(f"🔤 Typing text: '{text}'")
                    
                    # Try multiple methods with clear feedback
                    success = False
                    
                    # Method 1: Try clearing field first (may help with input fields)
                    try:
                        print("Trying to clear field first...")
                        self.device.clear_text()
                        await asyncio.sleep(0.5)
                    except Exception as e0:
                        print(f"Field clearing failed (this is often normal): {e0}")
                    
                    # Method 2: Direct send_keys with better error handling
                    if not success:
                        try:
                            print("Attempting direct text input...")
                            self.device.send_keys(text)
                            # Verify text was entered by checking UI elements
                            await asyncio.sleep(1.0)
                            success = True
                            print("✓ Text input successful using send_keys")
                        except Exception as e1:
                            print(f"Direct input failed: {e1}")
                    
                    # Method 3: Shell input text with error handling
                    if not success:
                        try:
                            print("Attempting shell text input...")
                            # Escape special characters
                            escaped_text = text.replace("'", "\\'").replace('"', '\\"')
                            self.device.shell(f"input text '{escaped_text}'")
                            await asyncio.sleep(1.0)
                            success = True
                            print("✓ Text input successful using shell command")
                        except Exception as e2:
                            print(f"Shell input failed: {e2}")
                    
                    # Method 4: Character-by-character with verification
                    if not success:
                        try:
                            print("Trying character-by-character input...")
                            for char in text:
                                self.device.send_keys(char)
                                await asyncio.sleep(0.3)  # Slower typing for reliability
                            success = True
                            print("✓ Text input successful character by character")
                        except Exception as e3:
                            print(f"Character input failed: {e3}")
                    
                    # As last resort, try tapping Enter/Done after input
                    try:
                        print("Tapping Enter key to finalize input...")
                        self.device.press("enter")
                        await asyncio.sleep(0.5)
                    except Exception as e4:
                        print(f"Enter key failed (may not be needed): {e4}")
                    
                    if success:
                        return f"Entered text: '{text}'"
                    else:
                        return "⚠️ Failed to input text with all methods"
            
            elif action == "scroll":
                width, height = self.device.window_size()
                print("Scrolling down")
                self.device.swipe(width/2, height*0.7, width/2, height*0.3)
                return "Scrolled down"
            
            elif action == "back":
                print("Pressing back button")
                self.device.press("back")
                return "Pressed back button"
            
            elif action == "home":
                print("Pressing home button")
                self.device.press("home")
                return "Pressed home button"
                
            elif action == "launch_app":
                app_name = parameters.get("app_name", "")
                if not app_name:
                    return "No app name provided for launch_app action"
                
                app_name_lower = app_name.lower()
                if app_name_lower in self.common_packages:
                    package_name = self.common_packages[app_name_lower]
                    print(f"Launching app: {app_name} ({package_name})")
                    self.device.app_start(package_name)
                    return f"Launched app: {app_name}"
                else:
                    # If no known package, go to home and try to find it
                    print(f"Unknown app: {app_name}. Going to home screen to search.")
                    self.device.press("home")
                    await asyncio.sleep(1)
                    # Try to find the app in the app drawer
                    width, height = self.device.window_size()
                    # Swipe up to open app drawer
                    self.device.swipe(width/2, height*0.8, width/2, height*0.2)
                    return f"Went to home screen to look for {app_name}"
                
            elif action == "wait":
                wait_time = parameters.get("time", 3)
                print(f"Waiting for {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                return f"Waited for {wait_time} seconds"
            
            else:
                return f"Unknown action: {action}"
        
        except Exception as e:
            error_msg = f"Action failed: {e}"
            print(error_msg)
            return error_msg
            
    async def analyze_screenshot(self, screenshot_path, task):
        """Send screenshot to GPT-4o for analysis and get action recommendation."""
        # For backward compatibility, just call the context-aware version
        return await self.analyze_screenshot_with_context(screenshot_path, task)
            
    async def plan_task(self, task):
        """Use the LLM to break down the task into steps and determine if direct actions are possible."""
        try:
            system_prompt = """
            You are an expert at planning Android automation tasks. Your job is to analyze a user's request and break it down into executable steps.
            
            For each task, determine:
            1. If it involves launching a specific app
            2. What steps should be taken after the app is launched
            3. Whether any parts can be executed directly without vision guidance
            
            Return ONLY valid JSON in this format:
            {
              "analysis": "Brief analysis of what the task involves",
              "has_app_launch": true/false,
              "app_name": "Name of the app to launch (only if has_app_launch is true)",
              "requires_vision_after_launch": true/false,
              "post_launch_steps": "Description of what needs to be done after app launch",
              "pure_vision_task": "Full task description if no direct actions possible"
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
            # Return a fallback plan that uses vision guidance for everything
            return {
                "analysis": "Failed to plan with LLM, using vision guidance",
                "has_app_launch": False,
                "requires_vision_after_launch": False,
                "pure_vision_task": task
            }
    
    async def run_task(self, task):
        """Execute a task using LLM planning and vision-guided automation."""
        print(f"Starting task: {task}")
        
        # Reset counters
        self.screenshot_count = 0
        self.last_action_time = 0
        
        # Use LLM to plan the task
        plan = await self.plan_task(task)
        
        task_stages = []
        
        # Build stages based on the plan
        if plan.get("has_app_launch", False) and plan.get("app_name"):
            app_name = plan["app_name"].lower()
            
            # Verify the app exists in our dictionary
            if app_name in self.common_packages:
                package_name = self.common_packages[app_name]
                
                # Add app launch as first stage
                task_stages.append({
                    "type": "direct_action",
                    "action": "launch_app",
                    "app_name": app_name,
                    "package_name": package_name,
                    "completed": False
                })
                
                # If there are post-launch steps, add them as a vision stage
                if plan.get("requires_vision_after_launch", False) and plan.get("post_launch_steps"):
                    task_stages.append({
                        "type": "vision_guided",
                        "description": plan["post_launch_steps"],
                        "context": f"The {app_name} app has already been launched.",
                        "completed": False
                    })
            else:
                # App not in our database, use pure vision
                print(f"⚠️ App '{app_name}' not in database, using vision guidance")
                task_stages.append({
                    "type": "vision_guided", 
                    "description": task,
                    "completed": False
                })
        else:
            # Pure vision task
            task_stages.append({
                "type": "vision_guided", 
                "description": plan.get("pure_vision_task", task),
                "completed": False
            })
        
        # Execute all stages in sequence
        results = []
        for i, stage in enumerate(task_stages):
            if stage["type"] == "direct_action" and stage["action"] == "launch_app":
                # Handle direct app launch
                app_name = stage["app_name"]
                package_name = stage["package_name"]
                
                print(f"📱 Stage {i+1}/{len(task_stages)}: Launching {app_name} ({package_name}) directly")
                try:
                    self.device.app_start(package_name)
                    await asyncio.sleep(2)  # Wait for app to start
                    print(f"✅ Successfully launched {app_name}")
                    stage["completed"] = True
                    results.append(f"Launched {app_name}")
                except Exception as e:
                    print(f"⚠️ Direct app launch failed: {e}")
                    # Don't mark as completed if failed
            
            elif stage["type"] == "vision_guided":
                # Handle vision-guided part
                print(f"📸 Stage {i+1}/{len(task_stages)}: Using vision guidance for: {stage['description']}")
                
                # Execute vision-guided steps with proper context
                vision_result = await self.run_vision_guided_stage(
                    stage["description"],
                    context=stage.get("context", ""),
                    previous_stages=task_stages[:i],
                    task_analysis=plan.get("analysis", "")
                )
                results.append(vision_result)
                stage["completed"] = True
        
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
            
            # Verify that basic device operations work
            try:
                test_screenshot = await self.take_screenshot()
                if not test_screenshot or not os.path.exists(test_screenshot):
                    print("Failed to take a test screenshot. Device might not be properly connected.")
                    return
                print("Successfully took a test screenshot.")
            except Exception as e:
                print(f"Device test failed: {e}")
                print("Please ensure your device is properly connected and authorized.")
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
            self.cleanup_old_screenshots()
            print("Session ended.")

async def main():
    if "OPENAI_API_KEY" not in os.environ:
        print("Error: OPENAI_API_KEY not set.")
        return
    
    agent = AndroidVisionAgent()
    await agent.interactive_session()

if __name__ == "__main__":
    asyncio.run(main())