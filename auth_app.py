<<<<<<< HEAD
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn
import os
from core.auth_service import register_user, authenticate_user, generate_otp, send_otp_email, verify_otp_code, reset_password

app = FastAPI(title="Aegis Ghost Auth")

# --- HTML TEMPLATES WITH PASSWORD MANAGER SUPPORT ---

STYLE = """
<style>
    body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
    .card { background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }
    input { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
    button { width: 100%; padding: 10px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
    button:hover { background: #0056b3; }
    .link { text-align: center; margin-top: 15px; font-size: 14px; }
    a { color: #007bff; text-decoration: none; }
    h2 { text-align: center; color: #333; }
</style>
"""

LOGIN_HTML = f"""
<!DOCTYPE html>
<html><head><title>Login</title>{STYLE}</head><body>
    <div class="card">
        <h2>Login</h2>
        <form action="/login" method="post">
            <label>Email</label>
            <input type="email" name="email" required autocomplete="username" placeholder="Enter email">
            <label>Password</label>
            <input type="password" name="password" required autocomplete="current-password" placeholder="Enter password">
            <button type="submit">Sign In</button>
        </form>
        <div class="link">
            <a href="/forgot-password">Forgot Password?</a> | <a href="/register">Create Account</a>
        </div>
    </div>
</body></html>
"""

REGISTER_HTML = f"""
<!DOCTYPE html>
<html><head><title>Register</title>{STYLE}</head><body>
    <div class="card">
        <h2>Create Account</h2>
        <form action="/register" method="post">
            <label>Email</label>
            <input type="email" name="email" required autocomplete="username" placeholder="Enter email">
            <label>New Password</label>
            <!-- autocomplete="new-password" triggers Google Password Manager to suggest a strong password -->
            <input type="password" name="password" required autocomplete="new-password" placeholder="Create strong password">
            <button type="submit" style="background: #28a745;">Register</button>
        </form>
        <div class="link"><a href="/login">Back to Login</a></div>
    </div>
</body></html>
"""

FORGOT_HTML = f"""
<!DOCTYPE html>
<html><head><title>Reset Password</title>{STYLE}</head><body>
    <div class="card">
        <h2>Reset Password</h2>
        <p style="text-align:center; color:#666;">Enter your email to receive an OTP.</p>
        <form action="/forgot-password" method="post">
            <input type="email" name="email" required autocomplete="username" placeholder="Enter your email">
            <button type="submit">Send OTP</button>
        </form>
        <div class="link"><a href="/login">Back to Login</a></div>
    </div>
</body></html>
"""

VERIFY_HTML = f"""
<!DOCTYPE html>
<html><head><title>Verify OTP</title>{STYLE}</head><body>
    <div class="card">
        <h2>Enter OTP</h2>
        <p style="text-align:center; color:#666;">Check your email for the code.</p>
        <form action="/verify-otp" method="post">
            <input type="hidden" name="email" value="{{email}}">
            <label>OTP Code</label>
            <input type="text" name="otp" required autocomplete="one-time-code" placeholder="123456">
            <label>New Password</label>
            <input type="password" name="new_password" required autocomplete="new-password" placeholder="Enter new password">
            <button type="submit" style="background: #dc3545;">Reset Password</button>
        </form>
    </div>
</body></html>
"""

@app.get("/", response_class=HTMLResponse)
async def index(): return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page(): return LOGIN_HTML

@app.post("/login", response_class=HTMLResponse)
async def login(email: str = Form(...), password: str = Form(...)):
    if authenticate_user(email, password):
        return f"<html><head>{STYLE}</head><body><div class='card'><h2>Welcome!</h2><p style='text-align:center'>Login Successful.</p><div class='link'><a href='/login'>Logout</a></div></div></body></html>"
    return LOGIN_HTML.replace("<h2>Login</h2>", "<h2 style='color:red'>Invalid Credentials</h2><h2>Login</h2>")

@app.get("/register", response_class=HTMLResponse)
async def register_page(): return REGISTER_HTML

@app.post("/register", response_class=HTMLResponse)
async def register(email: str = Form(...), password: str = Form(...)):
    success, msg = register_user(email, password)
    return f"<html><head>{STYLE}</head><body><div class='card'><h2>{'Success' if success else 'Error'}</h2><p style='text-align:center'>{msg}</p><div class='link'><a href='/login'>Login Now</a></div></div></body></html>"

@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_page(): return FORGOT_HTML

@app.post("/forgot-password", response_class=HTMLResponse)
async def send_otp_route(email: str = Form(...)):
    otp = generate_otp(email)
    success, msg = send_otp_email(email, otp)
    if success: return VERIFY_HTML.replace("{email}", email)
    return f"<html><head>{STYLE}</head><body><div class='card'><h2>Error</h2><p>{msg}</p><div class='link'><a href='/forgot-password'>Try Again</a></div></div></body></html>"

@app.post("/verify-otp", response_class=HTMLResponse)
async def verify_otp_route(email: str = Form(...), otp: str = Form(...), new_password: str = Form(...)):
    if verify_otp_code(email, otp):
        reset_password(email, new_password)
        return f"<html><head>{STYLE}</head><body><div class='card'><h2>Password Reset!</h2><p style='text-align:center'>You can now login with your new password.</p><div class='link'><a href='/login'>Login</a></div></div></body></html>"
    return f"<html><head>{STYLE}</head><body><div class='card'><h2>Invalid OTP</h2><p style='text-align:center'>The code was incorrect or expired.</p><div class='link'><a href='/forgot-password'>Try Again</a></div></div></body></html>"

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=3001)
=======
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn
import os
from core.auth_service import register_user, authenticate_user, generate_otp, send_otp_email, verify_otp_code, reset_password

