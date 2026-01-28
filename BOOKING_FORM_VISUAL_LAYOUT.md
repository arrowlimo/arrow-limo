# Booking Form Visual Layout Guide

## Display Mode (Read-Only) - Default View

```
┌──────────────────────────────────────────────────────────────────────────┐
│  CUSTOMER INFORMATION - IMPROVED CUSTOMER WIDGET                         │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Reserve #: 006717                                             ✏️  Edit   │
│  ────────────────────────────────────────────────────────────────────    │
│                                                                            │
│  Phone:             (403) 555-0123       Email:  rich@example.com         │
│  Address:           123 Main St, Calgary, AB T2N 1K7                      │
│                                                                            │
│  Client: Richard, Angie                                                   │
│                                                                            │
│  ════════════════════════════════════════════════════════════════════    │
│  All text, no input boxes - clean professional appearance                │
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- ✓ Reserve # displayed as 8-char monospace at top
- ✓ Phone, Email, Address in readable columns
- ✓ All fields text-only (no edit boxes)
- ✓ Edit button in top-right corner
- ✓ Proper spacing and alignment

---

## Edit Mode - Form with Editable Fields

```
┌──────────────────────────────────────────────────────────────────────────┐
│  CUSTOMER INFORMATION - IMPROVED CUSTOMER WIDGET                         │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Reserve #:  ┌─────────┐  (auto-generated, read-only)                    │
│              │ 006717  │                                                  │
│              └─────────┘                                                  │
│                                                                            │
│  Client: *   ┌──────────────────────┐  ┌─────────┐  ┌─────┐             │
│              │ Start typing...  ▼   │  │ ➕ New  │  │ ✏️  │             │
│              └──────────────────────┘  │ Client  │  │Edit │             │
│                                         └─────────┘  └─────┘             │
│                     (searchable dropdown with autocomplete)              │
│                                                                            │
│  Phone: *    ┌──────────────────┐                                         │
│              │ (403) 555-0123   │                                         │
│              └──────────────────┘                                         │
│              (std phone width: 150px)                                    │
│                                                                            │
│  Email:      ┌──────────────────────────────┐                            │
│              │ rich@example.com             │                            │
│              └──────────────────────────────┘                            │
│              (email width: 300px)                                        │
│                                                                            │
│  Address:    ┌────────────────────────────────────┐                      │
│              │ 123 Main St, Calgary, AB T2N 1K7   │                      │
│              └────────────────────────────────────┘                      │
│              (address width: 400px)                                      │
│                                                                            │
│                          ┌────────┐  ┌──────────────┐                   │
│                          │ Cancel │  │💾 Save Client│                   │
│                          └────────┘  └──────────────┘                   │
│                                                                            │
│  Save button only ENABLED when changes detected (blue), otherwise gray  │
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- ✓ Reserve # field read-only (gray background)
- ✓ Client field is searchable dropdown with autocomplete
- ✓ "New Client" button to add instantly
- ✓ "Edit" button to modify selected client
- ✓ Field widths optimized for content (150/300/400px)
- ✓ Cancel/Save buttons bottom-right
- ✓ Save disabled until user makes changes

---

## Quick Add Client Dialog

```
┌──────────────────────────────────────────────────────┐
│  ADD NEW CLIENT                                   [X]│
├──────────────────────────────────────────────────────┤
│                                                       │
│  Client Name: *  ┌──────────────────────────────┐    │
│                  │ Full name or business name   │    │
│                  └──────────────────────────────┘    │
│                                                       │
│  Phone: *        ┌──────────────────┐                │
│                  │ (403) 555-1234   │                │
│                  └──────────────────┘                │
│                                                       │
│  Email:          ┌──────────────────────────────┐    │
│                  │ email@example.com            │    │
│                  └──────────────────────────────┘    │
│                                                       │
│  Address:        ┌──────────────────────────────┐    │
│                  │ Street address               │    │
│                  └──────────────────────────────┘    │
│                                                       │
│                     ┌────────┐  ┌──────────────┐     │
│                     │ Cancel │  │💾 Save Client│     │
│                     └────────┘  └──────────────┘     │
│                                                       │
└──────────────────────────────────────────────────────┘
```

**Features:**
- ✓ Minimal form (only 4 fields)
- ✓ Name and Phone marked required (*)
- ✓ Save button bottom-right
- ✓ Cancel to dismiss without saving
- ✓ Validation before save

---

## Edit Client Dialog (Similar to Add)

