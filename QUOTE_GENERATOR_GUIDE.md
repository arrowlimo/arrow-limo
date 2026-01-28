# Quote Generator - User Guide

## Overview
The Quote Generator allows you to quickly create professional, printable quotes from any past charter in the system. This is useful for:
- Re-quoting similar trips
- Providing quotes to clients for future trips
- Printing confirmation documents
- Email delivery to clients

## How to Access
1. In the Desktop App, go to **🚀 Operations** tab
2. Click the **💬 Quote Generator** sub-tab
3. The system will load all past charters (last 500 records)

## Finding a Charter

### Method 1: Search by Reserve Number
1. Enter the **reserve number** (e.g., `019233`) in the search field
2. Click **Search** or press Enter
3. Click on the charter in the table to select it

### Method 2: Filter by Status
1. Use the **Filter by Status** dropdown to show only:
   - `quote` - Initial quotes
   - `booked` - Confirmed bookings
   - `completed` - Completed trips
   - `cancelled` - Cancelled charters
   - `All` - All statuses
2. Click on a charter in the filtered list

### Method 3: Browse All Charters
1. Leave the search field empty
2. Click **Reset** to see all past charters, newest first
3. Scroll through the table and click to select

## After Selecting a Charter

Once you've selected a charter (row highlights in blue), you can:

### Preview Quote
- **Click "Preview Quote"** to see a formatted HTML preview
- The preview shows all key information:
  - Client name and account number
  - Pickup and dropoff addresses
  - Passenger count and vehicle type
  - Pricing breakdown with GST calculation
  - Deposit requirement and balance due
- From the preview, you can print or export without closing

### Print Quote
- **Click "Print Quote"** to send directly to a printer
- A print dialog will appear - select your printer and settings
- The quote will print in professional format

### Export to PDF
- **Click "Export as PDF"** to save locally
- Choose a save location on your computer
- File will be named `Quote_[RESERVE_NUMBER].pdf`
- Share via email or store in your records

### Email Quote
- **Click "Email Quote"** (coming soon)
- Will prompt for client email address
- Quote will be sent as PDF attachment

## Quote Information Included

Each generated quote includes:

**Header**
- Arrow Limousine Services logo/name
- Professional formatting
- Reservation number and quote date
- Current booking status

**Client Information**
- Client name
- Account number (if applicable)

**Service Details**
- Pickup and dropoff addresses
- Passenger count
- Vehicle type/description
- Special requirements (if any)

**Pricing Breakdown**
- Rate (base price)
- Subtotal before GST
- GST amount (5% - INCLUDED in total)
- **Total Amount Due**
- Deposit required (percentage-based)
- Balance due after deposit

**Terms**
- 30-day quote validity
- Deposit percentage requirement
- 48-hour cancellation notice
- Payment terms

**Footer**
- Generation date/time
- Professional footer with company info

## Tips & Tricks

### Bulk Operations
For multiple quotes:
1. Open a browser or file manager on the side
2. Generate one quote at a time
3. Save PDFs to a dedicated folder
4. Email or print as needed

### Customization
**Current:** Quotes use standard Arrow Limousine template

**Future Enhancements:**
- Custom company details (header logo, footer, terms)
- Discount/promotion application
- Custom payment schedules
- Digital signature capture

### Reusing Quote Data
When you select a charter:
- All data pulls from the actual database record
- Modifications in the quote don't affect the original charter
- Each quote generation creates a fresh copy

## Troubleshooting

### "Charter not found"
- Verify the reserve number is correct
- Reserve numbers are case-INSENSITIVE
- Check that the charter exists in the system
- Try searching without filters

### "No charters to display"
- The system might not have loaded yet (wait a moment)
- Click **Reset** to reload all charters
- Check database connection in Admin tab

### Print not working
- Ensure a printer is installed and connected
- Try **Export as PDF** instead
- Check printer settings in your OS

### Missing information on quote
- If fields are blank in the quote, they're also blank in the charter record
- You can edit the charter and regenerate the quote
- Special requirements and payment instructions are optional

## Best Practices

✅ **Do:**
- Keep reserve numbers organized
- Store PDF quotes for reference
- Use consistent naming conventions
- Archive PDF quotes by year/month

❌ **Don't:**
- Modify the charter database directly when quoting
- Assume all fields will be populated (some are optional)
- Delete charters without backing up quotes
- Share quotes with sensitive client financial info

## Keyboard Shortcuts
- **Ctrl+P** - Print current quote (if in preview)
- **Escape** - Close preview dialog
- **Enter** - Search by reserve number

## Future Enhancements Planned
- Multi-quote batch operations
- Email delivery with SMTP integration
- Custom quote templates per branch
- Quote history and tracking
- Digital signature support
- Payment gateway integration
- Quote expiration reminders

---

**Need Help?**
Contact your system administrator or check the main app's Help menu.

**Database Schema Note:**
Quotes pull from the `charters` table using `reserve_number` as the business key (best practice for the system).
