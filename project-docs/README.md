# Project Documentation Structure

This folder contains all project documentation and artifacts, organized for clarity and safety.

## 📁 Folder Structure

### `/copilot-config/`
**Purpose:** GitHub Copilot configuration files  
**Contains:** copilot-instructions.md and related AI assistant configs  
**Git Status:** ✅ Tracked (these are project guidelines)

### `/conversation-outputs/`
**Purpose:** Markdown files and outputs generated during Copilot conversations  
**Contains:** Feature specs, implementation plans, analysis reports  
**Git Status:** ❌ Not tracked (local working files)

### `/session-logs/`
**Purpose:** Session notes and work logs  
**Contains:** SESSION_LOG_*.md, SESSION_CONTEXT_*.md  
**Git Status:** ❌ Not tracked (temporary tracking)

### `/reference-guides/`
**Purpose:** Long-term reference documentation  
**Contains:** Database schemas, API references, architecture docs  
**Git Status:** ✅ Tracked (important reference material)

### `/code-snippets/`
**Purpose:** Reusable code examples and templates  
**Contains:** Python snippets, SQL queries, utility functions  
**Git Status:** ✅ Tracked (useful for development)

## 🚨 Important Rules

1. **Never commit passwords** - Use environment variables
2. **No customer PII** - Keep customer data local only
3. **Web app focus** - Only web deployment files in git root
4. **Keep it clean** - Conversation outputs stay local

## 📝 Usage Guidelines

**When creating new documentation:**
- Session notes → `/session-logs/`
- Feature specs → `/conversation-outputs/`
- Database docs → `/reference-guides/`
- Code examples → `/code-snippets/`
- Copilot rules → `/copilot-config/`

**Before committing:**
- Check for passwords/credentials
- Verify no customer data
- Ensure proper folder placement
