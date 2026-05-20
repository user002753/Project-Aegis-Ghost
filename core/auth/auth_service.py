import os
import json
import hashlib
import secrets
import smtplib
import time
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

# Get absolute paths based on this file's location
_AUTH_SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_AUTH_SERVICE_DIR))

USERS_FILE = os.path.join(_PROJECT_ROOT, "data", "users.json")
PROFILE_PICTURES_DIR = os.path.join(_PROJECT_ROOT, "data", "profile_pictures")
PROFILE_FACES_DIR = os.path.join(_PROJECT_ROOT, "data", "profile_faces")

# Debug: Print paths on import
print(f"[DEBUG] auth_service.py loaded from: {os.path.abspath(__file__)}")
print(f"[DEBUG] USERS_FILE resolved to: {USERS_FILE}")
print(f"[DEBUG] USERS_FILE exists: {os.path.exists(USERS_FILE)}")
OTP_STORAGE = {}  # In-memory storage for OTPs {email: {'otp': '123456', 'expires': timestamp}}
_USERS_CACHE = None
_USERS_MTIME = None
_ENV_LOADED = False


def _is_placeholder(value: str | None) -> bool:
    v = (value or "").strip().lower()
    if not v:
        return True
    markers = (
        "your_",
        "example",
        "changeme",
        "replace_me",
        "placeholder",
        "<",
        ">",
    )
    return any(m in v for m in markers)


def _as_bool(value, default=True):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _get_smtp_config():
    """
    Resolve SMTP settings with backward-compatible aliases.
    Priority:
    1) SMTP_* variables
    2) MAILTRAP_* variables
    """
    smtp_email = os.environ.get("SMTP_EMAIL") or os.environ.get("MAILTRAP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD") or os.environ.get("MAILTRAP_PASSWORD")
    smtp_server = os.environ.get("SMTP_SERVER") or os.environ.get("MAILTRAP_HOST")
    smtp_port_raw = os.environ.get("SMTP_PORT") or os.environ.get("MAILTRAP_PORT")
    smtp_timeout = float(os.environ.get("SMTP_TIMEOUT", "15"))
    smtp_sender_name = os.environ.get("SMTP_SENDER_NAME") or os.environ.get("MAILTRAP_SENDER_NAME") or "Project Aegis Ghost"
    smtp_sender_email = os.environ.get("SMTP_SENDER_EMAIL") or os.environ.get("MAILTRAP_SENDER_EMAIL") or smtp_email
    # Auto-default for Gmail when SMTP_* host/port are not explicitly set.
    if not smtp_server and smtp_email and smtp_email.strip().lower().endswith("@gmail.com"):
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
    else:
        smtp_server = smtp_server or "smtp.mailtrap.io"
        smtp_port = int(smtp_port_raw or ("587" if smtp_server == "smtp.gmail.com" else "2525"))

    smtp_use_tls = _as_bool(os.environ.get("SMTP_USE_TLS"), default=(smtp_port in (587, 2525)))
    smtp_use_ssl = _as_bool(os.environ.get("SMTP_USE_SSL"), default=(smtp_port == 465))
    return {
        "email": smtp_email,
        "password": smtp_password,
        "server": smtp_server,
        "port": smtp_port,
        "timeout": smtp_timeout,
        "sender_name": smtp_sender_name,
        "sender_email": smtp_sender_email,
        "use_tls": smtp_use_tls,
        "use_ssl": smtp_use_ssl,
    }


def _send_via_mailtrap_api(to_email: str, subject: str, body_text: str):
    token = os.environ.get("MAILTRAP_API_TOKEN") or os.environ.get("MAILTRAP_TOKEN")
    if not token:
        return False, "MAILTRAP_API_TOKEN is not configured."

    api_url = os.environ.get("MAILTRAP_API_URL", "https://send.api.mailtrap.io/api/send")
    sender_name = os.environ.get("MAILTRAP_FROM_NAME") or os.environ.get("SMTP_SENDER_NAME") or "Project Aegis Ghost"
    sender_email = (
        os.environ.get("MAILTRAP_FROM_EMAIL")
        or os.environ.get("SMTP_SENDER_EMAIL")
        or os.environ.get("SMTP_EMAIL")
        or "no-reply@aegis-ghost.local"
    )

    payload = {
        "from": {"email": sender_email, "name": sender_name},
        "to": [{"email": normalize_email(to_email)}],
        "subject": subject,
        "text": body_text,
    }
    category = os.environ.get("MAILTRAP_CATEGORY")
    if category:
        payload["category"] = category

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=float(os.environ.get("SMTP_TIMEOUT", "15"))) as resp:
            status = getattr(resp, "status", 200)
            if 200 <= status < 300:
                return True, "Email sent successfully (Mailtrap API)."
            return False, f"Mailtrap API returned status {status}."
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="ignore")
        except Exception:
            detail = str(e)
        return False, f"Mailtrap API error: {e.code} {detail}"
    except Exception as e:
        return False, f"Mailtrap API failed: {e}"

