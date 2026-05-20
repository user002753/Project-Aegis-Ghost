// IP Address Change Detection Service
// Monitors IP changes to detect unusual login behavior

const IP_STORAGE_KEY = 'aegis_ip_history';
const IP_CHANGE_EVENT = 'aegis_ip_changed';

class IPDetectionService {
  constructor() {
    this.currentIP = null;
    this.ipHistory = this.loadHistory();
    this.listeners = [];
    this.isMonitoring = false;
  }

  loadHistory() {
    try {
      const saved = localStorage.getItem(IP_STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  }

  saveHistory() {
    localStorage.setItem(IP_STORAGE_KEY, JSON.stringify(this.ipHistory));
  }

  addListener(callback) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter(cb => cb !== callback);
    };
  }

  notifyListeners(event) {
    this.listeners.forEach(cb => cb(event));
  }

  async getCurrentIP() {
    try {
      // Try multiple IP detection services
      const services = [
        'https://api.ipify.org?format=json',
        'https://api64.ipify.org?format=json',
        'https://ifconfig.me/ip',
        'https://icanhazip.com'
      ];

      for (const service of services) {
        try {
          const response = await fetch(service);
          if (response.ok) {
            const data = await response.json();
            return data.ip || data;
          }
        } catch {
          continue;
        }
      }

      // Fallback: try any available service
      const fallbackResponse = await fetch('https://api.ipify.org?format=json');
      const fallbackData = await fallbackResponse.json();
      return fallbackData.ip;
    } catch (error) {
      console.warn('Could not detect IP address:', error);
      return null;
    }
  }

