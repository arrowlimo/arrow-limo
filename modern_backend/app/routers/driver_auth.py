"""
User authentication routes - supports any user role (admin, driver, manager, super_user, etc.)
Serves login page and handles login for all user types
"""

import os
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
import psycopg2
from ..db import get_connection

router = APIRouter(prefix="/auth", tags=["user_auth"])

# Simple in-memory session store (in production, use Redis)
SESSIONS = {}
SESSION_TIMEOUT = 30 * 60  # 30 minutes


class LoginRequest(BaseModel):
    username: str
    password: str


def verify_user_credentials(username: str, password: str) -> dict:
    """Verify user login credentials against employees table"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Query employee with matching username/name (any role)
        cur.execute("""
            SELECT employee_id, name, role, phone 
            FROM employees 
            WHERE LOWER(name) = LOWER(%s)
            LIMIT 1
        """, (username,))
        
        employee = cur.fetchone()
        cur.close()
        conn.close()
        
        if not employee:
            return None
        
        # For now, accept any password (demo mode)
        # In production, check against hashed password
        return {
            "employee_id": employee[0],
            "name": employee[1],
            "role": employee[2],
            "phone": employee[3]
        }
    except Exception as e:
        print(f"Auth error: {e}")
        return None


def create_session(employee_id: int, employee_name: str) -> str:
    """Create a session token"""
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "employee_id": employee_id,
        "name": employee_name,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(seconds=SESSION_TIMEOUT)
    }
    return token


def get_session(token: str) -> dict:
    """Retrieve session if valid"""
    if token not in SESSIONS:
        return None
    
    session = SESSIONS[token]
    if datetime.now() > session["expires_at"]:
        del SESSIONS[token]
        return None
    
    return session


def get_driver_trips(employee_id: int) -> list:
    """Fetch today's trips for driver"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                charter_id,
                reserve_number,
                pickup_address,
                dropoff_address,
                scheduled_date,
                scheduled_time,
                passenger_name,
                status
            FROM charters
            WHERE assigned_employee_id = %s 
              AND DATE(scheduled_date) = CURRENT_DATE
            ORDER BY scheduled_time ASC
        """, (employee_id,))
        
        trips = []
        for row in cur.fetchall():
            trips.append({
                "charter_id": row[0],
                "reserve_number": row[1],
                "pickup": row[2],
                "dropoff": row[3],
                "date": str(row[4]),
                "time": str(row[5]),
                "passenger": row[6],
                "status": row[7]
            })
        
        cur.close()
        conn.close()
        return trips
    except Exception as e:
        print(f"Error fetching trips: {e}")
        return []


LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Arrow Limo - Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .login-container { background: white; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.3); width: 100%; max-width: 400px; padding: 40px; }
        .login-header { text-align: center; margin-bottom: 30px; }
        .login-header h1 { color: #333; font-size: 28px; margin-bottom: 10px; }
        .login-header p { color: #666; font-size: 14px; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; color: #333; font-weight: 600; margin-bottom: 8px; font-size: 14px; }
        .form-group input { width: 100%; padding: 12px 15px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 14px; transition: all 0.3s; }
        .form-group input:focus { outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }
        .login-btn { width: 100%; padding: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.3s; margin-top: 10px; }
        .login-btn:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4); }
        .error-message { background: #fee; border: 1px solid #fcc; color: #c00; padding: 12px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; display: none; }
        .error-message.show { display: block; }
        .demo-note { background: #f0f7ff; border-left: 4px solid #667eea; padding: 12px; margin-top: 20px; font-size: 12px; color: #555; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>🚗 Arrow Limo</h1>
            <p>Portal Login</p>
        </div>
        <div class="error-message" id="errorMsg"></div>
        <form id="loginForm">
            <div class="form-group">
                <label for="username">Username (Employee Name)</label>
                <input type="text" id="username" name="username" placeholder="Enter your name" autocomplete="off" required>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" placeholder="Enter password" required>
            </div>
            <button type="submit" class="login-btn">Sign In</button>
        </form>
        <div class="demo-note">
            <strong>Demo Mode:</strong> Try any employee name. Password can be anything.
        </div>
    </div>
    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('errorMsg');
            try {
                const response = await fetch('/auth/login-submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
                });
                if (response.ok) {
                    window.location.href = '/auth/dashboard';
                } else {
                    const data = await response.json();
                    errorDiv.textContent = data.error || 'Login failed';
                    errorDiv.classList.add('show');
                }
            } catch (error) {
                errorDiv.textContent = 'Network error. Please try again.';
                errorDiv.classList.add('show');
            }
        });
    </script>
</body>
</html>
"""


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve user login page (works for any user role)"""
    session_token = request.cookies.get("session_token")
    if session_token and get_session(session_token):
        return RedirectResponse(url="/auth/dashboard", status_code=302)
    return LOGIN_HTML


@router.post("/login-submit")
async def login_submit(
    username: str = Form(...),
    password: str = Form(...),
    response: Response = None
):
    """Handle login form submission"""
    user = verify_user_credentials(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    session_token = create_session(user["employee_id"], user["name"])
    response.set_cookie(
        key="session_token",
        value=session_token,
        max_age=30 * 60,
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return {"status": "success", "redirect": "/auth/dashboard"}


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """User dashboard - shows different content based on role"""
    session_token = request.cookies.get("session_token")
    session = get_session(session_token)
    if not session:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    employee_id = session["employee_id"]
    user_name = session["name"]
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT role FROM employees WHERE employee_id = %s", (employee_id,))
        role_row = cur.fetchone()
        user_role = role_row[0] if role_row else "user"
        cur.close()
        conn.close()
    except:
        user_role = "user"
    
    if user_role in ["driver", "operator"]:
        trips = get_driver_trips(employee_id)
        content = generate_driver_dashboard(user_name, trips, user_role)
    elif user_role in ["admin", "manager"]:
        content = generate_admin_dashboard(user_name, user_role)
    elif user_role == "super_user":
        content = generate_super_user_dashboard(user_name)
    else:
        content = generate_default_dashboard(user_name, user_role)
    
    return content


@router.get("/logout")
async def logout(response: Response):
    """Logout user and clear session"""
    response.delete_cookie("session_token")
    return RedirectResponse(url="/auth/login", status_code=302)


def generate_driver_dashboard(driver_name: str, trips: list, role: str) -> str:
    """Generate dashboard for drivers/operators"""
    trips_html = ""
    for trip in trips:
        status_color = {"scheduled": "#667eea", "in_progress": "#f59e0b", "completed": "#10b981", "cancelled": "#ef4444"}.get(trip.get("status", "scheduled"), "#667eea")
        trips_html += f'<div class="trip-card"><div class="trip-header"><div><h3>{trip.get("passenger", "Unknown")}</h3></div><span class="trip-status" style="background-color: {status_color}">{trip.get("status", "scheduled").replace("_", " ").title()}</span></div><div class="trip-details"><p><strong>Pickup:</strong> {trip.get("pickup", "TBA")}</p><p><strong>Dropoff:</strong> {trip.get("dropoff", "TBA")}</p></div></div>'
    if not trips:
        trips_html = '<p style="text-align: center; color: #999; padding: 20px;">No trips scheduled</p>'
    
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width"><title>Driver Dashboard</title><style>
body{{font-family:sans-serif;background:#f5f7fa;margin:0}}
.navbar{{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:20px 40px;display:flex;justify-content:space-between}}
.container{{max-width:1200px;margin:40px auto;padding:0 20px}}
.welcome{{background:white;padding:30px;border-radius:12px;margin-bottom:30px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px;margin-bottom:30px}}
.stat-card{{background:white;padding:20px;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,0.05)}}
.stat-value{{font-size:32px;font-weight:700;color:#667eea}}
.trips-section{{background:white;padding:30px;border-radius:12px}}
.trip-card{{border:1px solid #e0e0e0;border-radius:8px;padding:16px;margin-bottom:12px}}
.trip-status{{color:white;padding:4px 12px;border-radius:20px;font-size:12px}}
</style></head>
<body>
<div class="navbar"><h1>Arrow Limo {role.title()} Portal</h1><a href="/auth/logout" style="color:white;text-decoration:none">Logout</a></div>
<div class="container">
<div class="welcome"><h2>Welcome, {driver_name}!</h2></div>
<div class="stats">
<div class="stat-card"><div style="color:#999;font-size:12px">Trips Today</div><div class="stat-value">{len(trips)}</div></div>
<div class="stat-card"><div style="color:#999;font-size:12px">Status</div><div class="stat-value" style="color:#10b981">Active</div></div>
</div>
<div class="trips-section"><h3>Today's Trips</h3>{trips_html}</div>
</div>
</body></html>"""


