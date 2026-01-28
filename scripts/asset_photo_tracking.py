#!/usr/bin/env python3
"""
Asset Photo/Documentation Tracking System
Manages photos and documents for CRA audit trail
"""
import os
import shutil
import psycopg2
from datetime import datetime
from pathlib import Path

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

PHOTO_STORAGE_BASE = os.path.join("l:\\limo", "asset_photos")


def init_photo_storage():
    """Initialize photo storage directories"""
    os.makedirs(PHOTO_STORAGE_BASE, exist_ok=True)
    
    # Create subdirectories by asset type
    asset_types = ["vehicles", "equipment", "electronics", "furniture", "real_estate"]
    for asset_type in asset_types:
        os.makedirs(os.path.join(PHOTO_STORAGE_BASE, asset_type), exist_ok=True)
    
    print(f"✅ Photo storage initialized at {PHOTO_STORAGE_BASE}")


def add_photo_to_asset(asset_id, photo_path, description=None, doc_type="photo"):
    """
    Add a photo/document to an asset
    
    Args:
        asset_id: ID of the asset
        photo_path: Path to the photo file
        description: Optional description of the photo
        doc_type: Type of document (photo, contract, receipt, insurance, registration, etc.)
    """
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        # Get asset info
        cur.execute("SELECT asset_name, asset_category FROM assets WHERE asset_id = %s", (asset_id,))
        asset_info = cur.fetchone()
        
        if not asset_info:
            print(f"❌ Asset ID {asset_id} not found")
            return False
        
        asset_name, asset_category = asset_info
        
        # Create storage directory for this asset
        asset_dir = os.path.join(PHOTO_STORAGE_BASE, asset_category or "other", f"asset_{asset_id}")
        os.makedirs(asset_dir, exist_ok=True)
        
        # Copy photo to storage
        if not os.path.exists(photo_path):
            print(f"❌ Photo file not found: {photo_path}")
            return False
        
        filename = os.path.basename(photo_path)
        stored_path = os.path.join(asset_dir, filename)
        shutil.copy2(photo_path, stored_path)
        
        # Record in database
        cur.execute("""
            INSERT INTO asset_documentation (
                asset_id, document_type, file_path, 
                description, uploaded_date
            ) VALUES (%s, %s, %s, %s, %s)
        """, (
            asset_id,
            doc_type,
            stored_path,
            description or f"{doc_type} of {asset_name}",
            datetime.now()
        ))
        
        conn.commit()
        print(f"✅ Added {doc_type} to Asset {asset_id} ({asset_name})")
        print(f"   Stored at: {stored_path}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error adding photo: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def list_asset_photos(asset_id):
    """List all photos/documents for an asset"""
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT asset_id, asset_name FROM assets WHERE asset_id = %s
        """, (asset_id,))
        asset_info = cur.fetchone()
        
        if not asset_info:
            print(f"❌ Asset ID {asset_id} not found")
            return
        
        asset_id, asset_name = asset_info
        
        cur.execute("""
            SELECT doc_id, document_type, file_path, description, uploaded_date
            FROM asset_documentation
            WHERE asset_id = %s
            ORDER BY uploaded_date DESC
        """, (asset_id,))
        
        docs = cur.fetchall()
        
        print(f"\n📸 Documentation for Asset {asset_id} ({asset_name}):")
        if not docs:
            print("   No documentation found")
        else:
            for doc_id, doc_type, file_path, description, uploaded_date in docs:
                exists = "✓" if os.path.exists(file_path) else "✗ (missing)"
                print(f"\n   [{doc_id}] {doc_type.upper()}")
                print(f"      {description}")
                print(f"      File: {file_path} {exists}")
                print(f"      Date: {uploaded_date}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cur.close()
        conn.close()


def generate_photo_audit_report():
    """Generate report of all assets with/without photos"""
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                a.asset_id,
                a.asset_name,
                a.asset_category,
                COUNT(ad.doc_id) as doc_count
            FROM assets a
            LEFT JOIN asset_documentation ad ON a.asset_id = ad.asset_id
            WHERE a.status IN ('active', 'disposed', 'stolen')
            GROUP BY a.asset_id, a.asset_name, a.asset_category
            ORDER BY doc_count ASC, a.asset_name
        """)
        
        results = cur.fetchall()
        
        report_path = os.path.join("l:\\limo", "reports", "assets", "PHOTO_DOCUMENTATION_AUDIT.txt")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("ASSET PHOTO & DOCUMENTATION AUDIT REPORT\n")
            f.write("=" * 100 + "\n")
            f.write(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Count by documentation status
            no_docs = [r for r in results if r[3] == 0]
            with_docs = [r for r in results if r[3] > 0]
            
            f.write("SUMMARY:\n")
            f.write("-" * 100 + "\n")
            f.write(f"Total Assets: {len(results)}\n")
            f.write(f"Assets WITH Documentation: {len(with_docs)} ({100*len(with_docs)//len(results)}%)\n")
            f.write(f"Assets WITHOUT Documentation: {len(no_docs)} ({100*len(no_docs)//len(results)}%)\n\n")
            
            f.write("ASSETS WITH DOCUMENTATION:\n")
            f.write("-" * 100 + "\n")
            for asset_id, name, category, doc_count in sorted(with_docs, key=lambda x: -x[3]):
                f.write(f"[{asset_id}] {name:<50} {category:<15} {doc_count} document(s)\n")
            
            f.write("\n\nASSETS NEEDING DOCUMENTATION:\n")
            f.write("-" * 100 + "\n")
            for asset_id, name, category, doc_count in no_docs:
                f.write(f"[{asset_id}] {name:<50} {category:<15} ⚠️  NO DOCS\n")
        
        print(f"✅ Report generated: {report_path}")
        
        return report_path
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import sys
    
    # Initialize photo storage
    init_photo_storage()
    
    # Generate initial audit report
    print("\n" + "="*100)
    print("Asset Photo & Documentation Tracking System Initialized")
    print("="*100 + "\n")
    
    print("USAGE EXAMPLES:")
    print("-" * 100)
    print("\n1. Add a photo to an asset:")
    print("   from scripts.asset_photo_tracking import add_photo_to_asset")
    print("   add_photo_to_asset(")
    print("       asset_id=27,")
    print("       photo_path=r'C:\\Photos\\caddy_2015_front.jpg',")
    print("       description='Front view of 2015 Cadillac before repossession',")
    print("       doc_type='photo'")
    print("   )")
    
    print("\n2. List all photos for an asset:")
    print("   from scripts.asset_photo_tracking import list_asset_photos")
    print("   list_asset_photos(27)")
    
    print("\n3. Add documentation (contracts, receipts, insurance, etc.):")
    print("   add_photo_to_asset(")
    print("       asset_id=30,")
    print("       photo_path=r'C:\\Documents\\td_bank_loan_agreement.pdf',")
    print("       description='TD Bank Loan Agreement for L-4 Navigator',")
    print("       doc_type='contract'")
    print("   )")
    
    print("\n4. Generate documentation audit report:")
    print("   from scripts.asset_photo_tracking import generate_photo_audit_report")
    print("   generate_photo_audit_report()")
    
    print("\n" + "-" * 100)
    print("\nDOCUMENT TYPES SUPPORTED:")
    print("   - photo: Asset photos (front, side, damage, condition)")
    print("   - contract: Loan agreements, leases, borrowing agreements")
    print("   - receipt: Purchase receipts, auction documents")
    print("   - insurance: Insurance claims, payout documents, appraisals")
    print("   - registration: Title, registration, VIN documents")
    print("   - maintenance: Service records, repair documentation")
    print("   - other: Any other supporting documentation")
    
    print(f"\nPhoto Storage Location: {PHOTO_STORAGE_BASE}")
    print("\n" + "="*100)
    
    # Generate audit report
    generate_photo_audit_report()
