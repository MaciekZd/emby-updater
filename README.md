# Emby Updater

A QNAP QPKG application that updates [Emby Server](https://emby.media/) (stable & beta) with one click.  
Features a web UI with scheduler, login, and Polish/English language support.  
**No Python or external dependencies required** — pure shell implementation.

<img width="1625" height="1348" alt="image" src="https://github.com/user-attachments/assets/a635ed7c-e966-41b4-bb36-9c1d8463f407" />

<img width="1587" height="1221" alt="image" src="https://github.com/user-attachments/assets/8ab16fbd-af2c-4fe3-ac32-6948683000db" />

---

## Features

- 🔄 One-click update to latest **stable** or **beta** Emby Server release
- 📅 **Scheduler** — set automatic update checks (daily/weekly)
- 🔐 **Authentication** — login with configurable credentials (default: `admin` / `admin`)
- 🌐 **PL/EN** — Polish and English interface
- 🔁 **Self-update** — detects new EmbyUpdater versions on GitHub and installs with one click
- 💾 **Settings persistence** — configuration is preserved across QPKG upgrades
- 📦 Installs as a native QNAP App Center package

---

## Requirements

| Requirement | Details |
|-------------|---------|
| NAS architecture | **x86_64 only** |
| QTS version | 4.3.0 or later |
| Port | 9876 (must be free) |
| Internet | Required for update checks and downloads |
| Emby Server | Should be installed before using the updater |

> No QBase24, Python, or other packages needed — the app uses a bundled static busybox binary.

---

## Installation

1. Download the latest `.qpkg` from [Releases](../../releases)
2. In QNAP App Center: click the **gear icon ⚙** → **Install Manually**
3. Select the downloaded `.qpkg` file
4. After installation, open the app at `http://YOUR_NAS_IP:9876/`
5. Default credentials: **admin / admin** — change them in the Settings tab

---

## Self-update

When a new version is released on GitHub, a banner appears at the top of the UI with a one-click **Update** button. The QPKG is downloaded and installed in the background — no token or additional configuration needed.

---

## Password reset (SSH)

If you forget your password, run via SSH:

```sh
touch /share/CACHEDEV1_DATA/.qpkg/EmbyUpdater/reset_credentials
/share/CACHEDEV1_DATA/.qpkg/EmbyUpdater/EmbyUpdater.sh restart
```

Credentials will be reset to the default: `admin` / `admin`.

---

## Project Structure

```
emby-updater/
├── shared/www/
│   ├── index.html             # Main web UI (Versions, Schedule, Settings tabs)
│   ├── login.html             # Login page
│   ├── .busyboxrc             # busybox httpd config
│   └── cgi-bin/
│       └── api.cgi            # Shell CGI API handler
├── bin/
│   └── busybox                # Bundled static busybox binary (x86_64)
├── icons/
│   ├── EmbyUpdater.gif        # 64px App Center icon
│   ├── EmbyUpdater_80.gif     # 80px App Center icon
│   └── EmbyUpdater_gray.gif   # 64px grayscale icon
├── qpkg.cfg                   # QPKG metadata
├── package_routines           # Install/uninstall hooks
├── qinstall.sh                # QPKG installer script
├── build-qpkg.sh              # Build script (run on QNAP)
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

All source code is plain shell — no compiled binaries (other than the bundled busybox for the web server).  
You can inspect every file before installing.

The default password is `admin` — **change it immediately** after first login via the Settings tab.

---

## Disclaimer
This software is provided as-is, without any warranty of any kind.

Use at your own risk. The author takes no responsibility for any data loss, system instability, or damage caused by using this software.
Always back up your Emby Server data before performing an update.
This project is not affiliated with or endorsed by Emby LLC.
Tested on QNAP QTS with x86_64 architecture only - behavior on other configurations may vary.

---

## License

GPL