def generate_admin_dashboard(admin_name: str, role: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Admin Dashboard</title><style>
body{{font-family:sans-serif;background:#f5f7fa;margin:0}}
.navbar{{background:linear-gradient(135deg,#e74c3c,#c0392b);color:white;padding:20px 40px;display:flex;justify-content:space-between}}
.container{{max-width:1200px;margin:40px auto;padding:0 20px}}
.welcome{{background:white;padding:30px;border-radius:12px;margin-bottom:30px}}
.tools{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px}}
.tool-card{{background:white;padding:20px;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,0.05)}}
</style></head>
<body>
<div class="navbar"><h1>Arrow Limo {role.title()} Panel</h1><a href="/auth/logout" style="color:white;text-decoration:none">Logout</a></div>
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
.navbar{{background:linear-gradient(135deg,#8e44ad,#2c3e50);color:white;padding:20px 40px;display:flex;justify-content:space-between}}
.container{{max-width:1200px;margin:40px auto;padding:0 20px}}
.welcome{{background:white;padding:30px;border-radius:12px;margin-bottom:30px;border-left:4px solid #8e44ad}}
.badge{{background:#8e44ad;color:white;padding:4px 12px;border-radius:20px;font-size:12px;display:inline-block;margin-top:10px}}
.tools{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px}}
.tool-card{{background:white;padding:20px;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,0.05)}}
</style></head>
<body>
<div class="navbar"><h1>Arrow Limo Super User Panel</h1><a href="/auth/logout" style="color:white;text-decoration:none">Logout</a></div>
<div class="container">
<div class="welcome"><h2>Welcome, {super_user_name}!</h2><div class="badge">SUPER USER</div></div>
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
.navbar{{background:linear-gradient(135deg,#3498db,#2980b9);color:white;padding:20px 40px;display:flex;justify-content:space-between}}
.container{{max-width:1200px;margin:40px auto;padding:0 20px}}
.welcome{{background:white;padding:30px;border-radius:12px}}
.role-badge{{background:#3498db;color:white;padding:4px 12px;border-radius:20px;font-size:12px;display:inline-block;margin-top:10px}}
</style></head>
<body>
<div class="navbar"><h1>Arrow Limo Portal</h1><a href="/auth/logout" style="color:white;text-decoration:none">Logout</a></div>
<div class="container">
<div class="welcome"><h2>Welcome, {user_name}!</h2><p>Role: {role}</p><div class="role-badge">{role.upper()}</div></div>
</div></body></html>"""