app = FastAPI(title="Aegis Ghost Auth")

# --- HTML TEMPLATES WITH PASSWORD MANAGER SUPPORT ---

STYLE = """
<style>
    body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
    .card { background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }
    input { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
    button { width: 100%; padding: 10px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
    button:hover { background: #0056b3; }
    .link { text-align: center; margin-top: 15px; font-size: 14px; }
    a { color: #007bff; text-decoration: none; }
    h2 { text-align: center; color: #333; }
</style>
"""

LOGIN_HTML = f"""
<!DOCTYPE html>
<html><head><title>Login</title>{STYLE}</head><body>
    <div class="card">
        <h2>Login</h2>
        <form action="/login" method="post">
            <label>Email</label>
            <input type="email" name="email" required autocomplete="username" placeholder="Enter email">
            <label>Password</label>
            <input type="password" name="password" required autocomplete="current-password" placeholder="Enter password">
            <button type="submit">Sign In</button>
        </form>
        <div class="link">
            <a href="/forgot-password">Forgot Password?</a> | <a href="/register">Create Account</a>
        </div>
    </div>
</body></html>
"""

REGISTER_HTML = f"""
<!DOCTYPE html>
<html><head><title>Register</title>{STYLE}</head><body>
    <div class="card">
        <h2>Create Account</h2>
        <form action="/register" method="post">
            <label>Email</label>
            <input type="email" name="email" required autocomplete="username" placeholder="Enter email">
            <label>New Password</label>
            <!-- autocomplete="new-password" triggers Google Password Manager to suggest a strong password -->
            <input type="password" name="password" required autocomplete="new-password" placeholder="Create strong password">
            <button type="submit" style="background: #28a745;">Register</button>
        </form>
        <div class="link"><a href="/login">Back to Login</a></div>
    </div>
</body></html>
"""

FORGOT_HTML = f"""
<!DOCTYPE html>
<html><head><title>Reset Password</title>{STYLE}</head><body>
    <div class="card">
        <h2>Reset Password</h2>
        <p style="text-align:center; color:#666;">Enter your email to receive an OTP.</p>
        <form action="/forgot-password" method="post">
            <input type="email" name="email" required autocomplete="username" placeholder="Enter your email">
            <button type="submit">Send OTP</button>
        </form>
        <div class="link"><a href="/login">Back to Login</a></div>
    </div>
</body></html>
"""

VERIFY_HTML = f"""
<!DOCTYPE html>
<html><head><title>Verify OTP</title>{STYLE}</head><body>
    <div class="card">
        <h2>Enter OTP</h2>
        <p style="text-align:center; color:#666;">Check your email for the code.</p>
        <form action="/verify-otp" method="post">
            <input type="hidden" name="email" value="{{email}}">
            <label>OTP Code</label>
            <input type="text" name="otp" required autocomplete="one-time-code" placeholder="123456">
            <label>New Password</label>
            <input type="password" name="new_password" required autocomplete="new-password" placeholder="Enter new password">
            <button type="submit" style="background: #dc3545;">Reset Password</button>
        </form>
    </div>
</body></html>
"""

@app.get("/", response_class=HTMLResponse)
async def index(): return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page(): return LOGIN_HTML

@app.post("/login", response_class=HTMLResponse)
async def login(email: str = Form(...), password: str = Form(...)):
    if authenticate_user(email, password):
        return f"<html><head>{STYLE}</head><body><div class='card'><h2>Welcome!</h2><p style='text-align:center'>Login Successful.</p><div class='link'><a href='/login'>Logout</a></div></div></body></html>"
    return LOGIN_HTML.replace("<h2>Login</h2>", "<h2 style='color:red'>Invalid Credentials</h2><h2>Login</h2>")

@app.get("/register", response_class=HTMLResponse)
async def register_page(): return REGISTER_HTML

@app.post("/register", response_class=HTMLResponse)
async def register(email: str = Form(...), password: str = Form(...)):
    success, msg = register_user(email, password)
    return f"<html><head>{STYLE}</head><body><div class='card'><h2>{'Success' if success else 'Error'}</h2><p style='text-align:center'>{msg}</p><div class='link'><a href='/login'>Login Now</a></div></div></body></html>"

@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_page(): return FORGOT_HTML

@app.post("/forgot-password", response_class=HTMLResponse)
async def send_otp_route(email: str = Form(...)):
    otp = generate_otp(email)
    success, msg = send_otp_email(email, otp)
    if success: return VERIFY_HTML.replace("{email}", email)
    return f"<html><head>{STYLE}</head><body><div class='card'><h2>Error</h2><p>{msg}</p><div class='link'><a href='/forgot-password'>Try Again</a></div></div></body></html>"

@app.post("/verify-otp", response_class=HTMLResponse)
async def verify_otp_route(email: str = Form(...), otp: str = Form(...), new_password: str = Form(...)):
    if verify_otp_code(email, otp):
        reset_password(email, new_password)
        return f"<html><head>{STYLE}</head><body><div class='card'><h2>Password Reset!</h2><p style='text-align:center'>You can now login with your new password.</p><div class='link'><a href='/login'>Login</a></div></div></body></html>"
    return f"<html><head>{STYLE}</head><body><div class='card'><h2>Invalid OTP</h2><p style='text-align:center'>The code was incorrect or expired.</p><div class='link'><a href='/forgot-password'>Try Again</a></div></div></body></html>"

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
>>>>>>> e5fc0b8f35306ee3f5004b4278ee840afa3c8da4
