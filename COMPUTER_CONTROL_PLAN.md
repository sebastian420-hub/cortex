# Computer Control & Browser Automation Plan for Cortex

## Executive Summary

This document outlines a comprehensive plan to add computer control capabilities to Cortex, enabling it to:
1. **Control the mouse and keyboard** (GUI automation)
2. **Automate browser interactions** (web automation)
3. **Take screenshots and analyze screen content** (computer vision)
4. **Control applications and windows** (window management)

**Safety is paramount**: All computer control features require explicit user permission and include fail-safes to prevent runaway automation.

---

## 1. Architecture Overview

### 1.1 System Components

```
cortex/
├── tools/
│   └── automation/
│       ├── __init__.py
│       ├── base.py                    # AutomationTool base class
│       ├── computer_control.py        # Mouse/keyboard control
│       ├── browser_automation.py      # Browser control
│       ├── screenshot.py              # Screen capture & analysis
│       ├── window_manager.py          # Window control
│       └── schemas.py                 # Tool schemas
├── core/
│   └── automation/
│       ├── safety.py                  # Safety controls & fail-safes
│       ├── permissions.py             # Permission management
│       ├── session.py                 # Automation session tracking
│       └── audit.py                   # Audit logging
└── ui/
    └── automation/
        ├── overlay.py                  # Visual feedback overlay
        └── status.py                 # Automation status display
```

### 1.2 Safety Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER REQUEST                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              PERMISSION VALIDATION LAYER                      │
│  • Is automation enabled in config?                         │
│  • Does user have required permission level?                  │
│  • Is target within authorized scope?                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   SAFETY CONTROLS                           │
│  • Fail-safe corner detection (mouse in corner = stop)         │
│  • Maximum action limits (prevent infinite loops)            │
│  • Rate limiting (prevent system overload)                    │
│  • Screenshot verification (confirm actions)                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  ACTION EXECUTION                           │
│  • Execute with timeout protection                            │
│  • Capture before/after screenshots                          │
│  • Log all actions to audit trail                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  RESULT & AUDIT                             │
│  • Return results to user                                     │
│  • Update audit log                                           │
│  • Release any locks/resources                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Computer Control Tools

### 2.1 Mouse & Keyboard Control

#### 2.1.1 Mouse Control Tool
```python
class MouseControlTool(AutomationTool):
    """Control mouse movements and clicks"""
    
    default_timeout = 30
    timeout_category = "automation"
    
    def execute(
        self,
        action: str,  # "move", "click", "double_click", "right_click", "drag", "scroll"
        x: int = None,
        y: int = None,
        duration: float = 0.5,
        button: str = "left",  # "left", "right", "middle"
        clicks: int = 1,
        interval: float = 0.0,
        scroll_amount: int = None,
        image_target: str = None,  # Path to image to find and click
    ) -> Dict[str, Any]:
        """
        Control mouse with safety checks.
        
        Examples:
            # Move mouse to coordinates
            mouse_control(action="move", x=500, y=300)
            
            # Click at current position
            mouse_control(action="click")
            
            # Find and click image
            mouse_control(action="click", image_target="button.png")
            
            # Scroll down
            mouse_control(action="scroll", scroll_amount=-500)
        """
```

#### 2.1.2 Keyboard Control Tool
```python
class KeyboardControlTool(AutomationTool):
    """Control keyboard input"""
    
    def execute(
        self,
        action: str,  # "type", "press", "hotkey", "hold"
        text: str = None,
        keys: List[str] = None,
        interval: float = 0.01,
        presses: int = 1,
    ) -> Dict[str, Any]:
        """
        Control keyboard with safety checks.
        
        Examples:
            # Type text
            keyboard_control(action="type", text="Hello World")
            
            # Press single key
            keyboard_control(action="press", keys=["enter"])
            
            # Hotkey combination
            keyboard_control(action="hotkey", keys=["ctrl", "c"])
            
            # Hold and release
            keyboard_control(action="hold", keys=["shift"])
        """
```

### 2.2 Screenshot & Screen Analysis

