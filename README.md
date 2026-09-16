# 🐾 Desktop Pets — Animated Windows Companions & Reminder Assistants

Interactive pixel-art desktop pets for Windows that waddle along your taskbar across multiple monitors, perform playful animations, respond to physics, manage reminders, and expose a local REST API.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![Platform Windows](https://img.shields.io/badge/platform-Windows-0078D6.svg)
![License MIT](https://img.shields.io/badge/license-MIT-green.svg)

---

## 🌟 Available Pets

### 🐱 Patches the Calico Cat (`cat.py`)
A lively, cheerful calico cat ported faithfully from procedural pixel-art and packed with silly cat animations:
- **Walk Cycle**: 4-step gait with body bobs and tail sway.
- **Cheery Face**: Classic `:3` cat smile and curious green eyes (no sad face!).
- **🎯 Butt Wiggle & Pounce**: Crouches low, locks onto a target, wiggles its butt and tail, then leaps forward!
- **🧘 Big Morning Stretch**: Downward-dog stretch with paws flat and tail straight up.
- **🧼 Wash Face & Groom**: Sits, licks front paw, and washes behind ears with happy closed eyes (`^ ^`).
- **🪰 Paw Swat (*Bap Bap Bap!*)**: Playfully bats at imaginary bugs on your taskbar.
- **💖 Happy Purr**: Curls up into loaf or sitting pose with floating hearts.

### 🐧 The Emperor Penguin (`penguin_original.py`)
A dignified emperor penguin:
- Columnar posture with golden neck/chest wash and flush flippers.
- Taskbar waddle gait with rhythmic bobs.
- Calm, lifelike glances and soft blinks.
- Excited flipper flutter when reminders are due.

---

## 🚀 Getting Started

### Prerequisites
- Windows 10 / 11
- Python 3.10+
- `Pillow` library:
  ```bash
  pip install Pillow
  ```

### Launching

- **Double-click** `start_cat.bat` to launch Patches the Cat silently in the background (no black terminal window!).
- **Double-click** `start_penguin.bat` to launch the Emperor Penguin.
- Or run via terminal:
  ```powershell
  python cat.py
  # or
  python penguin_original.py
  ```

---

## 🎮 Desktop Mouse Interactions

| Action | Behavior |
| :--- | :--- |
| **Left Click** | Opens the pet speech bubble with upcoming reminder info, `+ Add`, `📋 View`, `Walk / Stay`, and `🐾 Silly` trick button. |
| **Left Click & Drag** | Pick up and carry your pet anywhere across your dual monitors. Releasing in mid-air drops it back to the taskbar with gravity physics! |
| **Right Click** | Context menu with reminder management and instant animation triggers (Big Stretch, Butt Wiggle & Pounce, Wash Face, Paw Swat, Purr). |
| **Due Alerts** | When a reminder is due, the pet halts, plays a chime, and pops up an alert dialog with **Dismiss**, **1 Hour**, and **Tomorrow** snooze buttons. |

---

## 🌐 Local REST API (`http://127.0.0.1:8766`)

Both pets run a lightweight local HTTP REST API on port `8766`.

### 1. ➕ Add a Reminder (`POST /reminders`)
```powershell
# In minutes
curl.exe -X POST http://127.0.0.1:8766/reminders -H "Content-Type: application/json" -d '{\"text\": \"Coffee break\", \"in_minutes\": 20}'

# In hours
curl.exe -X POST http://127.0.0.1:8766/reminders -H "Content-Type: application/json" -d '{\"text\": \"Check metrics\", \"in_hours\": 2}'

# In days
curl.exe -X POST http://127.0.0.1:8766/reminders -H "Content-Type: application/json" -d '{\"text\": \"Team follow-up\", \"in_days\": 7}'

# Exact timestamp
curl.exe -X POST http://127.0.0.1:8766/reminders -H "Content-Type: application/json" -d '{\"text\": \"Quarterly review\", \"due\": \"2026-09-22T09:00:00\"}'
```

### 2. 📋 List & Manage Reminders
```powershell
# List all reminders
curl.exe -s http://127.0.0.1:8766/reminders

# Dismiss a reminder
curl.exe -X POST http://127.0.0.1:8766/reminders/1/dismiss

# Delete a reminder
curl.exe -X DELETE http://127.0.0.1:8766/reminders/1
```

### 3. 🎭 Trigger Silly Pet Actions (`POST /pet/action`)
```powershell
# Butt wiggle & pounce
curl.exe -X POST http://127.0.0.1:8766/pet/action -H "Content-Type: application/json" -d '{\"action\": \"wiggle\"}'

# Morning stretch
curl.exe -X POST http://127.0.0.1:8766/pet/action -H "Content-Type: application/json" -d '{\"action\": \"stretch\"}'

# Paw swat (Bap bap!)
curl.exe -X POST http://127.0.0.1:8766/pet/action -H "Content-Type: application/json" -d '{\"action\": \"swat\"}'

# Wash face / Groom
curl.exe -X POST http://127.0.0.1:8766/pet/action -H "Content-Type: application/json" -d '{\"action\": \"groom\"}'

# Happy purr
curl.exe -X POST http://127.0.0.1:8766/pet/action -H "Content-Type: application/json" -d '{\"action\": \"purr\"}'

# Random silly trick
curl.exe -X POST http://127.0.0.1:8766/pet/action -H "Content-Type: application/json" -d '{\"action\": \"silly\"}'
```

### 4. 💬 Speech & Status
```powershell
# Custom speech bubble on screen
curl.exe -X POST http://127.0.0.1:8766/pet/speak -H "Content-Type: application/json" -d '{\"text\": \"Hello from the terminal! 🐱\"}'

# Check pet coordinates, monitor, and state
curl.exe -s http://127.0.0.1:8766/pet/status

# Toggle walking / roaming
curl.exe -X POST http://127.0.0.1:8766/pet/roam -H "Content-Type: application/json" -d '{\"roam\": false}'
```

---

## 🧠 Architecture Highlights
- **Chroma-Key Transparency**: Uses Windows layered window chroma-keying (`TRANS_KEY = "#ff00ff"`) with hard pixel-art edges for razor-sharp rendering over any wallpaper without magenta or gray halos.
- **Interactive Desktop Attachment**: Windows services or detached subshells attach via `SetThreadDesktop(OpenDesktopW("Default", ...))` to ensure UI renders directly onto the user's interactive desktop (`WinSta0\Default`).
- **Multi-Monitor Roaming**: Detects all connected displays dynamically via `EnumDisplayMonitors` / `GetMonitorInfoW`, giving pets natural cross-screen trekking behavior across dual (or triple) monitor setups.
- **Pure In-Memory Sprite Caching**: Generates and scales pixel-art frames on startup in <30ms, yielding 0% idle CPU usage.

---

## 📄 License
MIT License. Free to use, modify, and distribute.
