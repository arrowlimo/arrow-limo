# 🔒 SECURE INSPECTION FORMS - QUICK REFERENCE

## Endpoints

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| **POST** | `/api/inspection-forms/signed-url/{reserve}` | Get time-limited download link | JWT |
| **GET** | `/api/inspection-forms/{reserve}?signature=...&expires=...` | Download form (requires signed URL) | JWT |
| **GET** | `/api/inspection-forms/{reserve}/metadata` | Check if form exists | JWT |

## Flow

```
1. User logs in → Get JWT token
        ↓
2. Click "View Inspection Form" 
        ↓
3. POST /api/inspection-forms/signed-url/019123 (with JWT)
        ↓
4. Server returns: { "url": "http://...?signature=abc&expires=123456" }
        ↓
5. GET that signed URL (with JWT)
        ↓
6. Server verifies: JWT ✓ + Signature ✓ + Expires ✓ + Permission ✓
        ↓
7. Return PDF file + Log access to audit_logs
```

## Security Checks

```
✓ JWT token valid? (user logged in)
✓ JWT expired? (not older than token TTL)
✓ URL signature valid? (HMAC-SHA256 matches)
✓ URL expired? (not older than 30 min)
✓ User authorized? (driver/dispatch/admin)
✓ Charter exists? (reserve_number valid)
```

## Desktop Usage

**Upload**:
```
1. Select driver
2. Enter charter details
3. Click "📄 Upload Inspection Form"
4. Select PDF/image
5. Done! File saved: L:\limo\data\inspections\charter_019123\inspection_20260125_143022.pdf
```

**View Local**:
```
1. Click "👁 View/Download Form"
2. Opens in default PDF viewer
3. Only works on desktop (local file system)
```

## Web Usage

**Get Signed URL**:
```javascript
const response = await fetch('/api/inspection-forms/signed-url/019123', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${jwt_token}` }
});
const { url } = await response.json();
```

**Download**:
```javascript
// Method 1: Link
<a href={url} download>Download</a>

// Method 2: API with fetch
const file = await fetch(url, {
  headers: { 'Authorization': `Bearer ${jwt_token}` }
});

// Method 3: Viewer (iframe)
<iframe src={url} />
```

## What's Protected

```
BEFORE: No security
http://127.0.0.1:8000/files/inspection.pdf
↑ Anyone who knows the URL can access

AFTER: Bank-level security
POST /api/inspection-forms/signed-url/019123
  ← Requires JWT token
  ← Checks user role
  ← Returns temporary link (30 min)
  
GET /api/inspection-forms/019123?signature=...&expires=...
  ← Requires JWT token
  ← Verifies HMAC signature
  ← Checks expiration
  ← Logs access to audit_logs
  ← Returns file only if all checks pass
```

## Compliance Features

```
✅ eHOS Compliance
   - Digital copy on file (6+ months)
   - Timestamp proof
   - Driver signature
   
✅ DOT Audit Ready
   - Download history (audit_logs)
   - User identification
   - IP address tracking
   - Timestamp proof
   
✅ Security
   - Tamper-proof URLs
   - Time-limited access
   - Role-based access
   - Encryption ready
```

## Troubleshooting

| Error | Fix |
|-------|-----|
| "Invalid token" | Login again |
| "Link expired" | Generate new signed URL |
| "Invalid signature" | Don't modify URL params |
| "Not authorized" | Check user role |
| "File not found" | Upload form first |

## URLs

- Signed URL: `http://127.0.0.1:8000/api/inspection-forms/019123?signature=abc123...&expires=1706270522`
- Never access: `http://127.0.0.1:8000/files/...` (insecure!)
- Always use: `POST /api/inspection-forms/signed-url/...` (secure!)

## Key Points

⚡ **Signed URLs expire in 30 minutes**
- Generate new one if download takes longer
- Share URL with others = they can download once
- URL not reusable after expiration

🔐 **Every download is logged**
- audit_logs table tracks all access
- Compliance ready for audits
- Who, when, from where

👨‍💼 **Role-based access**
- Drivers: Own charters only
- Dispatch: Any charter
- Admin: Any charter

📄 **Supports PDF and images**
- .pdf, .jpg, .jpeg, .png
- Latest file automatically selected
- Multiple forms per charter allowed
