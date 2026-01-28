"""
RBAC Management CLI
Assign roles, view permissions, audit access.
"""
import os
import psycopg2

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

HELP = """
Role-Based Access Control (RBAC) Management

Usage:
  python -X utf8 scripts/rbac_manage.py list-users
  python -X utf8 scripts/rbac_manage.py list-roles
  python -X utf8 scripts/rbac_manage.py add-user <username> <full_name> <email>
  python -X utf8 scripts/rbac_manage.py assign-role <username> <role_name>
  python -X utf8 scripts/rbac_manage.py revoke-role <username> <role_name>
  python -X utf8 scripts/rbac_manage.py user-permissions <username>
  python -X utf8 scripts/rbac_manage.py user-scopes <username> <scope_type>
  python -X utf8 scripts/rbac_manage.py set-scope <username> <scope_type> <scope_value>

Roles: admin, accountant, manager, employee, driver
Scope types: charter_id, employee_id, vehicle_id, account_number

Examples:
  Add driver user:
    python -X utf8 scripts/rbac_manage.py add-user john_driver "John Smith" "john@company.com"
    python -X utf8 scripts/rbac_manage.py assign-role john_driver driver

  Assign driver to charters:
    python -X utf8 scripts/rbac_manage.py set-scope john_driver charter_id 001234
    python -X utf8 scripts/rbac_manage.py set-scope john_driver charter_id 001235

  View driver permissions:
    python -X utf8 scripts/rbac_manage.py user-permissions john_driver
"""

def main():
    import sys
    if len(sys.argv) < 2:
        print(HELP)
        return

    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    cmd = sys.argv[1]

    if cmd == 'list-users':
        cur.execute("""
        SELECT user_id, username, full_name, email, is_active FROM system_users ORDER BY username
        """)
        print("\nUsers:\n")
        for uid, username, full_name, email, is_active in cur.fetchall():
            status = "✓ ACTIVE" if is_active else "✗ INACTIVE"
            print(f"  {status} | {username:<25} | {full_name:<30} | {email}")

    elif cmd == 'list-roles':
        cur.execute("""
        SELECT role_id, role_name, description FROM system_roles ORDER BY role_name
        """)
        print("\nRoles:\n")
        for rid, name, desc in cur.fetchall():
            print(f"  {name:<20} | {desc}")

    elif cmd == 'add-user':
        if len(sys.argv) < 5:
            print("Usage: add-user <username> <full_name> <email>")
            return
        username, full_name, email = sys.argv[2], sys.argv[3], sys.argv[4]
        cur.execute("""
        INSERT INTO system_users (username, full_name, email) VALUES (%s, %s, %s)
        """, (username, full_name, email))
        conn.commit()
        print(f"✓ User {username} created.")

    elif cmd == 'assign-role':
        if len(sys.argv) < 4:
            print("Usage: assign-role <username> <role_name>")
            return
        username, role_name = sys.argv[2], sys.argv[3]
        cur.execute("""
        SELECT user_id FROM system_users WHERE username = %s
        """, (username,))
        result = cur.fetchone()
        if not result:
            print(f"✗ User {username} not found.")
            return
        user_id = result[0]
        cur.execute("""
        SELECT role_id FROM system_roles WHERE role_name = %s
        """, (role_name,))
        result = cur.fetchone()
        if not result:
            print(f"✗ Role {role_name} not found.")
            return
        role_id = result[0]
        cur.execute("""
        INSERT INTO system_user_roles (user_id, role_id, assigned_by)
        VALUES (%s, %s, 'admin')
        ON CONFLICT DO NOTHING
        """, (user_id, role_id))
        conn.commit()
        print(f"✓ Assigned role '{role_name}' to user '{username}'.")

    elif cmd == 'revoke-role':
        if len(sys.argv) < 4:
            print("Usage: revoke-role <username> <role_name>")
            return
        username, role_name = sys.argv[2], sys.argv[3]
        cur.execute("""
        DELETE FROM system_user_roles
        WHERE user_id = (SELECT user_id FROM system_users WHERE username = %s)
          AND role_id = (SELECT role_id FROM system_roles WHERE role_name = %s)
        """, (username, role_name))
        conn.commit()
        print(f"✓ Revoked role '{role_name}' from user '{username}'.")

    elif cmd == 'user-permissions':
        if len(sys.argv) < 3:
            print("Usage: user-permissions <username>")
            return
        username = sys.argv[2]
        cur.execute("""
        SELECT DISTINCT p.module, p.action, r.role_name
        FROM system_users u
        JOIN system_user_roles ur ON u.user_id = ur.user_id
        JOIN system_role_permissions rp ON ur.role_id = rp.role_id
        JOIN system_permissions p ON rp.permission_id = p.permission_id
        JOIN system_roles r ON ur.role_id = r.role_id
        WHERE u.username = %s
        ORDER BY r.role_name, p.module, p.action
        """, (username,))
        rows = cur.fetchall()
        if not rows:
            print(f"✗ User {username} not found or has no roles.")
            return
        print(f"\nPermissions for {username}:\n")
        current_role = None
        for module, action, role_name in rows:
            if role_name != current_role:
                print(f"  [{role_name}]")
                current_role = role_name
            print(f"    {module:<20} {action}")

    elif cmd == 'user-scopes':
        if len(sys.argv) < 4:
            print("Usage: user-scopes <username> <scope_type>")
            return
        username, scope_type = sys.argv[2], sys.argv[3]
        cur.execute("""
        SELECT scope_value
        FROM system_user_scopes sus
        JOIN system_users u ON sus.user_id = u.user_id
        WHERE u.username = %s AND sus.scope_type = %s
        ORDER BY scope_value
        """, (username, scope_type))
        print(f"\n{scope_type} scopes for {username}:\n")
        for scope_value, in cur.fetchall():
            print(f"  {scope_value}")

    elif cmd == 'set-scope':
        if len(sys.argv) < 5:
            print("Usage: set-scope <username> <scope_type> <scope_value>")
            return
        username, scope_type, scope_value = sys.argv[2], sys.argv[3], sys.argv[4]
        cur.execute("""
        SELECT user_id FROM system_users WHERE username = %s
        """, (username,))
        result = cur.fetchone()
        if not result:
            print(f"✗ User {username} not found.")
            return
        user_id = result[0]
        cur.execute("""
        INSERT INTO system_user_scopes (user_id, scope_type, scope_value)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING
        """, (user_id, scope_type, scope_value))
        conn.commit()
        print(f"✓ Added scope: {username} can access {scope_type}={scope_value}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
