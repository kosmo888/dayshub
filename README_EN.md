# 📅 DaysHub · Lunar & Solar Countdown & Anniversary Hub v2.0.0

**English** | [简体中文](README.md)

[![Release](https://img.shields.io/badge/release-v2.0.0-6366f1.svg?style=flat-square)](https://github.com/kosmo888/dayshub)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg?style=flat-square)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ed.svg?style=flat-square)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-37%2F37%20passing-success.svg?style=flat-square)](tests/)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)

> **Dual-track Lunar & Solar Countdown / Anniversary / Days Matter Central Hub**  
> Tailored for self-hosted lovers and smart homes. Featuring exact Chinese Lunar leap month handling, minimalist iOS/Android widget endpoint, Home Assistant smart dashboard integration, physical multi-user isolation, dual-channel audit logs, and production-grade multithreaded Waitress WSGI.

---

## ✨ Features & Ecosystem

| Module | Description |
| :--- | :--- |
| **🌙 Dual Lunar Engine** | True dual-track support for Chinese Lunar & Solar calendars. Precise Lunar Leap month (`is_leap`) bidirectional conversions & UI tags. Smooth tolerance for 30-day small lunar months, 24 Solar Terms, and Zodiac signs. |
| **📱 Minimalist Widget** | Dedicated `/api/widget/summary` lightweight JSON endpoint. Comes with open-source **iOS Scriptable native widget script** (Small & Medium formats, Light/Dark mode auto-adaptive) and Widgy guides. |
| **🏠 Home Assistant Hub** | Integrated IoT ecosystem. Ready-to-use RESTful sensor declarations and Lovelace dashboard card YAMLs for wall tablets, smart screens, or e-ink displays. |
| **📋 Dual-Channel Logs** | **Channel A**: Full-audit business operation logs stored in database (login, logout, registration, event mutations, settings updates, backups).<br>**Channel B**: Server runtime rolling logs (`dayshub.log`, auto 5MB rotation, direct web UI inspection). |
| **🔒 Security & Auth** | Multi-user isolation, visitor self-registration toggle, PBKDF2-SHA256 password hashing, brute-force IP rate-limiting (5 failures = 10 min lock), password-independent iCal tokens. |
| **🏮 Holiday Presets** | Built-in importable presets for traditional Chinese festivals and 24 Solar Terms. |
| **⚙️ Micro-Architecture** | Fully refactored with **Flask Blueprint modular architecture** (`auth`, `events`, `widget`, `admin`, `system`). Driven by production-grade multithreaded Waitress WSGI. |

---

## 🚀 Quick Start (Docker)

```bash
# 1. Clone repository
git clone https://github.com/kosmo888/dayshub.git
cd dayshub

# 2. Configure environment
cat > .env << 'EOF'
DAYSHUB_SECRET_KEY=dayshub-prod-secret-2026
DAYSHUB_API_TOKEN=your-admin-password
DAYSHUB_TZ=Asia/Shanghai
DAYSHUB_PORT=5217
EOF

# 3. Launch with Docker Compose
docker compose up -d

# 4. Access Web UI
# http://<YOUR_IP>:5217/
# Default initial admin username: admin, password: DAYSHUB_API_TOKEN
```

---

## 📱 Desktop Widget & Home Assistant

Explore the [`examples/`](examples/) directory for instant configuration:

* **iOS Scriptable Widget**: [`examples/widgets/dayshub_scriptable.js`](examples/widgets/dayshub_scriptable.js)
* **Home Assistant Sensors & Cards**: [`examples/homeassistant/`](examples/homeassistant/)
* **Holiday Presets**: [`examples/presets/`](examples/presets/)

---

## 🔌 Core API Endpoints

| Blueprint | Method | Path | Auth | Description |
| :--- | :---: | :---| :---: | :---|
| **Auth** | `POST` | `/api/login` | Public | Login and obtain token |
| **Auth** | `POST` | `/api/register` | Public (Configurable) | Self-register account |
| **Widget** | `GET` | `/api/widget/summary` | Token | **Dedicated minimalist widget JSON feed** |
| **Widget** | `GET` | `/api/dashboard` | User | Full dashboard aggregated dataset |
| **Events** | `GET` | `/api/events` | User | List user events (strictly isolated) |
| **Events** | `POST` | `/api/events` | User | Create countdown / anniversary event |
| **Admin** | `GET` | `/api/admin/logs` | Admin | Multi-dimensional audit logs |
| **Admin** | `GET` | `/api/admin/runtime_logs`| Admin | Real-time backend rolling logs |
| **System** | `GET` | `/api/calendar.ics` | Token | RFC-5545 compliant iCal feed |

---

## 📄 License

Open-sourced under the [MIT License](LICENSE).