```python
class ScreenshotTool(AutomationTool):
    """Capture and analyze screen content"""
    
    def execute(
        self,
        action: str = "capture",  # "capture", "region", "window", "analyze"
        region: Tuple[int, int, int, int] = None,  # (left, top, width, height)
        window_title: str = None,
        save_path: str = None,
        analyze_text: bool = False,
        find_image: str = None,  # Find image on screen
    ) -> Dict[str, Any]:
        """
        Capture and analyze screen.
        
        Examples:
            # Full screenshot
            screenshot(action="capture")
            
            # Region screenshot
            screenshot(action="region", region=(100, 100, 500, 300))
            
            # Find image on screen
            screenshot(action="analyze", find_image="submit_button.png")
        """
```

### 2.3 Window Management

```python
class WindowManagerTool(AutomationTool):
    """Control application windows"""
    
    def execute(
        self,
        action: str,  # "list", "focus", "move", "resize", "minimize", "maximize", "close"
        window_title: str = None,
        window_id: int = None,
        position: Tuple[int, int] = None,
        size: Tuple[int, int] = None,
    ) -> Dict[str, Any]:
        """
        Manage application windows.
        
        Examples:
            # List all windows
            window_manager(action="list")
            
            # Focus specific window
            window_manager(action="focus", window_title="Chrome")
            
            # Resize and move window
            window_manager(action="resize", window_title="Notepad", size=(800, 600))
        """
```

---

## 3. Browser Automation Tools

### 3.1 Browser Control

```python
class BrowserAutomationTool(AutomationTool):
    """Control web browser for automation"""
    
    def execute(
        self,
        action: str,  # "launch", "navigate", "click", "type", "scroll", "screenshot", "close"
        url: str = None,
        selector: str = None,  # CSS selector or XPath
        text: str = None,
        browser: str = "chrome",  # chrome, firefox, edge
        headless: bool = False,
        wait_for: str = None,  # Element to wait for
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """
        Automate browser actions.
        
        Examples:
            # Launch browser and navigate
            browser_automation(action="launch", url="https://example.com")
            
            # Click element
            browser_automation(action="click", selector="#submit-button")
            
            # Type in form
            browser_automation(action="type", selector="#username", text="myuser")
            
            # Take screenshot
            browser_automation(action="screenshot", save_path="page.png")
        """
```

### 3.2 Web Scraping with AI

```python
class WebScrapeTool(AutomationTool):
    """Intelligent web scraping with AI understanding"""
    
    def execute(
        self,
        url: str,
        extract: str,  # "text", "links", "images", "tables", "structured", "ai_summary"
        selector: str = None,
        ai_prompt: str = None,  # For AI-powered extraction
        max_pages: int = 1,
        follow_links: bool = False,
    ) -> Dict[str, Any]:
        """
        Scrape web content with AI understanding.
        
        Examples:
            # Extract article text
            web_scrape(url="https://example.com/article", extract="text")
            
            # AI-powered extraction
            web_scrape(
                url="https://example.com/products",
                extract="structured",
                ai_prompt="Extract all product names and prices"
            )
        """
```

---

## 4. Implementation Dependencies

### 4.1 Python Packages

```txt
# Computer Control
pyautogui>=0.9.54          # Mouse and keyboard control
pywinauto>=0.6.8           # Windows GUI automation (Windows only)
pynput>=1.7.6              # Input monitoring and control
Pillow>=10.0.0             # Screenshot and image processing
opencv-python>=4.8.0       # Image recognition on screen

# Browser Automation
playwright>=1.40.0         # Modern browser automation
selenium>=4.15.0           # Alternative browser automation
beautifulsoup4>=4.12.0     # HTML parsing
requests>=2.31.0           # HTTP requests

# Security Tools
python-nmap>=0.7.1         # Nmap integration
scapy>=2.5.0               # Packet manipulation (optional)
cryptography>=41.0.0       # Cryptographic operations
```

### 4.2 System Requirements

```bash
# Install browser binaries for Playwright
playwright install chromium
playwright install firefox

# Install nmap (system package)
# Ubuntu/Debian:
sudo apt-get install nmap

# macOS:
brew install nmap

# Windows:
# Download from https://nmap.org/download.html
```

---

## 5. Safety Implementation

### 5.1 Fail-Safe Mechanisms

