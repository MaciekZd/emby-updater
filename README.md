# Emby Updater

A QNAP QPKG application that updates [Emby Server](https://emby.media/) (stable & beta) with one click.  
Features a web UI with scheduler, login, and Polish/English language support.

<img width="1625" height="1348" alt="image" src="https://github.com/user-attachments/assets/a635ed7c-e966-41b4-bb36-9c1d8463f407" />

<img width="1587" height="1221" alt="image" src="https://github.com/user-attachments/assets/8ab16fbd-af2c-4fe3-ac32-6948683000db" />


![App Center Icon](icons/EmbyUpdater.gif)

---

## Features

- 🔄 One-click update to latest **stable** or **beta** Emby Server release
- 📅 **Scheduler** — set automatic update checks (daily/weekly/monthly)
- 🔐 **Authentication** — login with configurable credentials (default: `admin` / `admin`)
- 🌐 **PL/EN** — Polish and English interface
- 📦 Installs as a native QNAP App Center package

---

## Requirements

| Requirement | Details |
|-------------|---------|
| NAS architecture | **x86_64 only** |
| QTS version | 4.3.0 or later |
| [QBase24]([https://www.qnap.com/en/app_center/](https://www.myqnap.org/product/qbase24/)) | Must be installed (provides Python 3) |
| Port | 9876 (must be free) |
| Internet | Required for update checks and downloads |
| Emby Server | Should be installed before using the updater |

---

## Installation

1. Download the latest `.qpkg` from [Releases](../../releases)
2. In QNAP App Center: click the **gear icon ⚙** → **Install Manually**
3. Select the downloaded `.qpkg` file
4. After installation, open the app at `http://YOUR_NAS_IP:9876/`
5. Default credentials: **admin / admin** — change them in the Settings tab

---

## Project Structure

```
emby-updater/
├── shared/
│   ├── server.py          # Python 3 HTTP server with auth & API
│   ├── EmbyUpdater.sh     # QPKG start/stop script
│   ├── emby-updater.sh    # Core update logic (download, install, version check)
│   ├── index.html         # Main web UI (Versions, Schedule, Settings tabs)
│   ├── login.html         # Login page
│   ├── fix_icons.py       # Generates App Center GIF icons
│   └── cgi-bin/
│       └── update         # CGI endpoint for update progress
├── icons/
│   ├── EmbyUpdater.gif        # 64px App Center icon
│   ├── EmbyUpdater_80.gif     # 80px App Center icon
│   └── EmbyUpdater_gray.gif   # 64px grayscale icon
├── qpkg.cfg               # QPKG metadata
├── package_routines       # Install/uninstall hooks
├── build-qpkg.sh          # Build script (run on QNAP)
└── README.md
```

---

## Building from Source

The QPKG must be built **on a QNAP device** because the `qpkg --encrypt` signing tool is only available on QTS.

```sh
# Copy source files to QNAP
scp -r . admin@YOUR_NAS_IP:/share/homes/admin/EmbyUpdater/

# SSH into QNAP and build
ssh admin@YOUR_NAS_IP
cd /share/homes/admin/EmbyUpdater
sh build-qpkg.sh
```

The signed `.qpkg` will be created in the `build/` directory.

---

## Security

All source code is plain shell scripts and Python — no compiled binaries.  
You can inspect every file before installing.

The default password is `admin` — **change it immediately** after first login via the Settings tab.

---

## License

GPL