def _load_dotenv_if_present():
    """Load .env from project root into process env (non-destructive)."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, ".env")
    if not os.path.exists(env_path):
        _ENV_LOADED = True
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if len(value) >= 2 and (
                    (value[0] == '"' and value[-1] == '"') or
                    (value[0] == "'" and value[-1] == "'")
                ):
                    value = value[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = value
    finally:
        _ENV_LOADED = True

def normalize_email(email: str) -> str:
    return (email or "").strip().lower()

def ensure_data_dir():
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    os.makedirs(PROFILE_PICTURES_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump({}, f)

def load_users():
    global _USERS_CACHE, _USERS_MTIME
    ensure_data_dir()
    mtime = os.path.getmtime(USERS_FILE)
    if _USERS_CACHE is not None and _USERS_MTIME == mtime:
        return _USERS_CACHE
    print(f"[DEBUG] Loading users from: {USERS_FILE}")
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    _USERS_CACHE = data
    _USERS_MTIME = mtime
    print(f"[DEBUG] Loaded {len(data)} users")
    return data

def save_users(users):
    global _USERS_CACHE, _USERS_MTIME
    ensure_data_dir()
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4)
    _USERS_CACHE = users
    _USERS_MTIME = os.path.getmtime(USERS_FILE)

def hash_password(password, salt=None):
    if not salt:
        salt = secrets.token_hex(16)
    # PBKDF2 with SHA256
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 60000)
    return salt, key.hex()

def verify_password(stored_password, provided_password):
    salt = stored_password['salt']
    stored_hash = stored_password['hash']
    _, new_hash = hash_password(provided_password, salt)
    return new_hash == stored_hash

def register_user(email, password, name=None):
    email = normalize_email(email)
    users = load_users()
    if email in users:
        return False, "User already exists"

    salt, hashed = hash_password(password)
    users[email] = {
        'salt': salt,
        'hash': hashed,
        'name': (name or "").strip(),
        'id_no': "",
        'profile_picture': "",
        'face_reference_picture': "",
        'pattern_signature': "",
        'profile_completed': False,
        'created_at': int(time.time())
    }
    save_users(users)
    return True, "User registered successfully"

def authenticate_user(email, password):
    email = normalize_email(email)
    users = load_users()
    if email not in users:
        return False
    return verify_password(users[email], password)

def get_user(email):
    email = normalize_email(email)
    users = load_users()
    print(f"[DEBUG] get_user called with email: {email}")
    print(f"[DEBUG] Available users: {list(users.keys())}")
    user = users.get(email)
    print(f"[DEBUG] User found: {user is not None}")
    return user


def get_all_registered_users():
    """Get all registered users with basic info (for user search)"""
    users = load_users()
    result = []
    for email, data in users.items():
        result.append({
            "email": email,
            "name": data.get("name", ""),
            "profile_picture": data.get("profile_picture", ""),
            "profile_completed": data.get("profile_completed", False)
        })
    return result


def is_registered_user(email: str) -> bool:
    """Check if an email is registered"""
    user = get_user(email)
    return user is not None


def is_profile_complete(user: dict | None) -> bool:
    if not user:
        return False
    if user.get("profile_completed") is True:
        return True
    return bool((user.get("name") or "").strip() and (user.get("profile_picture") or "").strip())


def update_user_profile(email: str, name: str, id_no: str, profile_picture_rel_path: str):
    email = normalize_email(email)
    users = load_users()
    if email not in users:
        return False, "User not found"

    users[email]["name"] = (name or "").strip()
    users[email]["id_no"] = (id_no or "").strip()
    users[email]["profile_picture"] = (profile_picture_rel_path or "").strip()
    users[email]["profile_completed"] = is_profile_complete(users[email])
    users[email]["profile_updated_at"] = int(time.time())
    users[email].setdefault("face_reference_picture", "")
    users[email].setdefault("pattern_signature", "")
    save_users(users)
    return True, "Profile updated successfully"


def update_user_face_reference(email: str, face_picture_rel_path: str):
    email = normalize_email(email)
    print(f"[DEBUG] update_user_face_reference called with email: {email}, path: {face_picture_rel_path}")
    users = load_users()
    if email not in users:
        return False, "User not found"

    users[email]["face_reference_picture"] = (face_picture_rel_path or "").strip()
    users[email]["biometric_updated_at"] = int(time.time())
    users[email].setdefault("pattern_signature", "")
    save_users(users)
    print(f"[DEBUG] Face reference saved for {email}")
    return True, "Face reference updated successfully"


def update_user_pattern_signature(email: str, pattern_signature: str):
    email = normalize_email(email)
    users = load_users()
    if email not in users:
        return False, "User not found"

    users[email]["pattern_signature"] = (pattern_signature or "").strip()
    users[email]["biometric_updated_at"] = int(time.time())
    users[email].setdefault("face_reference_picture", "")
    save_users(users)
    return True, "Pattern updated successfully"

def generate_otp(email):
    email = normalize_email(email)
    # Generate 6-digit OTP
    otp = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    OTP_STORAGE[email] = {
        'otp': otp,
        'expires': time.time() + 300  # 5 minutes expiration
    }
    print(f"\n[OTP GENERATED] Email: {email}  |  OTP: {otp}  |  Expires in 5 min")
    return otp

def _print_mock_email(to_email: str, otp: str):
    """Print a styled mock OTP email to the terminal and write to mock_otp.log."""
    border = "=" * 60
    inner = "-" * 60
    lines = [
        f"\n{border}",
        "  📧  MOCK EMAIL  [ Password Reset OTP ]",
        border,
        f"  From    : Project Aegis Ghost <no-reply@aegis-ghost.local>",
        f"  To      : {to_email}",
        f"  Subject : Project Aegis Ghost - Password Reset OTP",
        inner,
        "",
        "  Your One-Time Password (OTP) for resetting your password:",
        "",
        f"      ┌─────────────────┐",
        f"      │   OTP : {otp}   │",
        f"      └─────────────────┘",
        "",
        "  ⏱  This code expires in 5 minutes.",
        "  ⚠  If you did not request this, ignore this email.",
        "",
        border + "\n",
    ]
    output = "\n".join(lines)

    # Print to backend terminal
    print(output)

    # Also write to mock_otp.log in project root so it's visible in VS Code / any editor
    try:
        log_path = os.path.join(_PROJECT_ROOT, "mock_otp.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"  📄  OTP saved to: {log_path}\n")
    except Exception:
        pass


def send_otp_email(email, otp):
    _load_dotenv_if_present()
    email = normalize_email(email)
    cfg = _get_smtp_config()
    smtp_email = cfg["email"]
    smtp_password = cfg["password"]
    smtp_server = cfg["server"]
    smtp_port = cfg["port"]
    smtp_timeout = cfg["timeout"]
    smtp_sender_name = cfg["sender_name"]
    smtp_sender_email = cfg["sender_email"]
    subject = "Project Aegis Ghost - Password Reset OTP"
    body = (
        f"Your One-Time Password (OTP) is: {otp}\n\n"
        "This code expires in 5 minutes.\n"
        "If you did not request this, please ignore this email."
    )

    # ── MOCK MODE ── triggered by SMTP_PASSWORD=MOCK or SMTP_PASSWORD=TEST
    if smtp_password in ("MOCK", "TEST"):
        _print_mock_email(email, otp)
        return True, "Mock email sent (check server console for OTP)"

    # ── PLACEHOLDER / NOT CONFIGURED ── fallback to mock so the flow always works in dev
    if _is_placeholder(smtp_email) or _is_placeholder(smtp_password):
        print("\n[WARN] SMTP not configured — falling back to MOCK mode.")
        _print_mock_email(email, otp)
        return True, "Mock email sent (SMTP not configured — check server console for OTP)"

    # Prefer explicit SMTP config; use Mailtrap API only when explicitly enabled or SMTP creds are absent.
    use_mailtrap_api = _as_bool(os.environ.get("MAILTRAP_USE_API"), default=False)
    smtp_configured = bool(smtp_email and smtp_password)
    if not smtp_configured and (os.environ.get("MAILTRAP_API_TOKEN") or os.environ.get("MAILTRAP_TOKEN")):
        use_mailtrap_api = True
    if use_mailtrap_api and (os.environ.get("MAILTRAP_API_TOKEN") or os.environ.get("MAILTRAP_TOKEN")):
        sent, msg = _send_via_mailtrap_api(email, subject, body)
        if sent:
            return True, msg

    if not smtp_email or not smtp_password:
        return False, (
            "SMTP is not configured. Set SMTP_EMAIL and SMTP_PASSWORD "
            "or MAILTRAP_API_TOKEN to send OTP email. Use 'MOCK' as password for testing."
        )

    try:
        msg = MIMEMultipart()
        msg['From'] = formataddr((smtp_sender_name, smtp_sender_email))
        msg['To'] = email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        if cfg["use_ssl"] or smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=smtp_timeout)
            server.ehlo()
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=smtp_timeout)
            server.ehlo()
            if cfg["use_tls"]:
                server.starttls()
                server.ehlo()
        server.login(smtp_email, smtp_password)
        server.send_message(msg)
        server.quit()
        return True, "Email sent successfully"
    except Exception as e:
        message = str(e)
        if "gmail" in smtp_server.lower():
            message = (
                f"Email failed: {e}. For Gmail, enable 2-Step Verification and "
                "use a 16-character App Password as SMTP_PASSWORD."
            )
        return False, message

def send_test_email(email=None):
    _load_dotenv_if_present()
    cfg = _get_smtp_config()
    smtp_email = cfg["email"]
    smtp_password = cfg["password"]
    smtp_server = cfg["server"]
    smtp_port = cfg["port"]
    smtp_timeout = cfg["timeout"]
    smtp_sender_name = cfg["sender_name"]
    smtp_sender_email = cfg["sender_email"]
    subject = "Project Aegis Ghost - SMTP Test"
    
    # Check for mock/test mode
    if smtp_password == "MOCK" or smtp_password == "TEST":
        recipient = normalize_email(email) if email else normalize_email(smtp_email)
        print("\n" + "="*50)
        print("MOCK TEST EMAIL")
        print("="*50)
        print(f"To: {recipient}")
        print(f"Subject: {subject}")
        print(f"Body: This is a test email from Project Aegis Ghost.")
        print("="*50 + "\n")
        return True, "Mock test email sent (check server console)"

    if _is_placeholder(smtp_email) or _is_placeholder(smtp_password):
        return False, (
            "SMTP credentials are placeholders. Configure SMTP_EMAIL as your Gmail address and "
            "SMTP_PASSWORD as a 16-character Gmail App Password."
        )

    # Prefer explicit SMTP config; use Mailtrap API only when explicitly enabled or SMTP creds are absent.
    use_mailtrap_api = _as_bool(os.environ.get("MAILTRAP_USE_API"), default=False)
    smtp_configured = bool(smtp_email and smtp_password)
    if not smtp_configured and (os.environ.get("MAILTRAP_API_TOKEN") or os.environ.get("MAILTRAP_TOKEN")):
        use_mailtrap_api = True
    if use_mailtrap_api and (os.environ.get("MAILTRAP_API_TOKEN") or os.environ.get("MAILTRAP_TOKEN")):
        recipient = normalize_email(email) if email else normalize_email(smtp_email)
        body = (
            "SMTP/API test successful.\n\n"
            "Your Mailtrap configuration is working for Project Aegis Ghost."
        )
        sent, msg = _send_via_mailtrap_api(recipient, subject, body)
        if sent:
            return True, f"Mailtrap API test email sent to {recipient}"

    if not smtp_email or not smtp_password:
        return False, (
            "SMTP is not configured. Set SMTP_EMAIL and SMTP_PASSWORD "
            "or MAILTRAP_API_TOKEN to send email. Use 'MOCK' as password for testing."
        )

    recipient = normalize_email(email) if email else normalize_email(smtp_email)

    try:
        msg = MIMEMultipart()
        msg['From'] = formataddr((smtp_sender_name, smtp_sender_email))
        msg['To'] = recipient
        msg['Subject'] = subject
        body = (
            "SMTP test successful.\n\n"
            "Your SMTP configuration is working for Project Aegis Ghost."
        )
        msg.attach(MIMEText(body, 'plain'))

        if cfg["use_ssl"] or smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=smtp_timeout)
            server.ehlo()
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=smtp_timeout)
            server.ehlo()
            if cfg["use_tls"]:
                server.starttls()
                server.ehlo()

        server.login(smtp_email, smtp_password)
        server.send_message(msg)
        server.quit()
        return True, f"SMTP test email sent to {recipient}"
    except Exception as e:
        message = str(e)
        if "gmail" in smtp_server.lower():
            message = (
                f"Email failed: {e}. For Gmail, enable 2-Step Verification and "
                "use a 16-character App Password as SMTP_PASSWORD."
            )
        return False, message

def verify_otp_code(email, code):
    email = normalize_email(email)
    if email not in OTP_STORAGE:
        return False
    data = OTP_STORAGE[email]
    if time.time() > data['expires']:
        return False
    if data['otp'] == code:
        del OTP_STORAGE[email] # Consume OTP
        return True
    return False

def reset_password(email, new_password):
    email = normalize_email(email)
    users = load_users()
    if email not in users:
        return False, "User not found"
    
    salt, hashed = hash_password(new_password)
    users[email]['salt'] = salt
    users[email]['hash'] = hashed
    save_users(users)
    return True, "Password reset successfully"
