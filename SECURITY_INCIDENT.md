# SECURITY INCIDENT - Credential Exposure in Git History

## Incident Summary
**Date Discovered:** January 31, 2026  
**Severity:** HIGH  
**Status:** ACTIVE REMEDIATION  

### What Was Exposed
- **Old Neon Database Password:** `npg_89MbcFmZwUWo` (user: `neondb_owner`)
- **Exposure Method:** Hardcoded in 20+ git commits across backup files and scripts
- **Accessible To:** Anyone with access to GitHub repository
- **Time Window:** Password was exposed from at least commit 875e678 onwards

### Affected Files
**In Git History (100+ instances):**
- `backup_20260130_235425/` - Multiple audit and migration scripts
- `scripts/audit_dead_code_columns.py`
- `scripts/auto_sync_to_neon.py`
- `scripts/check_charter_columns.py`
- `scripts/check_neon_tables.py`
- `scripts/compare_vehicle_columns.py`
- `scripts/create_pricing_table_neon.py`
- `scripts/diagnose_neon_schema.py`
- `scripts/phase2_validation_suite.py`
- `scripts/migrate_to_neon_pro.py`
- `scripts/find_charter_totals.py`
- `scripts/restore_*.py` (multiple files)
- `pre_render_deployment_check.py`
- `render_health_check.py`
- Documentation files (md, yaml)

**In Working Directory (DELETED):**
- `passwords.txt` - Contained `npg_89MbcFmZwUWo`

## Remediation Actions Taken

### Immediate Actions (Jan 31, 2026)
✅ **COMPLETED:**
1. ✅ Identified all files containing old password
2. ✅ Deleted `passwords.txt` from working directory
3. ✅ Updated `.gitignore` to include `passwords.txt`
4. ✅ Updated `pre_render_deployment_check.py` to use environment variables
5. ✅ Created SECURITY_INCIDENT.md documentation

### Required Actions (PENDING)
⏳ **IMMEDIATE:**
1. **Neon Console:**
   - Log into Neon dashboard (https://console.neon.tech)
   - Go to Project: arrow-limo
   - Go to Users section
   - Revoke user `neondb_owner` password
   - Generate NEW password immediately
   - Copy new password

2. **Update Credentials:**
   - Update `.env` with new Neon password
   - Update Render environment variables with new password
   - Redeploy web service on Render

3. **Git History Cleaning:**
   - Use BFG Repo-Cleaner to remove `npg_89MbcFmZwUWo` from all commits
   - Force push to GitHub to update remote history
   - All clone operations will get clean history

4. **Scripts & Files:**
   - Update all `/scripts/` files to use `os.getenv('DB_PASSWORD')` instead of hardcoding
   - Update documentation files to not include passwords
   - Remove `render.yaml` from git if it contains credentials

5. **Update .gitignore:**
   - Add `**/*.py.bak` to ignore backup scripts
   - Add `config/secrets/` to ignore
   - Add `*.sql` if used for local setup with credentials

## Security Improvements (Going Forward)

### 1. Environment Variables Only
All database credentials must use environment variables:
```python
# ❌ WRONG
DB_PASSWORD = "npg_89MbcFmZwUWo"

# ✅ RIGHT
DB_PASSWORD = os.getenv('DB_PASSWORD')
```

### 2. Pre-Commit Hooks
Install git-secrets or husky to prevent credential commits:
```bash
# Scan patterns to catch
- "password\s*[:=]"
- "npg_"
- "DB_PASSWORD\s*="
- "secret"
```

### 3. Git Configuration
```bash
# Enable gitconfig protection
git config core.hooksPath .githooks

# Use git-crypt for sensitive files
git-crypt init
git-crypt add-gpg-user YOUR_GPG_KEY_ID
```

### 4. .gitignore Additions
```
# Secrets
.env*
!.env.example
passwords.txt
*.key
*.pem
config/secrets/
scripts/*.backup
```

## Timeline

| Date | Time | Action |
|------|------|--------|
| 2026-01-31 | 16:45 | Git security warning detected |
| 2026-01-31 | 16:47 | Identified 20+ files with `npg_89MbcFmZwUWo` |
| 2026-01-31 | 16:50 | Deleted `passwords.txt` |
| 2026-01-31 | 16:52 | Updated `.gitignore` and fixed active scripts |
| 2026-01-31 | 16:55 | Created this incident report |
| **2026-02-01** | **ASAP** | **Revoke password in Neon console** |
| **2026-02-01** | **ASAP** | **Generate new password** |
| **2026-02-01** | **ASAP** | **Update .env and Render** |
| **2026-02-01** | **ASAP** | **Clean git history with BFG** |

## Credentials Currently Active

### ✅ SAFE (In .env, NOT in git history)
- **Neon Password:** `npg_rlL0yK9pvfCW` (current, in use)
- **ALMS Local Password:** `alms_secure_password_2024` (local only)

### ⚠️ EXPOSED (Must be revoked)
- **Old Neon Password:** `npg_89MbcFmZwUWo` (REVOKE IMMEDIATELY)

## Lessons Learned
1. **Never hardcode secrets** - Use environment variables from day one
2. **Review before commit** - `git diff --cached` before every commit
3. **Use .gitignore from start** - Don't add and commit then gitignore
4. **Automate checks** - Pre-commit hooks catch mistakes automatically
5. **Document security** - Have clear procedures for all team members

## Contact & Questions
- **Incident Reporter:** GitHub Copilot AI
- **Status Updates:** Check this file for latest remediation status
- **Questions:** Review git commit message when history is cleaned