```python
class AutomationSafetyController:
    """Central safety controller for all automation"""
    
    def __init__(self):
        self.emergency_stop = False
        self.action_count = 0
        self.max_actions = 1000  # Hard limit
        self.start_time = time.time()
        self.max_duration = 3600  # 1 hour max
    
    def check_safety(self) -> bool:
        """Check if automation should continue"""
        # Check emergency stop
        if self.emergency_stop:
            return False
        
        # Check action limit
        if self.action_count >= self.max_actions:
            logger.warning("Maximum action limit reached")
            return False
        
        # Check time limit
        if time.time() - self.start_time > self.max_duration:
            logger.warning("Maximum duration exceeded")
            return False
        
        # Check for fail-safe trigger (mouse in corner)
        if self._check_failsafe_triggered():
            logger.warning("Fail-safe triggered - stopping automation")
            return False
        
        return True
    
    def _check_failsafe_triggered(self) -> bool:
        """Check if user triggered fail-safe (mouse in corner)"""
        try:
            import pyautogui
            x, y = pyautogui.position()
            screen_width, screen_height = pyautogui.size()
            
            # Check if mouse is in any corner (within 10 pixels)
            corner_size = 10
            in_corner = (
                (x <= corner_size and y <= corner_size) or  # Top-left
                (x >= screen_width - corner_size and y <= corner_size) or  # Top-right
                (x <= corner_size and y >= screen_height - corner_size) or  # Bottom-left
                (x >= screen_width - corner_size and y >= screen_height - corner_size)  # Bottom-right
            )
            
            return in_corner
        except:
            return False
```

### 5.2 Permission System Integration

```python
class ComputerControlPermissionManager:
    """Extended permission system for computer control"""
    
    PERMISSION_LEVELS = {
        "read_only": [
            "screenshot",
            "list_windows",
            "get_cursor_position",
        ],
        "basic_control": [
            "read_only",
            "click",
            "type",
            "press_key",
            "scroll",
        ],
        "full_control": [
            "basic_control",
            "move_mouse",
            "drag",
            "right_click",
            "double_click",
            "hotkey_combinations",
        ],
        "browser_control": [
            "full_control",
            "launch_browser",
            "navigate",
            "fill_forms",
            "submit_forms",
            "extract_data",
        ],
    }
    
    def check_permission(self, action: str, user_level: str) -> bool:
        """Check if user has permission for action"""
        allowed_actions = self.PERMISSION_LEVELS.get(user_level, [])
        return action in allowed_actions or "*" in allowed_actions
```

---

## 6. Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Create `cortex/tools/automation/` module structure
- [ ] Implement `AutomationTool` base class with safety controls
- [ ] Create `AutomationSafetyController`
- [ ] Implement basic permission system
- [ ] Add audit logging infrastructure

### Phase 2: Screenshot & Screen Analysis (Week 2)
- [ ] Implement `ScreenshotTool`
- [ ] Add screen region capture
- [ ] Implement image recognition on screen
- [ ] Add OCR for text extraction from screenshots
- [ ] Create visual diff for before/after comparisons

### Phase 3: Mouse & Keyboard Control (Week 3)
- [ ] Implement `MouseControlTool`
- [ ] Implement `KeyboardControlTool`
- [ ] Add fail-safe mechanisms
- [ ] Implement action queuing and sequencing
- [ ] Add visual feedback (cursor highlighting)

### Phase 4: Window Management (Week 4)
- [ ] Implement `WindowManagerTool`
- [ ] Add window listing and filtering
- [ ] Implement window manipulation (move, resize, focus)
- [ ] Add application launching
- [ ] Implement window state detection

### Phase 5: Browser Automation (Week 5-6)
- [ ] Implement `BrowserAutomationTool`
- [ ] Add Playwright integration
- [ ] Implement navigation and element interaction
- [ ] Add form filling and submission
- [ ] Implement screenshot and PDF generation
- [ ] Add cookie and session management
- [ ] Implement JavaScript execution

### Phase 6: Advanced Features (Week 7-8)
- [ ] Implement `WebScrapeTool` with AI understanding
- [ ] Add intelligent element detection
- [ ] Implement workflow recording and replay
- [ ] Add multi-step task automation
- [ ] Implement error recovery and retry logic

---

## 7. Dependencies

