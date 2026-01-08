# LocalAgent - Complete Setup Guide

## 🚀 Quick Start (5 Minutes)

### Step 1: Install Ollama

**macOS:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:**
Download from https://ollama.ai/download/windows

### Step 2: Start Ollama & Pull a Model

```bash
# Start Ollama (runs in background)
ollama serve

# In a new terminal, pull a model
ollama pull llama3.2          # 3B - Fast, good for testing
# OR
ollama pull llama3.3:70b      # 70B - Much smarter, needs good GPU
# OR
ollama pull qwen2.5:32b       # 32B - Good balance
```

### Step 3: Install Python Dependencies

```bash
pip install ollama rich prompt_toolkit
```

### Step 4: Save the Agent Code

Save the agent code from the artifact as `localagent.py`

### Step 5: Run It!

```bash
# Make it executable (optional)
chmod +x localagent.py

# Navigate to any project
cd ~/my-project

# Start the agent
python localagent.py
```

---

## 📖 Usage Examples

### Interactive Mode (Like Claude Code)

```bash
cd my-project
python localagent.py

> add logging to api.py
> create a README file
> fix the bug in line 45 of database.py
> explain how authentication works
> write tests for the user service
```

### One-Shot Mode

```bash
python localagent.py -p "list all Python files"
python localagent.py -p "add type hints to utils.py"
```

### Different Models

```bash
# Use Llama 3.3 70B (much smarter)
python localagent.py --model llama3.3:70b

# Use Qwen 2.5 (good at coding)
python localagent.py --model qwen2.5:32b
```

### Permission Modes

```bash
# Normal mode (asks for everything) - DEFAULT
python localagent.py

# Auto-approve mode (dangerous! use in containers)
python localagent.py --auto-approve

# Plan mode (read-only, no changes)
python localagent.py --plan-mode
```

---

## 🎯 Real Usage Examples

### Example 1: Add a Feature

```bash
cd flask-app
python localagent.py

> add a /health endpoint that returns server status

🤖 I'll add a health endpoint. Let me check your code structure first...
📖 Reading: app.py
📖 Reading: routes.py

✍️  I'll add the endpoint to routes.py:
   [shows code diff with syntax highlighting]

❓ Write to routes.py? [y/n]: y

✅ Done! The endpoint is now available at /health
```

### Example 2: Debug an Issue

```bash
> the login function is returning 500 errors

🤖 Let me investigate...
📖 Reading: auth.py
📖 Reading: database.py

🔍 Found the issue: database connection not being closed
✍️  Here's the fix:
   [shows fix]

❓ Write to auth.py? [y/n]: y

✅ Fixed! Want me to add error handling too?

> yes please

✍️  Adding try-catch blocks...
❓ Write to auth.py? [y/n]: y

✅ Done!
```

### Example 3: Understand Code

```bash
> explain the authentication flow in this project

🤖 Let me read the relevant files...
📖 Reading: auth.py
📖 Reading: middleware.py
📖 Reading: models.py

🤖 Here's how authentication works in your project:

1. **Login Flow** (auth.py):
   - User POSTs credentials to /login
   - validate_user() checks against database
   - On success, generates JWT token with generate_token()
   
2. **Token Storage** (auth.py):
   - Token stored in Redis with 24h expiry
   - Key format: "session:{user_id}"
   
3. **Request Authentication** (middleware.py):
   - auth_middleware() intercepts all requests
   - Reads token from Authorization header
   - Validates against Redis
   - Attaches user object to request

Want me to show you any specific part in detail?
```

---

## 🎮 In-Session Commands

While in interactive mode, you can use these commands:

```
/help              Show help
/clear             Clear conversation history
/mode normal       Change to normal permission mode
/mode auto         Change to auto-approve mode
/mode plan         Change to plan mode (read-only)
/project           Show project information
/exit              Exit LocalAgent
```

---

## 🔧 Making It a Global Command (Like Claude Code)

Want to run `localagent` from anywhere? Here's how:

### Option 1: Symlink (Quick & Easy)

```bash
# Make executable
chmod +x localagent.py

# Create symlink in your PATH
sudo ln -s $(pwd)/localagent.py /usr/local/bin/localagent

# Now use it anywhere!
cd ~/any-project
localagent
```

### Option 2: Install with pip (Professional)

Create `setup.py`:

```python
from setuptools import setup

setup(
    name="localagent",
    version="1.0.0",
    py_modules=["localagent"],
    install_requires=[
        "ollama>=0.1.0",
        "rich>=13.0.0",
        "prompt_toolkit>=3.0.0"
    ],
    entry_points={
        "console_scripts": [
            "localagent=localagent:main",
        ],
    },
)
```

Then install:

```bash
pip install -e .

# Now works system-wide!
cd ~/any-project
localagent
```

---

## 📋 Project Configuration (Optional)

Create an `AGENT.md` file in your project root to give the agent context:

```markdown
# My Project

## Tech Stack
- Python 3.11 + FastAPI
- PostgreSQL + SQLAlchemy
- Redis for caching
- Docker for deployment

## Architecture
- `api/`: FastAPI routes and schemas
- `service/`: Business logic layer
- `repository/`: Database access
- `models/`: SQLAlchemy models

## Code Style
- Use type hints everywhere
- Follow PEP 8 strictly
- Write docstrings for all functions
- Prefer composition over inheritance

## Testing
- Use pytest
- Write tests BEFORE implementation
- Mock external dependencies
- Aim for 80%+ coverage

## Common Tasks
- Add endpoint: Create in api/, add service logic, update tests
- Add table: Create model, add migration, update repository
- Deploy: `docker-compose up -d`
```

The agent will automatically read this and follow your conventions!

---

## 🛡️ Safety Features

The agent has built-in safety:

1. **Dangerous Command Blocking**
   - Blocks `rm -rf /`, fork bombs, etc.
   - Always asks before executing commands

2. **Permission System**
   - Normal mode: Asks for approval on all writes/commands
   - Auto mode: For use in sandboxed environments only
   - Plan mode: Read-only, safe for exploration

3. **File Preview**
   - Shows diffs before overwriting
   - Shows command output
   - Syntax highlighting for code

---

## 🎨 Advanced Features

### 1. Search Across Project

```bash
> search for all database queries

🔍 Searching for: 'database queries'
[shows results from multiple files]
```

### 2. List Files with Pattern

```bash
> list all Python test files

📁 Files:
  tests/test_api.py
  tests/test_auth.py
  tests/test_database.py
```

### 3. Multi-Step Tasks

```bash
> refactor the authentication system to use JWT instead of sessions

🤖 This is a complex task. Let me break it down:

Phase 1: Read current implementation
📖 Reading: auth.py, session.py, middleware.py

Phase 2: Plan changes
📋 I'll need to:
   1. Add JWT library
   2. Update auth.py with JWT functions
   3. Update middleware to validate JWT
   4. Remove session management
   5. Update tests

Phase 3: Implementation
✍️  Installing JWT library...
🔧 Executing: pip install pyjwt

✍️  Updating auth.py...
[shows changes]
❓ Apply? [y/n]: y

[continues through all phases]

✅ Refactoring complete! All tests passing.
```

---

## 🐛 Troubleshooting

### "Cannot connect to Ollama"

```bash
# Make sure Ollama is running
ollama serve

# Check if it's running
curl http://localhost:11434/api/tags
```

### "Model not found"

```bash
# Pull the model first
ollama pull llama3.2

# List available models
ollama list
```

### "Agent is too slow"

```bash
# Use a smaller model
python localagent.py --model llama3.2

# Or if you have a good GPU, use quantized version
ollama pull llama3.3:70b-q4_K_M
python localagent.py --model llama3.3:70b-q4_K_M
```

### "Permission denied" on commands

```bash
# Don't run with sudo - the agent asks for permission
python localagent.py  # Not: sudo python localagent.py
```

---

## 🚀 Next Steps

1. **Try it out** on a small project first
2. **Create an AGENT.md** file with your project conventions
3. **Use plan mode** to explore codebases without making changes
4. **Install globally** so you can use it anywhere
5. **Try different models** to find the best balance of speed/quality

---

## 🆚 Comparison with Claude Code

| Feature | LocalAgent | Claude Code |
|---------|------------|-------------|
| **Cost** | Free (local) | $20-100/month |
| **Model** | Your choice (Llama, Qwen, etc.) | Claude Sonnet 4 |
| **Privacy** | 100% local | Sent to Anthropic |
| **Speed** | Depends on GPU | Fast (cloud) |
| **Quality** | Good (depends on model) | Excellent |
| **Internet** | Not required | Required |
| **Customization** | Full control | Limited |

---

## 💡 Tips for Best Results

1. **Be Specific**: "Add logging to api.py with INFO level" vs "add logging"

2. **Use Plan Mode First**: Explore new codebases in plan mode before making changes

3. **Read Before Write**: The agent is trained to read files first, but you can reinforce this

4. **Break Down Complex Tasks**: For major refactors, break into smaller steps

5. **Use Better Models**: Llama 3.3 70B or Qwen 2.5 72B are much better than 3B models

6. **Check the Code**: Always review what the agent writes - it's not perfect!

---

## 🎉 You're Ready!

Try it now:

```bash
cd your-project
python localagent.py

> create a simple hello world API endpoint
```

Have fun building with your local autonomous agent! 🚀