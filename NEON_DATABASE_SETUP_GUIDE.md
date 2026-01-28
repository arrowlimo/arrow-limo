# Setting Up Remote Database with Neon

## Why Neon?

- ✓ Free tier available
- ✓ PostgreSQL managed service
- ✓ No ops/maintenance needed
- ✓ Auto-scaling available
- ✓ Accessible from anywhere
- ✓ Point-in-time restore backups
- ✓ Canadian regions available

## Step-by-Step Setup

### 1. Create Neon Account

1. Go to https://neon.tech
2. Sign up with email (or GitHub)
3. Verify email

### 2. Create a New Project

1. Click "New Project"
2. Fill in:
   - **Project name**: "Arrow Limousine"
   - **Database name**: "almsdata"
   - **PostgreSQL version**: 17 (recommended) or 16 (if you prefer LTS)
   - **Region**: Canada (ca-central-1 for low latency)
   - **Compute size**: Shared (free tier)

3. Click "Create project"

### 3. Get Connection String

After project creation:

1. Click "Connection string" tab
2. You'll see something like:

```
postgresql://[user]:[password]@[your-project-name].neon.tech/almsdata?sslmode=require
```

**Save this string - you'll need it**

### 4. Dump Your Local Database

From your local machine (where PostgreSQL is running). **Use the PostgreSQL 17 client tools (pg_dump/pg_restore) to match the Neon engine version.**

```powershell
# Create a compressed backup dump of your local almsdata (custom format)
pg_dump -h localhost -U postgres -d almsdata -F c -f almsdata_export.dump

# File size check
ls -lah almsdata_export.dump
```

### 5. Restore to Neon

Extract connection details from the Neon connection string:

```powershell
# Example connection string from Neon:
# postgresql://neondb_owner:AbC123xyz@bright-shadow-12345.neon.tech/almsdata?sslmode=require

# Parse and connect (replace with YOUR values from Neon):
$neonHost = "bright-shadow-12345.neon.tech"
$neonUser = "neondb_owner"
$neonPassword = "AbC123xyz"
$neonDb = "almsdata"

# Restore the dump (use pg_restore with SSL)
pg_restore -h $neonHost -U $neonUser -d $neonDb --clean --if-exists "almsdata_export.dump"
# When prompted, enter the Neon password (or set PGPASSWORD env var)
```

Or use the connection string directly:

```powershell
pg_restore "postgresql://neondb_owner:AbC123xyz@bright-shadow-12345.neon.tech/almsdata?sslmode=require" \
   --clean --if-exists "almsdata_export.dump"
```

### 6. Verify Data Transfer

```powershell
# Connect to Neon database
psql "postgresql://neondb_owner:AbC123xyz@bright-shadow-12345.neon.tech/almsdata?sslmode=require"

# Check tables
\dt

# Quick counts
SELECT COUNT(*) FROM charters;
SELECT COUNT(*) FROM banking_transactions;
SELECT COUNT(*) FROM payments;
\q
```

### 7. Update Your Application

Edit `.env` file in your project:

```ini
# OLD (local):
# DB_HOST=localhost
# DB_NAME=almsdata
# DB_USER=postgres
# DB_PASSWORD=***REMOVED***

# NEW (Neon):
DB_HOST=bright-shadow-12345.neon.tech
DB_NAME=almsdata
DB_USER=neondb_owner
DB_PASSWORD=AbC123xyz
DB_SSLMODE=require
```

Or use the full connection string in Python:

```python
import psycopg2

# Using connection string
conn = psycopg2.connect(
    "postgresql://neondb_owner:AbC123xyz@bright-shadow-12345.neon.tech/almsdata?sslmode=require"
)

# Or individual parameters
conn = psycopg2.connect(
    host="bright-shadow-12345.neon.tech",
    database="almsdata",
    user="neondb_owner",
    password="AbC123xyz",
    sslmode="require"
)
```

### 8. Test Connection

```powershell
cd l:\limo

python -c "
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    sslmode='require'
)
print('✓ Connected to Neon')

cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM charters')
count = cur.fetchone()[0]
print(f'✓ Found {count} charters in Neon')

conn.close()
"
```

### 9. Run Application with Neon

Now your FastAPI backend will connect to Neon automatically:

```powershell
# Start backend (will use Neon database from .env)
uvicorn modern_backend.app.main:app --reload

# Start frontend
cd frontend
npm run serve
```

Your application is now using the cloud database!

---

## Managing Your Neon Database

### From Neon Console

1. **SQL Editor**: Run queries directly
2. **Tables browser**: View schemas
3. **Monitoring**: Check connection metrics
4. **Backups**: Download backups, restore from snapshots

### Common Operations

```powershell
# Create new database branch (for testing)
# Use Neon console → Branches → Create branch

# Reset database to snapshot
# Use Neon console → Backups → Restore from snapshot

# Backup before migrations
# Use Neon console → Backups → Manual backup
```

---

## Security Best Practices

⚠️ **Important**:

1. **Never commit `.env`** to Git - add to `.gitignore`:
   ```
   .env
   .env.local
   *.secret
   ```

2. **Rotate password** if exposed:
   - Neon console → Settings → Password → Change password

3. **Use role-based access**:
   - Admin role: Full access (your development user)
   - App role: Limited (for production connection)

4. **Enable IP whitelist** (Neon Pro):
   - Restrict access to your IP only
   - In production, whitelist your server IP

5. **Use environment variables** (never hardcode passwords):
   ```python
   import os
   from dotenv import load_dotenv
   
   load_dotenv()  # Load from .env
   
   conn = psycopg2.connect(
       host=os.getenv('DB_HOST'),
       database=os.getenv('DB_NAME'),
       user=os.getenv('DB_USER'),
       password=os.getenv('DB_PASSWORD')
   )
   ```

---

## Pricing

**Free Tier** (Plenty for most uses):
- 3 branches
- 10 GB storage
- Shared compute
- Serverless compute for dev

**Pro Tier** ($15-20/month if needed):
- Unlimited branches
- Compute instances
- IP whitelist
- Priority support

---

## Troubleshooting

### Connection Refused

```
Error: could not connect to server: Connection refused
```

**Solution**: 
- Verify Neon host is correct
- Check `.env` variables
- Ensure `sslmode=require` is set

### Authentication Failed

```
FATAL: role "neondb_owner" does not exist
```

**Solution**:
- Check username matches Neon console
- Verify password is correct
- Try resetting password in Neon

### SSL Certificate Error

```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solution**:
- Add `sslmode=require` to connection string
- Update psycopg2: `pip install --upgrade psycopg2-binary`

### Slow Queries

- Check Neon console → Monitoring → Connections
- Consider upgrade to paid compute
- Optimize SQL queries with indexes

---

## Next Steps

After Neon setup:

1. ✅ Test all API endpoints
2. ✅ Verify data integrity
3. ✅ Set up regular backups (Neon auto-backup)
4. ✅ Configure monitoring alerts
5. ✅ Document connection details for team

---

**Status**: Neon database is production-ready
**Access**: https://console.neon.tech (your account)
**Support**: https://neon.tech/docs