### 7.1 Core Dependencies
```txt
# Computer Control
pyautogui>=0.9.54          # Cross-platform mouse/keyboard control
Pillow>=10.0.0             # Image processing for screenshots
opencv-python>=4.8.0       # Computer vision for image recognition
pytesseract>=0.3.10        # OCR for text extraction

# Platform-specific (optional but recommended)
pywinauto>=0.6.8           # Windows GUI automation (Windows only)
applescript>=2021.2.9      # macOS automation (macOS only)
pyatspi2>=2.46.0           # Linux accessibility/AT-SPI

# Browser Automation
playwright>=1.40.0         # Modern browser automation
selenium>=4.15.0           # Alternative browser automation
beautifulsoup4>=4.12.0     # HTML parsing
requests>=2.31.0           # HTTP requests

# Safety & Monitoring
pynput>=1.7.6              # Input monitoring for fail-safes
psutil>=5.9.0              # System monitoring
```

### 7.2 System Dependencies

```bash
# Tesseract OCR (required for text extraction)
# Ubuntu/Debian:
sudo apt-get install tesseract-ocr

# macOS:
brew install tesseract

# Windows:
# Download installer from https://github.com/UB-Mannheim/tesseract/wiki

# Playwright browsers
playwright install chromium
playwright install firefox
playwright install webkit
```

---

## 8. Safety Implementation Details

### 8.1 Fail-Safe Mechanisms

```python
class FailSafeManager:
    """Multi-layer fail-safe system"""
    
    def __init__(self):
        self.enabled = True
        self.corner_threshold = 10  # pixels
        self.emergency_key = "esc"
        self.max_consecutive_actions = 100
        self.action_count = 0
        
    def check_all(self) -> bool:
        """Run all fail-safe checks"""
        if not self.enabled:
            return True
            
        # Check 1: Mouse in corner
        if self._mouse_in_corner():
            self._trigger_emergency_stop("Mouse moved to corner")
            return False
            
        # Check 2: Emergency key pressed
        if self._emergency_key_pressed():
            self._trigger_emergency_stop("Emergency key pressed")
            return False
            
        # Check 3: Action limit
        self.action_count += 1
        if self.action_count > self.max_consecutive_actions:
            self._trigger_emergency_stop("Action limit exceeded")
            return False
            
        return True
    
    def _mouse_in_corner(self) -> bool:
        """Check if mouse is in fail-safe corner"""
        try:
            import pyautogui
            x, y = pyautogui.position()
            w, h = pyautogui.size()
            
            # Check all four corners
            corners = [
                (0, 0),  # Top-left
                (w, 0),  # Top-right
                (0, h),  # Bottom-left
                (w, h),  # Bottom-right
            ]
            
            for cx, cy in corners:
                if abs(x - cx) < self.corner_threshold and abs(y - cy) < self.corner_threshold:
                    return True
            return False
        except:
            return False
```

### 8.2 Permission Flow

```
User Request
    │
    ▼
┌─────────────────────────────────────────┐
│ 1. Check if automation is enabled      │
│    in configuration                      │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ 2. Check user permission level         │
│    - read_only: screenshots only        │
│    - basic_control: click, type         │
│    - full_control: all mouse/keyboard   │
│    - browser_control: browser access    │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ 3. For sensitive actions:              │
│    - Show visual preview                 │
│    - Request explicit confirmation       │
│    - Start countdown before execution    │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ 4. Execute with:                         │
│    - Fail-safe monitoring active         │
│    - Screenshot before/after             │
│    - Audit logging                       │
│    - Timeout protection                  │
└─────────────────────────────────────────┘
```

---

## 9. Example Usage Scenarios

### 9.1 Automated UI Testing
```python
# User: "Test the login form on my app"

# Agent workflow:
1. screenshot(action="capture")  # See current state
2. browser_automation(action="navigate", url="http://localhost:3000/login")
3. screenshot(action="capture")  # Verify page loaded
4. browser_automation(action="type", selector="#username", text="testuser")
5. browser_automation(action="type", selector="#password", text="testpass")
6. browser_automation(action="click", selector="#login-button")
7. screenshot(action="capture")  # Verify result
8. browser_automation(action="close")
```

### 9.2 Data Entry Automation
```python
# User: "Fill out this form with data from the spreadsheet"

# Agent workflow:
1. Read spreadsheet data
2. window_manager(action="focus", window_title="Form Application")
3. For each row in data:
   a. keyboard_control(action="type", text=row["name"])
   b. keyboard_control(action="press", keys=["tab"])
   c. keyboard_control(action="type", text=row["email"])
   d. keyboard_control(action="press", keys=["tab"])
   e. keyboard_control(action="type", text=row["phone"])
   f. keyboard_control(action="press", keys=["return"])
   g. time.sleep(0.5)  # Wait for processing
```