  async getLocationFromIP(ip) {
    // For localhost/127.0.0.1, use browser geolocation
    if (ip === '127.0.0.1' || ip === 'localhost' || ip.startsWith('192.168.') || ip.startsWith('10.')) {
      try {
        const position = await this.getBrowserLocation();
        if (position) {
          // Reverse geocode using a free service
          try {
            const response = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${position.latitude}&lon=${position.longitude}&format=json`);
            if (response.ok) {
              const data = await response.json();
              return {
                country: data.address?.country || 'Unknown',
                region: data.address?.state || data.address?.county || 'Unknown',
                city: data.address?.city || data.address?.town || data.address?.village || 'Unknown',
                isp: 'Local Network',
                latitude: position.latitude,
                longitude: position.longitude,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
              };
            }
          } catch (e) {
            console.warn('Reverse geocoding failed:', e);
          }
          return {
            country: 'Local',
            region: 'Local Network',
            city: 'localhost',
            isp: 'Local Network',
            latitude: position.latitude,
            longitude: position.longitude,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
          };
        }
      } catch (e) {
        console.warn('Browser geolocation failed:', e);
      }
      return { country: 'Local', region: 'Development', city: 'localhost', isp: 'Local Network', latitude: 37.7749, longitude: -122.4194 };
    }
    
    // Use free IP geolocation API (no API key required)
    // ipwho.is provides free geolocation without authentication
    try {
      const response = await fetch(`https://ipwho.is/${ip}`);
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          return {
            country: data.country || 'Unknown',
            region: data.region || 'Unknown',
            city: data.city || 'Unknown',
            isp: data.connection?.isp || 'Unknown',
            latitude: data.latitude,
            longitude: data.longitude,
            timezone: data.timezone?.id || 'Unknown'
          };
        }
      }
    } catch (error) {
      console.warn('IP geolocation failed, using fallback:', error);
    }
    
    // Fallback: try ip-api.com (free, 45 requests/minute, no API key)
    try {
      const response = await fetch(`http://ip-api.com/json/${ip}?fields=status,country,regionName,city,isp,lat,lon,timezone`);
      if (response.ok) {
        const data = await response.json();
        if (data.status === 'success') {
          return {
            country: data.country || 'Unknown',
            region: data.regionName || 'Unknown',
            city: data.city || 'Unknown',
            isp: data.isp || 'Unknown',
            latitude: data.lat,
            longitude: data.lon,
            timezone: data.timezone || 'Unknown'
          };
        }
      }
    } catch (error) {
      console.warn('IP-API fallback also failed:', error);
    }
    
    // Ultimate fallback: basic estimation
    return this.getBasicLocationFromIP(ip);
  }
  
  getBrowserLocation() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error('Geolocation not supported'));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (position) => resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude
        }),
        (error) => reject(error),
        { enableHighAccuracy: true, timeout: 5000 }
      );
    });
  }
  
  getBasicLocationFromIP(ip) {
    // Basic location estimation based on IP patterns
    // This is a last resort fallback
    const locationPatterns = {
      'US': { country: 'United States', region: 'North America' },
      'GB': { country: 'United Kingdom', region: 'Europe' },
      'DE': { country: 'Germany', region: 'Europe' },
      'FR': { country: 'France', region: 'Europe' },
      'IN': { country: 'India', region: 'Asia' },
      'CN': { country: 'China', region: 'Asia' },
      'JP': { country: 'Japan', region: 'Asia' },
      'AU': { country: 'Australia', region: 'Oceania' },
      'BR': { country: 'Brazil', region: 'South America' },
    };

    // Extract country code from IP (simplified - in production use proper geolocation)
    const countryCode = ip.substring(0, 2).toUpperCase();
    return locationPatterns[countryCode] || { country: 'Unknown', region: 'Unknown', latitude: 37.7749, longitude: -122.4194 };
  }

  async checkIPChange() {
    const newIP = await this.getCurrentIP();
    if (!newIP) {
      return { changed: false, ip: null, error: 'Could not detect IP' };
    }

    const lastIP = this.ipHistory.length > 0 ? this.ipHistory[0].ip : null;
    const location = await this.getLocationFromIP(newIP);
    const timestamp = new Date().toISOString();

    const ipEntry = {
      ip: newIP,
      location,
      timestamp,
    };

    const changed = lastIP !== newIP;

    if (changed) {
      this.ipHistory.unshift(ipEntry);
      // Keep only last 20 entries
      this.ipHistory = this.ipHistory.slice(0, 20);
      this.saveHistory();

      const event = {
        type: changed ? 'IP_CHANGED' : 'IP_CHECKED',
        previousIP: lastIP,
        currentIP: newIP,
        location,
        timestamp,
        isSuspicious: this.isSuspiciousChange(lastIP, newIP),
      };

      this.notifyListeners(event);
    }

    this.currentIP = newIP;
    return {
      changed,
      ip: newIP,
      location,
      timestamp,
      history: this.ipHistory.slice(0, 5),
    };
  }

  isSuspiciousChange(previousIP, currentIP) {
    if (!previousIP) return false;

    // Check for frequent changes in short time
    const recentChanges = this.ipHistory.filter(
      entry => new Date() - new Date(entry.timestamp) < 3600000 // 1 hour
    ).length;

    if (recentChanges > 3) return true;

    // Check for location jump (simplified)
    const prevLocation = this.getLocationFromIP(previousIP);
    const currLocation = this.getLocationFromIP(currentIP);

    if (prevLocation.region !== currLocation.region && 
        prevLocation.region !== 'Unknown' && 
        currLocation.region !== 'Unknown') {
      return true;
    }

    return false;
  }

  startMonitoring(intervalMinutes = 5) {
    if (this.isMonitoring) return;

    this.isMonitoring = true;
    
    // Initial check
    this.checkIPChange();

    // Set up periodic monitoring
    this.intervalId = setInterval(
      () => this.checkIPChange(),
      intervalMinutes * 60 * 1000
    );

    console.log(`[IP Detection] Started monitoring (every ${intervalMinutes} minutes)`);
  }

  stopMonitoring() {
    if (!this.isMonitoring) return;

    this.isMonitoring = false;
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    console.log('[IP Detection] Stopped monitoring');
  }

  getHistory() {
    return this.ipHistory;
  }

  clearHistory() {
    this.ipHistory = [];
    this.saveHistory();
  }

  getCurrentStatus() {
    const lastEntry = this.ipHistory[0];
    return {
      currentIP: this.currentIP,
      lastChecked: lastEntry?.timestamp,
      isMonitoring: this.isMonitoring,
      totalChanges: this.ipHistory.length,
    };
  }
}

// Export singleton instance
const ipDetectionService = new IPDetectionService();

export default ipDetectionService;

// Helper function to use in React components
export function useIPDetection() {
  return ipDetectionService;
}
