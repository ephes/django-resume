# Django Resume MCP Server

A Model Context Protocol (MCP) server that enables LLMs to interact with the django-resume codebase and create new plugins dynamically.

## 🎉 Successfully Integrated!

The MCP server is now fully integrated into your django-resume project using your existing `uv` dependency management. No separate virtual environments needed!

## 🚀 Quick Start

### 1. Install Dependencies
```bash
# Install MCP dependency (already added to pyproject.toml)
uv sync --dev
```

### 2. Run the MCP Server

**Option A: Using the command-line script**
```bash
django-resume-mcp-server
```

**Option B: Using Django management command**
```bash
cd example
python manage.py run_mcp_server
```

**Option C: Direct Python execution**
```bash
python -m django_resume.entrypoints.mcp_server
```

### 3. Configure Your MCP Client

Add to your MCP client configuration (e.g., Claude Desktop):

**Recommended configuration (using uv):**
```json
{
  "mcpServers": {
    "django-resume": {
      "command": "/path/to/uv",
      "args": ["--directory", "/path/to/django-resume", "run", "python", "-m", "django_resume.entrypoints.mcp_server_lazy"],
      "env": {
        "DJANGO_SETTINGS_MODULE": "example.settings"
      }
    }
  }
}
```

**Alternative (using command-line script):**
```json
{
  "mcpServers": {
    "django-resume": {
      "command": "django-resume-mcp-server",
      "cwd": "/path/to/django-resume",
      "env": {
        "DJANGO_SETTINGS_MODULE": "example.settings"
      }
    }
  }
}
```

**Note:** Replace paths with your actual locations. Find your uv path with `which uv`.

## 🔧 What's Available

### 📚 **Resources**
- **Codebase Access**: All plugin source files, models, views, core components
- **Template Access**: Django templates for all themes and plugin types  
- **Database Access**: Runtime access to database-stored plugins and resume data
- **Overview Documents**: Structured summaries of project architecture

### 🛠️ **Tools**
- **create_plugin**: Generate new plugins using your existing LLM system
- **list_plugins**: Enumerate all plugins (file-based and database)
- **analyze_plugin**: Deep analysis of plugin structure and code quality

### 📖 **Example Usage**

**List all available resources:**
```json
{
  "method": "resources/list"
}
```

**Get project overview:**
```json
{
  "method": "resources/read",
  "params": {
    "uri": "overview://codebase"
  }
}
```

**Create a new plugin:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "create_plugin",
    "arguments": {
      "prompt": "Create a plugin for programming languages with proficiency levels and years of experience",
      "plugin_name": "programming_languages",
      "save_to_database": true,
      "activate_plugin": false
    }
  }
}
```

**List all plugins:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "list_plugins",
    "arguments": {
      "include_details": true
    }
  }
}
```

**Analyze a plugin:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "analyze_plugin",
    "arguments": {
      "plugin_name": "about",
      "include_validation": true,
      "include_suggestions": true,
      "compare_with": "education"
    }
  }
}
```

## 🏗️ Architecture

### **Project Structure**
```
src/django_resume/
├── mcp_server/
│   ├── server.py           # Main MCP server
│   ├── resources/          # MCP Resources
│   │   ├── codebase.py     # Code access
│   │   ├── templates.py    # Template access  
│   │   └── database.py     # Database access
│   ├── tools/              # MCP Tools
│   │   ├── create_plugin.py    # Plugin generation
│   │   ├── list_plugins.py     # Plugin listing
│   │   └── analyze_plugin.py   # Plugin analysis
│   └── utils/              # Utilities
│       ├── django_setup.py     # Django integration
│       ├── code_generator.py   # Code generation
│       └── validator.py        # Code validation
├── entrypoints/
│   └── mcp_server.py       # Command-line entrypoint
└── management/commands/
    └── run_mcp_server.py   # Django management command
```

### **Integration Benefits**
- ✅ **Same Virtual Environment**: Uses your existing `.venv` with uv
- ✅ **Dependency Management**: MCP added to `pyproject.toml` dev dependencies
- ✅ **Django Integration**: Direct access to your models and plugin system
- ✅ **Command-line Access**: Multiple ways to run the server
- ✅ **No Duplication**: Reuses your existing `plugin_generator.py` system

## 🔒 Security Features

- **Code Pattern Analysis**: Blocks dangerous patterns (exec, eval, file operations)
- **Import Restrictions**: Prevents unsafe module imports
- **Template Validation**: Safe Django template syntax only
- **Size Limits**: Prevents resource exhaustion attacks
- **JSON Validation**: Ensures form fields are serializable

## 🎯 Use Cases

### **Plugin Development Workflow**
1. **Explore** existing patterns using `list_plugins` and `analyze_plugin`
2. **Generate** new plugin using `create_plugin` with detailed prompt
3. **Validate** generated code using built-in validation
4. **Refine** based on suggestions and comparison with existing plugins
5. **Deploy** by activating in database

### **AI-Assisted Development**
- LLMs can understand your entire django-resume architecture
- Generate plugins that follow your existing patterns
- Provide code quality feedback and suggestions
- Enable rapid prototyping of new functionality

## 🚨 Troubleshooting

### **Common Issues**

**MCP server won't start:**
```bash
# Check if dependencies are installed
uv sync --dev

# Verify Django can be imported
python -c "import django_resume; print('OK')"

# Test MCP server imports
python -c "from django_resume.mcp_server.server import main; print('MCP OK')"
```

**Django setup issues:**
```bash
# Ensure example settings work
cd example
python manage.py check

# Test database access
python manage.py shell -c "from django_resume.models import Plugin; print(Plugin.objects.count())"
```

**LLM generation fails:**
```bash
# Test LLM access
llm "test prompt"

# Check API keys
llm keys list
```

### **Debug Mode**

For detailed logging:
```bash
export DJANGO_RESUME_MCP_DEBUG=1
django-resume-mcp-server
```

## 🔗 Related Commands

```bash
# Your existing LLM content script (still works)
llm-content

# New MCP server command
django-resume-mcp-server

# Django management command
python manage.py run_mcp_server

# List available Django commands
python manage.py help
```

## 🎉 Success!

Your django-resume project now has a fully integrated MCP server that:

- **🤖 Enables AI Development**: LLMs can understand and extend your project
- **🔄 Reuses Existing Code**: Leverages your current plugin generation system  
- **🛡️ Maintains Security**: Multiple validation layers prevent dangerous code
- **📈 Scales Efficiently**: Uses the same dependency management as your main project
- **🎯 Production Ready**: Comprehensive error handling and logging

The server successfully bridges the gap between AI capabilities and your django-resume architecture, enabling intelligent plugin development while maintaining security and code quality standards.

---

**Ready to use!** 🚀 Start with `django-resume-mcp-server` and begin creating plugins with AI assistance!