### 9.3 Browser Research Assistant
```python
# User: "Research the latest Python features and summarize"

# Agent workflow:
1. browser_automation(action="launch", url="https://docs.python.org/3/whatsnew/3.12.html")
2. web_scrape(url="https://docs.python.org/3/whatsnew/3.12.html", extract="text")
3. browser_automation(action="navigate", url="https://realpython.com/python-312-features/")
4. web_scrape(url="https://realpython.com/python-312-features/", extract="text")
5. browser_automation(action="close")
6. Use LLM to summarize findings
```

---

## 10. Testing Strategy

### 10.1 Unit Tests
```python
# Test safety mechanisms
def test_failsafe_corner_detection():
    safety = FailSafeManager()
    # Mock mouse position in corner
    assert safety._mouse_in_corner() == True
    assert safety.check_all() == False  # Should trigger stop

# Test permission validation
def test_permission_denied_for_unauthorized_target():
    tool = PortScanTool(...)
    result = tool.execute(target="8.8.8.8")  # Unauthorized external IP
    assert result["success"] == False
    assert result["error_type"] == "permission"
```

### 10.2 Integration Tests
```python
# Test complete workflow
def test_browser_automation_workflow():
    # Launch local test server
    with TestServer() as server:
        tool = BrowserAutomationTool(...)
        
        # Navigate
        result = tool.execute(action="navigate", url=server.url)
        assert result["success"]
        
        # Type in form
        result = tool.execute(
            action="type",
            selector="#test-input",
            text="Hello World"
        )
        assert result["success"]
        
        # Verify with screenshot
        result = tool.execute(action="screenshot")
        assert result["success"]
```

### 10.3 Safety Tests
```python
# Test emergency stop
def test_emergency_stop():
    controller = AutomationController()
    controller.start_session()
    
    # Simulate emergency key press
    controller.failsafe_manager.emergency_stop = True
    
    result = controller.execute_action("click", x=100, y=100)
    assert result["success"] == False
    assert "emergency_stop" in result["error"]
```

---

## 11. Configuration

### 11.1 Default Configuration
```yaml
# config/default.yaml

automation:
  enabled: false  # Must be explicitly enabled
  
  safety:
    failsafe_enabled: true
    corner_threshold: 10  # pixels
    emergency_key: "esc"
    max_actions_per_session: 1000
    max_session_duration: 3600  # seconds
    require_confirmation_for: ["click", "type", "hotkey"]
    screenshot_before_after: true
  
  permissions:
    default_level: "read_only"  # read_only, basic_control, full_control, browser_control
    require_explicit_authorization: true
    authorized_applications: []  # List of allowed app names
    blocked_applications: ["password_manager", "banking_app"]  # Never automate
  
  browser:
    default_browser: "chromium"
    headless: false  # Show browser window for transparency
    screenshot_on_navigate: true
    max_pages_per_session: 50
    allowed_domains: []  # Empty = all (with confirmation)
    blocked_domains: ["localhost:.*", "127.0.0.1:.*"]  # Protect local services
    
  audit:
    log_all_actions: true
    log_screenshots: true
    retention_days: 30
    log_file: "logs/automation_audit.log"
```

---

## 12. Usage Examples

### 12.1 Complete Workflow Examples

#### Example 1: Automated Form Filling
```python
# User: "Fill out the contact form on this website"

# Agent reasoning:
1. Check if browser automation is enabled
2. Verify user has browser_control permission
3. Ask for confirmation with target URL
4. Execute:

workflow = [
    {"action": "launch", "browser": "chrome", "headless": False},
    {"action": "navigate", "url": "https://example.com/contact"},
    {"action": "screenshot", "description": "Verify page loaded"},
    {"action": "type", "selector": "#name", "text": "John Doe"},
    {"action": "type", "selector": "#email", "text": "john@example.com"},
    {"action": "type", "selector": "#message", "text": "Hello, I have a question..."},
    {"action": "screenshot", "description": "Review form before submission"},
    {"action": "ask_user", "question": "Submit the form?"},
    {"action": "click", "selector": "#submit", "if_approved": True},
    {"action": "screenshot", "description": "Confirm submission"},
    {"action": "close"},
]
```