```
┌──────────────────────────────────────────────────────┐
│  EDIT CLIENT                                      [X]│
├──────────────────────────────────────────────────────┤
│                                                       │
│  Client Name:    ┌──────────────────────────────┐    │
│                  │ Richard, Angie               │    │
│                  └──────────────────────────────┘    │
│                                                       │
│  Phone:          ┌──────────────────┐                │
│                  │ (403) 555-0123   │                │
│                  └──────────────────┘                │
│                                                       │
│  Email:          ┌──────────────────────────────┐    │
│                  │ rich@example.com             │    │
│                  └──────────────────────────────┘    │
│                                                       │
│  Address:        ┌──────────────────────────────┐    │
│                  │ 123 Main St, Calgary, AB     │    │
│                  └──────────────────────────────┘    │
│                                                       │
│                     ┌────────┐  ┌────────────────┐   │
│                     │ Cancel │  │💾 Save Changes │   │
│                     └────────┘  └────────────────┘   │
│                                                       │
└──────────────────────────────────────────────────────┘
```

**Features:**
- ✓ Same layout as Add Client
- ✓ Fields pre-filled with existing data
- ✓ Title says "EDIT CLIENT"
- ✓ Save button says "Save Changes"

---

## User Interaction Flow

```
START: New Charter
    ↓
    ├─→ [Empty form shown] → Customer section in EDIT mode
    │
    └─→ User types in "Client:" combo
        ↓
        ├─→ Match found → Auto-fill phone, email, address
        │   ↓
        │   User clicks "💾 Save Charter"
        │   ↓
        │   Charter saved → Customer section switches to DISPLAY mode
        │
        └─→ No match → User clicks "➕ New Client"
            ↓
            Quick Add dialog opens
            ↓
            User fills: Name, Phone, Email, Address
            ↓
            User clicks "💾 Save Client"
            ↓
            Dialog closes → Client auto-selected in combo
            ↓
            Continue with charter details
            ↓
            User clicks "💾 Save Charter"
            ↓
            Charter saved → Customer section switches to DISPLAY mode


START: Load Existing Charter
    ↓
    Charter loads → Customer section in DISPLAY mode
    ↓
    User sees all info as read-only text
    ↓
    User clicks "✏️ Edit" button
    ↓
    Customer section switches to EDIT mode
    ↓
    User can now:
    ├─→ Modify phone/email/address
    ├─→ Select different client from dropdown
    └─→ Click "✏️ Edit" next to client to modify full client info
    ↓
    User clicks "💾 Save Client"
    ↓
    Changes saved → Section switches back to DISPLAY mode
```

---

## Field Width Specifications

| Field | Width | Example | Notes |
|-------|-------|---------|-------|
| Reserve # | 80px | 006717 | 8-char max, monospace |
| Phone | 150px | (403) 555-1234 | Standard phone length |
| Email | 300px | user@domain.com | Email length + padding |
| Address | 400px | 123 Main St, Calgary... | Typical address |
| Client Name (combo) | 300px | Select or type... | Dropdown + text |

---

## CSS/Styling Notes

### Display Mode
```
Labels: Font: Arial 10pt Bold
Text:   Font: Arial 10pt Regular
        Color: Black (#000)
        No background
        Word wrap enabled
        
Reserve #: Font: Courier 11pt Bold
           Color: Black
```

### Edit Mode
```
Labels: Font: Arial 10pt Bold
Fields: Font: Arial 9pt
        Background: White
        Border: 1px gray
        Padding: 4px
        
Buttons: Style: Blue (enabled), Gray (disabled)
         Font: Arial 9pt
         Padding: 6px 12px
         
Save Button: Enabled only when ≥1 field changed
```

---

## Accessibility Features

- ✓ All labels clearly associated with fields
- ✓ Required fields marked with * (asterisk)
- ✓ Tab order: Client Name → Phone → Email → Address → Buttons
- ✓ Enter key in last field triggers Save
- ✓ Escape key in form cancels edits
- ✓ Focus management: Proper focus transitions
- ✓ Button text is clear and descriptive
- ✓ Error messages explain what's wrong

---

## Professional UX Standards Followed

1. **Clarity**: Mode clearly shown (Display vs Edit)
2. **Consistency**: Button placement, field sizing, spacing
3. **Feedback**: Save button enables/disables based on changes
4. **Efficiency**: One-click add/edit of clients (no modal)
5. **Safety**: Cancel button prevents accidental data loss
6. **Standards**: Professional dialog patterns
7. **Alignment**: Proper label alignment and field grouping
8. **Typography**: Monospace for fixed data (reserve #), regular for text

---

This design provides a professional, intuitive booking form that handles client management elegantly.
