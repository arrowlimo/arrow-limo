import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("=" * 80)
print("DATABASE SIZE ANALYSIS FOR NEON FREE TIER")
print("=" * 80)
print()

# Get total database size
cur.execute("SELECT pg_database_size('almsdata')")
size_bytes = cur.fetchone()[0]
size_mb = size_bytes / (1024 * 1024)
size_gb = size_bytes / (1024 * 1024 * 1024)

print(f"Current Database Size:")
print(f"  {size_bytes:,} bytes")
print(f"  {size_mb:.2f} MB")
print(f"  {size_gb:.3f} GB")
print()

# Neon free tier limits
neon_free_limit_gb = 0.5  # 512 MB
neon_launch_limit_gb = 10  # Launch tier

print(f"Neon Free Tier Limit: {neon_free_limit_gb} GB ({neon_free_limit_gb * 1024} MB)")
print(f"Your database: {size_gb:.3f} GB ({size_mb:.2f} MB)")
print()

if size_gb <= neon_free_limit_gb:
    print("✅ YES - You can downgrade to Neon Free tier!")
    headroom = (neon_free_limit_gb * 1024) - size_mb
    print(f"   Headroom: {headroom:.2f} MB ({(headroom / (neon_free_limit_gb * 1024) * 100):.1f}% remaining)")
else:
    overage = size_mb - (neon_free_limit_gb * 1024)
    print(f"❌ NO - You're {overage:.2f} MB over the free tier limit")
    print(f"   Need to reduce by: {overage:.2f} MB ({(overage / size_mb * 100):.1f}%)")
    print()
    print("Options:")
    print("  1. Stay on paid tier (Launch: 10 GB limit)")
    print("  2. Further optimize database to get under 512 MB")

print()

# Show largest tables
print("TOP 20 LARGEST TABLES:")
print("-" * 80)

cur.execute("""
    SELECT 
        schemaname,
        tablename,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
        pg_total_relation_size(schemaname||'.'||tablename) as bytes
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
    LIMIT 20
""")

total_top20 = 0
for row in cur.fetchall():
    schema, table, size, bytes_val = row
    total_top20 += bytes_val
    print(f"  {table:<45} {size:>10}")

print()
print(f"Top 20 tables total: {total_top20 / (1024*1024):.2f} MB ({total_top20 / size_bytes * 100:.1f}% of database)")

conn.close()