#### Example 2: Data Extraction from Web
```python
# User: "Get all product names and prices from this e-commerce page"

# Agent workflow:
1. browser_automation(action="launch")
2. browser_automation(action="navigate", url="https://shop.example.com/products")
3. web_scrape(
    url="https://shop.example.com/products",
    extract="structured",
    ai_prompt="Extract all product names and their prices. Return as JSON array."
   )
4. browser_automation(action="close")
5. Present results to user
```

#### Example 3: UI Testing
```python
# User: "Test the login flow of my application"

# Agent workflow:
1. window_manager(action="focus", window_title="MyApp")
2. screenshot(action="capture")  # Initial state
3. mouse_control(action="click", x=login_button_x, y=login_button_y)
4. keyboard_control(action="type", text="testuser")
5. keyboard_control(action="press", keys=["tab"])
6. keyboard_control(action="type", text="testpass")
7. screenshot(action="capture")  # Before submit
8. keyboard_control(action="press", keys=["return"])
9. time.sleep(2)  # Wait for response
10. screenshot(action="capture")  # Final state
11. Compare screenshots to determine success
```

---

## 13. Testing Strategy

### 13.1 Unit Tests
```python
def test_mouse_control_safety():
    """Test that mouse control respects safety limits"""
    tool = MouseControlTool(...)
    
    # Test that rapid clicks are rate-limited
    start = time.time()
    for i in range(100):
        tool.execute(action="click")
    duration = time.time() - start
    
    # Should take at least 10 seconds due to rate limiting
    assert duration >= 10.0

def test_failsafe_trigger():
    """Test emergency stop functionality"""
    controller = AutomationController()
    controller.start_session()
    
    # Simulate emergency
    controller.trigger_emergency_stop()
    
    # All subsequent actions should fail
    result = controller.execute_action("click", x=100, y=100)
    assert result["success"] == False
    assert "emergency_stop" in result["error"]
```

### 13.2 Integration Tests
```python
def test_complete_browser_workflow():
    """Test full browser automation workflow"""
    with TestWebServer() as server:
        tool = BrowserAutomationTool(...)
        
        # Launch
        result = tool.execute(action="launch", headless=True)
        assert result["success"]
        
        # Navigate
        result = tool.execute(action="navigate", url=server.url)
        assert result["success"]
        
        # Interact
        result = tool.execute(
            action="type",
            selector="#test-input",
            text="Hello"
        )
        assert result["success"]
        
        # Verify
        result = tool.execute(action="screenshot")
        assert result["success"]
        assert result["data"]["path"].exists()
        
        # Cleanup
        result = tool.execute(action="close")
        assert result["success"]
```

---

## 14. Configuration Example

```yaml
# config/automation.yaml

automation:
  enabled: true
  
  safety:
    failsafe_enabled: true
    corner_threshold: 10
    emergency_key: "esc"
    max_actions_per_session: 1000
    max_session_duration: 3600
    require_confirmation_for: ["click", "type", "hotkey"]
    screenshot_before_after: true
    pause_between_actions: 0.5  # seconds
  
  permissions:
    default_level: "basic_control"
    require_explicit_authorization: true
    authorized_applications: []
    blocked_applications:
      - "password_manager"
      - "banking_app"
      - "crypto_wallet"
  
  browser:
    default_browser: "chromium"
    headless: false
    screenshot_on_navigate: true
    max_pages_per_session: 50
    allowed_domains: []
    blocked_domains:
      - "localhost:*"
      - "127.0.0.1:*"
      - "*.local"
    user_agent: "Cortex-Bot/1.0"
    viewport:
      width: 1920
      height: 1080
  
  mouse:
    default_duration: 0.5  # Movement duration
    click_delay: 0.1
    double_click_interval: 0.5
    scroll_clicks: 10  # Lines per scroll
  
  keyboard:
    default_interval: 0.01  # Between keystrokes
    hotkey_delay: 0.1
  
  audit:
    log_all_actions: true
    log_screenshots: true
    retention_days: 30
    log_file: "logs/automation_audit.log"
    include_screenshots_in_log: false  # Store separately
```

---

## 15. Conclusion

This plan provides a comprehensive roadmap for adding computer control and browser automation capabilities to Cortex. The implementation prioritizes:

1. **Safety**: Multiple fail-safes and permission systems
2. **Transparency**: Visual feedback and audit logging
3. **Control**: User can stop automation at any time
4. **Utility**: Practical use cases for development and testing

The phased approach allows for incremental development and testing, ensuring each component is robust before adding more capabilities.
