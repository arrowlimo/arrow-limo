def generate_driver_dashboard(driver_name: str, trips: list, role: str) -> str:
    """Generate dashboard for drivers/operators."""
    trips_html = ""
    for trip in trips:
        status_color = {
            "scheduled": "#667eea",
            "in_progress": "#f59e0b",
            "completed": "#10b981",
            "cancelled": "#ef4444",
        }.get(trip.get("status", "scheduled"), "#667eea")
        trips_html += (
            '<div class="trip-card"><div class="trip-header"><div><h3>'
            f'{trip.get("passenger", "Unknown")}'
            '</h3></div><span class="trip-status" style="background-color: '
            f'{status_color}">'
            f'{trip.get("status", "scheduled").replace("_", " ").title()}'
            '</span></div><div class="trip-details"><p><strong>Pickup:'
            f'</strong> {trip.get("pickup", "TBA")}</p><p><strong>Dropoff:'
            f'</strong> {trip.get("dropoff", "TBA")}</p></div></div>'
        )
    if not trips:
        trips_html = (
            '<p style="text-align: center; color: #999; padding: 20px;">' "No trips scheduled</p>"
        )

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport"
content="width=device-width"><title>Driver Dashboard</title><style>
body{{font-family:sans-serif;background:#f5f7fa;margin:0}}
.navbar{{background:linear-gradient(135deg,#667eea,
# 764ba2);color:white;padding:20px
# 40px;display:flex;justify-content:space-between}}
.container{{max-width:1200px;margin:40px auto;padding:0 20px}}
.welcome{{background:white;padding:30px;border-radius:12px;margin-bottom:30px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,
1fr));gap:20px;margin-bottom:30px}}
.stat-card{{background:white;padding:20px;border-radius:12px;box-shadow:0 2px
10px rgba(0,0,0,0.05)}}
.stat-value{{font-size:32px;font-weight:700;color:#667eea}}
.trips-section{{background:white;padding:30px;border-radius:12px}}
.trip-card{{border:1px solid
#e0e0e0;border-radius:8px;padding:16px;margin-bottom:12px}}
.trip-status{{color:white;padding:4px 12px;border-radius:20px;font-size:12px}}
</style></head>
<body>
<div class="navbar"><h1>Arrow Limo {role.title()} Portal</h1><a
href="/auth/logout" style="color:white;text-decoration:none">Logout</a></div>
<div class="container">
<div class="welcome"><h2>Welcome, {driver_name}!</h2></div>
<div class="stats">
<div class="stat-card"><div style="color:#999;font-size:12px">Trips
Today</div><div class="stat-value">{len(trips)}</div></div>
<div class="stat-card"><div style="color:#999;font-size:12px">Status</div>
<div class="stat-value" style="color:#10b981">Active</div></div>
</div>
<div class="trips-section"><h3>Today's Trips</h3>{trips_html}</div>
</div>
</body></html>"""


def generate_admin_dashboard(admin_name: str, role: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Admin Dashboard</title><style>
body{{font-family:sans-serif;background:#f5f7fa;margin:0}}
.navbar{{background:linear-gradient(135deg,#e74c3c,
# c0392b);color:white;padding:20px
# 40px;display:flex;justify-content:space-between}}
.container{{max-width:1200px;margin:40px auto;padding:0 20px}}
.welcome{{background:white;padding:30px;border-radius:12px;margin-bottom:30px}}
.tools{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,
1fr));gap:20px}}
.tool-card{{background:white;padding:20px;border-radius:12px;box-shadow:0 2px
10px rgba(0,0,0,0.05)}}
</style></head>
<body>
<div class="navbar"><h1>Arrow Limo {role.title()} Panel</h1><a
href="/auth/logout" style="color:white;text-decoration:none">Logout</a></div>
<div class="container">
<div class="welcome"><h2>Welcome, {admin_name}!</h2></div>
<div class="tools">
<div class="tool-card"><h3>Reports</h3><p>View system reports</p></div>
<div class="tool-card"><h3>Drivers</h3><p>Manage drivers</p></div>
<div class="tool-card"><h3>Fleet</h3><p>Fleet management</p></div>
<div class="tool-card"><h3>Payments</h3><p>Process payments</p></div>
</div></div></body></html>"""


def generate_super_user_dashboard(super_user_name: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Super User Dashboard</title><style>
body{{font-family:sans-serif;background:#f5f7fa;margin:0}}
.navbar{{background:linear-gradient(135deg,#8e44ad,
# 2c3e50);color:white;padding:20px
# 40px;display:flex;justify-content:space-between}}
.container{{max-width:1200px;margin:40px auto;padding:0 20px}}
.welcome{{background:white;padding:30px;border-radius:12px;margin-bottom:30px;border-left:4px
solid #8e44ad}}
.badge{{background:#8e44ad;color:white;padding:4px
12px;border-radius:20px;font-size:12px;display:inline-block;margin-top:10px}}
.tools{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,
1fr));gap:20px}}
.tool-card{{background:white;padding:20px;border-radius:12px;box-shadow:0 2px
10px rgba(0,0,0,0.05)}}
</style></head>
<body>
<div class="navbar"><h1>Arrow Limo Super User Panel</h1><a
href="/auth/logout" style="color:white;text-decoration:none">Logout</a></div>
<div class="container">
<div class="welcome"><h2>Welcome, {super_user_name}!</h2><div
class="badge">SUPER USER</div></div>
<div class="tools">
<div class="tool-card"><h3>All Reports</h3></div>
<div class="tool-card"><h3>Settings</h3></div>
<div class="tool-card"><h3>Users</h3></div>
<div class="tool-card"><h3>Security</h3></div>
<div class="tool-card"><h3>Fleet</h3></div>
<div class="tool-card"><h3>Database</h3></div>
</div></div></body></html>"""


def generate_default_dashboard(user_name: str, role: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Dashboard</title><style>
body{{font-family:sans-serif;background:#f5f7fa;margin:0}}
.navbar{{background:linear-gradient(135deg,#3498db,
# 2980b9);color:white;padding:20px
# 40px;display:flex;justify-content:space-between}}
.container{{max-width:1200px;margin:40px auto;padding:0 20px}}
.welcome{{background:white;padding:30px;border-radius:12px}}
.role-badge{{background:#3498db;color:white;padding:4px
12px;border-radius:20px;font-size:12px;display:inline-block;margin-top:10px}}
</style></head>
<body>
<div class="navbar"><h1>Arrow Limo Portal</h1><a href="/auth/logout"
style="color:white;text-decoration:none">Logout</a></div>
<div class="container">
<div class="welcome"><h2>Welcome, {user_name}!</h2><p>Role: {role}</p><div
class="role-badge">{role.upper()}</div></div>
</div></body></html>"""


def generate_dashboard_content(user_name: str, user_role: str, trips: list | None = None) -> str:
    """Return the dashboard HTML content for the given role."""
    if user_role in ["driver", "operator"]:
        return generate_driver_dashboard(user_name, trips or [], user_role)
    if user_role in ["admin", "manager"]:
        return generate_admin_dashboard(user_name, user_role)
    if user_role == "super_user":
        return generate_super_user_dashboard(user_name)
    return generate_default_dashboard(user_name, user_role)
