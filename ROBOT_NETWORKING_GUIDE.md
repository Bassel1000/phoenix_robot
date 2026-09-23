# 📡 Phoenix Robot - Network & Hotspot Connection Guide

This guide documents the **3 tested and verified networking methods** used to communicate with the Phoenix Robot's Raspberry Pi 4 (`ambers-desktop`).

---

## 📋 Quick Reference Card

| Method | SSID / Medium | Frequency Band | Pi Hostname / Typical IP | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **1. Laptop Hotspot** | `Phoenix_Laptop` | **2.4 GHz** | `192.168.137.163` / `ambers-desktop.local` | **Exhibition / Fair Demo** (Untethered, laptop keeps internet) |
| **2. Phone Hotspot** | `phoenix` | **2.4 GHz** | Dynamic / `ambers-desktop.local` | **Arena Testing** (Independent cellular data) |
| **3. Direct Ethernet** | Physical RJ45 Cable | N/A | `192.168.137.42` / `ambers-desktop.mshome.net` | **Benchtop Testing & Flashing** (No Wi-Fi needed) |

* **Default Username:** `ambers`
* **Default Hostname:** `ambers-desktop` (`ambers-desktop.local`)
* **SSH Port:** `22`

---

## 💻 Method 1: Windows Laptop Mobile Hotspot (Recommended for Fairs)

Allows the robot to drive completely wirelessly while your laptop simultaneously stays connected to venue Wi-Fi or cellular internet.

### 1. Laptop Configuration (Windows 10/11)
1. Open Windows **Settings $\rightarrow$ Network & Internet $\rightarrow$ Mobile hotspot**.
2. Click **Edit** and set:
   * **Network Name (SSID):** `Phoenix_Laptop`
   * **Network Password:** `ambers2026`
   * **Network Band:** **2.4 GHz** *(Required: Raspberry Pi 4 reliably discovers 2.4 GHz soft-APs)*.
3. Toggle the **Mobile hotspot** switch to **ON**.

> [!IMPORTANT]
> **The ICS Conflict Rule:**
> If you previously used the direct Ethernet cable, Windows may lock the DHCP server (`192.168.137.1`) to the Ethernet port. If the Pi fails with *"IP configuration could not be reserved"*:
> 1. Press `Win + R`, type `ncpa.cpl`, and hit Enter.
> 2. Right-click **Wi-Fi** $\rightarrow$ **Properties** $\rightarrow$ **Sharing** tab.
> 3. Ensure **"Allow other network users to connect..."** is **UNCHECKED**.
> 4. Toggle Windows Mobile Hotspot OFF and back ON.

### 2. Connect from Laptop Terminal
Open PowerShell or Antigravity Terminal:
```powershell
ssh ambers@192.168.137.163
# or
ssh ambers@ambers-desktop.local
```

---

## 📱 Method 2: Mobile Phone Hotspot (Cellular Arena Setup)

Best when you want both your laptop and robot connected to high-speed 4G/5G mobile internet.

### 1. Phone Configuration
1. On your phone (Android / iPhone), go to **Personal Hotspot**.
2. Set **Hotspot Name (SSID):** `phoenix`
3. Set **Password:** (Your configured password)
4. **Enable 2.4 GHz:**
   * **iPhone:** Toggle **"Maximize Compatibility"** to **ON**.
   * **Android:** Set **AP Band** to **2.4 GHz**.
5. Keep the Personal Hotspot settings screen open until the Pi connects.

### 2. Laptop & Pi Connection
1. Connect your **Laptop's Wi-Fi** to `phoenix`.
2. Power on the Raspberry Pi (it will auto-associate with `phoenix`).
3. Your phone will show **2 Connected Devices** (Laptop + Pi).
4. SSH from your laptop:
   ```powershell
   ssh ambers@ambers-desktop.local
   ```

---

## 🔌 Method 3: Direct Ethernet LAN Cable (Emergency Bench Setup)

The fail-safe wired connection for flashing, heavy package compilation, or when all radio frequencies are jammed.

### 1. Setup
1. Plug an Ethernet cable directly between your laptop and the Raspberry Pi.
2. In Windows (`ncpa.cpl`):
   * Right-click **Wi-Fi** $\rightarrow$ **Properties** $\rightarrow$ **Sharing**.
   * Check **"Allow other network users to connect..."** and select **Ethernet**.
   * Click **OK**.
3. Wait 30 seconds for the Pi to receive an IP.

### 2. Connect
```powershell
ssh ambers@192.168.137.42
```

---

## 🛠️ Network Management on the Raspberry Pi (`nmcli`)

The Raspberry Pi has NetworkManager installed. You can inspect or modify saved profiles anytime via SSH:

### View All Saved Wi-Fi Networks
```bash
nmcli connection show
```
*(You should see `phoenix`, `Phoenix_Laptop`, and any wired connections).*

### Scan for Visible Wi-Fi Networks
```bash
sudo nmcli dev wifi rescan
sudo nmcli dev wifi list
```

### Add a New Wi-Fi Network (e.g. Home Router)
```bash
sudo nmcli dev wifi connect "<WIFI_SSID>" password "<WIFI_PASSWORD>"
```

### Check Active IP Addresses on the Pi
```bash
hostname -I
```

---

## ⚠️ Essential Troubleshooting Checklist

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| `Error: No network with SSID found` | Hotspot is broadcasting on 5 GHz or hidden | Switch hotspot to **2.4 GHz** (or toggle "Maximize Compatibility" on iPhone). Run `sudo rfkill unblock wifi`. |
| `IP configuration could not be reserved` | Windows DHCP locked to Ethernet port | In `ncpa.cpl`, uncheck Sharing on Wi-Fi. Turn Mobile Hotspot OFF and back ON. |
| `pigpiod.service failed (Result: signal)` | Stale PID lock file from sudden power loss | Run `sudo rm -f /var/run/pigpio.pid` then `sudo systemctl restart pigpiod`. |
| SSH disconnects when adding a new Wi-Fi | Single Wi-Fi chip (`wlan0`) switching APs | Expected. The Pi disconnects from old Wi-Fi to join new Wi-Fi. Re-SSH into the new IP. |
| `ros2 launch` hangs on exit | A node (e.g. LiDAR serial) ignoring SIGINT | Press **<kbd>Ctrl</kbd> + <kbd>\</kbd>** (`SIGQUIT`) to immediately force-quit back to bash prompt. |
| Terminal prompt is dark grey / no color | Windows OpenSSH terminal profile | Add to `~/.bashrc`: `export PS1="\[\e[1;38;5;46m\]\u@\h\[\e[0m\]:\[\e[1;38;5;39m\]\w\[\e[0m\]\$ "` |
