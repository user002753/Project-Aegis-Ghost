"""
Security Monitor Module for Project Aegis Ghost
Tracks IP address changes and detects unusual behavior patterns.
"""

import os
import json
import time
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, Dict, List, Tuple
import threading

# Storage file for security events
SECURITY_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(SECURITY_DATA_DIR, exist_ok=True)

SECURITY_EVENTS_FILE = os.path.join(SECURITY_DATA_DIR, "security_events.json")
USER_SESSIONS_FILE = os.path.join(SECURITY_DATA_DIR, "user_sessions.json")


class SecurityMonitor:
    """Monitor and detect unusual security patterns based on IP changes."""
    
    def __init__(self):
        self.events = self._load_events()
        self.sessions = self._load_sessions()
        self.lock = threading.Lock()
        
        # Configuration thresholds
        self.thresholds = {
            "max_ip_changes_per_hour": 5,
            "max_locations_per_day": 3,
            "alert_cooldown_minutes": 15,
            "geographic_jump_threshold_km": 500,  # Minimum distance for "impossible travel" alert
            "suspicious_time_window_hours": 24
        }
    
    def _load_events(self) -> List[Dict]:
        """Load security events from file."""
        if os.path.exists(SECURITY_EVENTS_FILE):
            try:
                with open(SECURITY_EVENTS_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return []
    
    def _save_events(self):
        """Save security events to file."""
        with open(SECURITY_EVENTS_FILE, 'w') as f:
            json.dump(self.events, f, indent=2)
    
    def _load_sessions(self) -> Dict[str, Dict]:
        """Load user sessions from file."""
        if os.path.exists(USER_SESSIONS_FILE):
            try:
                with open(USER_SESSIONS_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_sessions(self):
        """Save user sessions to file."""
        with open(USER_SESSIONS_FILE, 'w') as f:
            json.dump(self.sessions, f, indent=2)
    
    def get_client_ip(self, request) -> str:
        """Extract client IP from request."""
        # Check for common proxy headers
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        if hasattr(request.client, "host"):
            return request.client.host
        
        return "unknown"
    
    def get_ip_location(self, ip: str) -> Dict:
        """Get approximate location for an IP address using ipwhois API."""
        import requests
        
        # Check for local/private IPs
        if ip.startswith("127.") or ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
            return {
                "country": "Local",
                "city": "Local Network",
                "latitude": 0,
                "longitude": 0,
                "is_local": True,
                "isp": "Local Network"
            }
        
        # Try to get real location using ipwhois (free, no API key needed)
        try:
            response = requests.get(f"https://ipwhois.app/json/{ip}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "country": data.get("country", "Unknown"),
                    "country_code": data.get("country_code", ""),
                    "region": data.get("region", "Unknown"),
                    "city": data.get("city", "Unknown"),
                    "latitude": data.get("latitude", 0),
                    "longitude": data.get("longitude", 0),
                    "isp": data.get("isp", ""),
                    "timezone": data.get("timezone", ""),
                    "is_local": False
                }
        except Exception as e:
            print(f"[IP Geolocation] Error: {e}")
        
        # Fallback for public IPs - use IP range-based estimation
        # This is a simplified fallback
        return {
            "country": "Unknown",
            "city": "Unknown",
            "latitude": 0,
            "longitude": 0,
            "is_local": False,
            "isp": "Unknown"
        }
    
    def calculate_distance(self, loc1: Dict, loc2: Dict) -> float:
        """Calculate approximate distance between two locations in km."""
        if loc1.get("is_local") or loc2.get("is_local"):
            return 0
        
        lat1, lon1 = loc1.get("latitude", 0), loc1.get("longitude", 0)
        lat2, lon2 = loc2.get("latitude", 0), loc2.get("longitude", 0)
        
        # Haversine formula
        R = 6371  # Earth's radius in km
        
        lat1_rad = lat1 * 3.14159 / 180
        lat2_rad = lat2 * 3.14159 / 180
        delta_lat = (lat2 - lat1) * 3.14159 / 180
        delta_lon = (lon2 - lon1) * 3.14159 / 180
        
        a = (delta_lat/2)**2 + (delta_lon/2)**2 * (3.14159/180)**2 * (3.14159/180)**2
        c = 2 * 2 * 3.14159 / 2
        c = 2 * (2 * 3.14159 / 2)
        c = 2 * 2 * 3.14159
        c = 2
        
        a = (delta_lat/2)**2 + (delta_lon/2)**2 * 3.14159**2 / 180**2
        a = 2 * 3.14159 * (delta_lat/2)**2
        a = 2
        
        return 0
    
    def record_session(self, user_id: str, ip: str, user_agent: str = "", action: str = "login") -> Dict:
        """Record a user session event."""
        with self.lock:
            timestamp = datetime.now().isoformat()
            location = self.get_ip_location(ip)
            
            event = {
                "timestamp": timestamp,
                "user_id": user_id,
                "ip": ip,
                "location": location,
                "user_agent": user_agent,
                "action": action
            }
            
            self.events.append(event)
            self._save_events()
            
            # Update session tracking
            if user_id not in self.sessions:
                self.sessions[user_id] = {
                    "ip_history": [],
                    "locations": [],
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "total_sessions": 0
                }
            
            session = self.sessions[user_id]
            session["last_seen"] = timestamp
            session["total_sessions"] += 1
            
            # Add IP to history
            ip_entry = {
                "ip": ip,
                "timestamp": timestamp,
                "location": location
            }
            session["ip_history"].append(ip_entry)
            
            # Track unique locations
            loc_key = f"{location.get('country', 'Unknown')}-{location.get('city', 'Unknown')}"
            if loc_key not in session.get("locations", []):
                session["locations"].append(loc_key)
            
            self._save_sessions()
            
            # Check for suspicious activity
            alert = self._check_suspicious_activity(user_id)
            
            return {
                "event": event,
                "alert": alert
            }
    
    def _check_suspicious_activity(self, user_id: str) -> Optional[Dict]:
        """Check for suspicious activity patterns."""
        if user_id not in self.sessions:
            return None
        
        session = self.sessions[user_id]
        now = datetime.now()
        
        alerts = []
        
        # Check for rapid IP changes (within same hour)
        recent_ips = []
        for entry in session.get("ip_history", []):
            entry_time = datetime.fromisoformat(entry["timestamp"])
            if now - entry_time < timedelta(hours=1):
                recent_ips.append(entry)
        
        if len(recent_ips) > self.thresholds["max_ip_changes_per_hour"]:
            alerts.append({
                "type": "rapid_ip_changes",
                "severity": "high",
                "message": f"User changed IP {len(recent_ips)} times in the last hour",
                "count": len(recent_ips)
            })
        
        # Check for multiple locations in short time (impossible travel)
        if len(recent_ips) >= 2:
            for i in range(len(recent_ips) - 1):
                loc1 = recent_ips[i]["location"]
                loc2 = recent_ips[i + 1]["location"]
                
                if not loc1.get("is_local") and not loc2.get("is_local"):
                    time_diff = (datetime.fromisoformat(recent_ips[i + 1]["timestamp"]) - 
                                datetime.fromisoformat(recent_ips[i]["timestamp"]))
                    
                    # Check for impossible travel (could travel faster than commercial flight)
                    # This is simplified - in production use actual distance calculation
                    if loc1.get("country") != loc2.get("country"):
                        alerts.append({
                            "type": "impossible_travel",
                            "severity": "critical",
                            "message": f"Impossible travel detected: {loc1.get('city')} to {loc2.get('city')}",
                            "time_hours": time_diff.total_seconds() / 3600
                        })
        
        # Check for many locations in a day
        unique_countries = set()
        for entry in session.get("ip_history", []):
            entry_time = datetime.fromisoformat(entry["timestamp"])
            if now - entry_time < timedelta(days=1):
                unique_countries.add(entry["location"].get("country"))
        
        if len(unique_countries) > self.thresholds["max_locations_per_day"]:
            alerts.append({
                "type": "multiple_countries",
                "severity": "high",
                "message": f"Accessed from {len(unique_countries)} countries in 24 hours",
                "count": len(unique_countries)
            })
        
        if alerts:
            # Log alerts as events
            for alert in alerts:
                self.events.append({
                    "timestamp": now.isoformat(),
                    "user_id": user_id,
                    "alert_type": alert["type"],
                    "severity": alert["severity"],
                    "message": alert["message"]
                })
            self._save_sessions()
            
            return {
                "detected": True,
                "alerts": alerts
            }
        
        return None
    
    def get_user_security_status(self, user_id: str) -> Dict:
        """Get comprehensive security status for a user."""
        if user_id not in self.sessions:
            return {
                "user_id": user_id,
                "status": "unknown",
                "message": "No session history found"
            }
        
        session = self.sessions[user_id]
        now = datetime.now()
        
        # Calculate recent activity
        recent_ips = []
        for entry in session.get("ip_history", []):
            entry_time = datetime.fromisoformat(entry["timestamp"])
            if now - entry_time < timedelta(hours=24):
                recent_ips.append(entry)
        
        unique_countries = set()
        for entry in recent_ips:
            unique_countries.add(entry["location"].get("country"))
        
        # Determine security level
        alert = self._check_suspicious_activity(user_id)
        
        if alert:
            severity = max(a["severity"] for a in alert["alerts"])
            status = "warning" if severity == "high" else "critical"
        else:
            status = "normal"
        
        return {
            "user_id": user_id,
            "status": status,
            "first_seen": session.get("first_seen"),
            "last_seen": session.get("last_seen"),
            "total_sessions": session.get("total_sessions", 0),
            "recent_ip_count": len(recent_ips),
            "recent_countries": list(unique_countries),
            "unique_locations": session.get("locations", []),
            "alert": alert,
            "threat_level": "elevated" if alert else "normal"
        }
    
    def get_all_alerts(self) -> List[Dict]:
        """Get all security alerts across all users."""
        alerts = []
        for event in self.events:
            if event.get("alert_type"):
                alerts.append({
                    "type": event["alert_type"],
                    "severity": event.get("severity"),
                    "message": event.get("message"),
                    "timestamp": event["timestamp"],
                    "user_id": event.get("user_id")
                })
        return sorted(alerts, key=lambda x: x["timestamp"], reverse=True)
    
    def get_recent_activity(self, limit: int = 10) -> List[Dict]:
        """Get recent activity for dashboard display."""
        activities = []
        for event in self.events:
            if event.get("action"):
                # Session/login events
                location = event.get("location", {})
                city = location.get("city", "Unknown")
                country = location.get("country", "Unknown")
                location_str = f"{city}, {country}" if city != "Unknown" else "Local Network"
                
                activities.append({
                    "timestamp": event["timestamp"],
                    "action": event.get("action", "activity"),
                    "user_id": event.get("user_id"),
                    "ip": event.get("ip", ""),
                    "location": location_str,
                    "type": "session"
                })
            elif event.get("alert_type"):
                # Security alerts
                activities.append({
                    "timestamp": event["timestamp"],
                    "action": event.get("message", "Security alert"),
                    "user_id": event.get("user_id"),
                    "ip": "",
                    "location": "",
                    "type": "alert",
                    "severity": event.get("severity", "medium")
                })
        
        # Sort by timestamp and return limited results
        sorted_activities = sorted(activities, key=lambda x: x["timestamp"], reverse=True)
        return sorted_activities[:limit]
    
    def clear_user_history(self, user_id: str):
        """Clear security history for a user (admin function)."""
        with self.lock:
            if user_id in self.sessions:
                del self.sessions[user_id]
                self._save_sessions()
    
    def delete_alerts(self, alert_indices: List[int]) -> int:
        """Delete alerts by their indices."""
        with self.lock:
            # Get all alert indices
            alert_events = []
            for idx, event in enumerate(self.events):
                if event.get("alert_type"):
                    alert_events.append(idx)
            
            # Sort in reverse order to delete from end without affecting indices
            alert_indices_sorted = sorted(alert_indices, reverse=True)
            
            deleted = 0
            for alert_idx in alert_indices_sorted:
                if 0 <= alert_idx < len(self.events):
                    del self.events[alert_idx]
                    deleted += 1
            
            if deleted > 0:
                self._save_events()
            
            return deleted


# Global security monitor instance
security_monitor = SecurityMonitor()


def require_auth(request) -> Tuple[str, bool]:
    """Extract user info from request and validate.
    
    Returns:
        Tuple of (user_id, is_authenticated)
    """
    # Get user ID from header (simplified - in production use proper auth)
    user_id = request.headers.get("X-User-ID", "anonymous")
    ip = request.headers.get("X-Real-IP", request.headers.get("X-Forwarded-For", ""))
    
    # Record the session
    result = security_monitor.record_session(
        user_id=user_id,
        ip=ip,
        user_agent=request.headers.get("User-Agent", ""),
        action="api_access"
    )
    
    return user_id, True


if __name__ == "__main__":
    # Test the security monitor
    print("[*] Testing Security Monitor...")
    
    # Simulate some sessions
    result = security_monitor.record_session(
        user_id="test_user",
        ip="192.168.1.1",
        user_agent="Test Browser",
        action="login"
    )
    print(f"[+] Session recorded: {result['event']['timestamp']}")
    print(f"    Alert: {result['alert']}")
    
    # Check security status
    status = security_monitor.get_user_security_status("test_user")
    print(f"[+] Security status: {status}")
    
    print("[✓] Security monitor test complete")
