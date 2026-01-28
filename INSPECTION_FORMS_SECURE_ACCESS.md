# Secure Inspection Form Access (eHOS Compliance)

## Overview
Inspection forms are stored digitally with multi-layer security:
- JWT authentication (user must be logged in)
- HMAC-signed URLs (tamper-proof, 30-min expiration)
- Role-based authorization (driver/dispatch/admin only)
- Audit trail (every download logged)
- HTTPS/TLS encryption

## Workflow

### 1. Desktop App - Upload Form
```
Driver fills manual inspection form
↓
Dispatcher uploads via "📄 Upload Inspection Form" button
↓
System saves to: L:\limo\data\inspections\charter_019123\inspection_20260125_143022.pdf
↓
Path stored in charter metadata
```

### 2. Web App - Generate Signed URL
```
POST /api/inspection-forms/signed-url/019123
Authorization: Bearer <jwt_token>

Response:
{
  "url": "http://api.example.com/api/inspection-forms/019123?signature=abc123...&expires=1706270522",
  "expires_at": "2026-01-25T15:22:02",
  "charter_id": 1234
}
```

### 3. Web App - Download Form
```
GET /api/inspection-forms/019123?signature=abc123...&expires=1706270522
Authorization: Bearer <jwt_token>

Security checks:
✓ JWT token valid
✓ Token not expired
✓ Signature HMAC-verified
✓ URL not older than 30 min
✓ User authorized for this charter
✓ Access logged to audit_logs

Response: PDF file (with anti-caching headers)
```

### 4. Compliance - Audit Trail
```
audit_logs table records:
- user_id (who downloaded)
- charter_id (which charter)
- action: "download_inspection_form"
- ip_address (where from)
- timestamp (when)
```

## API Endpoints

### Generate Signed URL
```
POST /api/inspection-forms/signed-url/{reserve_number}
Authorization: Bearer <token>
Query Params:
  - expires_in_minutes: 30 (default)

Response: { "url": "...", "expires_at": "...", "charter_id": ... }
```

### Download Form
```
GET /api/inspection-forms/{reserve_number}
Authorization: Bearer <token>
Query Params:
  - signature: HMAC-SHA256 signature
  - expires: Unix timestamp

Response: File (PDF or image)
```

### Get Form Metadata
```
GET /api/inspection-forms/{reserve_number}/metadata
Authorization: Bearer <token>

Response:
{
  "reserve_number": "019123",
  "charter_id": 1234,
  "forms_count": 2,
  "forms": [
    {
      "filename": "inspection_20260125_143022.pdf",
      "size_bytes": 204800,
      "uploaded_at": "2026-01-25T14:30:22",
      "type": ".pdf"
    }
  ],
  "latest_form": { ... }
}
```

## Security Features

### 1. Authentication
- JWT tokens required for all endpoints
- Tokens must contain `user_id` and `role`
- Token expiration checked

### 2. Authorization
- **Drivers**: Can only download their own charter's form
- **Dispatch/Admin**: Can download any charter's form
- Role check: `if user_role not in ["admin", "dispatch"]:`

### 3. URL Security
- HMAC-SHA256 signature (prevents tampering)
- 30-minute expiration (short-lived URLs)
- Signature verified before file returned
- No direct file paths exposed

### 4. HTTPS/TLS
- All data encrypted in transit
- No passwords or sensitive data in URLs
- Secure header flags set (no-sniff, no-cache)

### 5. Audit Logging
- Every download recorded in `audit_logs` table
- Includes: user, charter, IP, timestamp
- Indexed for fast compliance queries
- Non-failing: audit log errors don't break download

### 6. File Security
- Files stored outside web root (L:\limo\data)
- No direct web access to files
- Only accessible via API endpoint
- Response headers prevent caching/MIME sniffing

## Implementation Checklist

- [x] Create `inspection_forms.py` router
- [x] JWT authentication (verify_jwt_token)
- [x] HMAC signature generation & verification
- [x] Authorization checks by role
- [x] Audit logging
- [x] Register router in main.py
- [ ] Create `audit_logs` table: `python modern_backend/migrations/create_audit_logs.py`
- [ ] Update frontend to use signed URLs
- [ ] Test with different user roles
- [ ] Document for compliance team

## Usage in Frontend

### React/Vue Example
```javascript
// 1. Get signed URL
const response = await fetch('/api/inspection-forms/signed-url/019123', {
  method: 'POST',
  headers: { 
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});
const { url } = await response.json();

// 2. Download or preview
window.open(url, '_blank');  // Opens in new tab
// OR
<a href={url} download>Download Inspection Form</a>

// 3. Open in iframe (PDF viewer)
<iframe src={url} width="100%" height="600px" />
```

## Compliance Notes

✓ **eHOS Compliance**: Digital copy on file with audit trail (6-month+ requirement)
✓ **DOT Audits**: Full download history in audit_logs
✓ **Data Privacy**: Only authorized users can access
✓ **Tamper-Proof**: HMAC signatures prevent URL modification
✓ **Audit Trail**: Timestamp proof of every access

## Troubleshooting

### "Link expired"
- Signed URL older than 30 minutes
- Generate new signed URL: `POST /api/inspection-forms/signed-url/...`

### "Invalid signature"
- URL was modified
- Don't edit signature or expires parameters
- Generate new signed URL

### "Not authorized"
- Your user role doesn't permit access
- Only drivers (for own charters), dispatch, and admins can download

### "Token expired"
- JWT token expired
- Log in again to get fresh token

### "Charter not found"
- Invalid reserve_number
- Check reserve number is correct
