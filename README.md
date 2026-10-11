# 🛡️ Mail Shield — Rule-Based E-mail Threat Scanner

**Mail Shield** is a deterministic, explainable e-mail threat scanner with multi-mailbox live synchronization across **Gmail**, **Outlook**, **Yahoo**, and **iCloud**.

Unlike traditional AI/ML spam filters that operate as opaque black boxes, Mail Shield runs a pure, transparent rule engine—evaluating keywords, SPF/DKIM/DMARC authentication, URL properties, typography patterns, and attachment vectors—delivering an itemized risk score (0 to 100) and human-readable evidence for every decision.

---

## ✨ Features

- **Multi-Mailbox Live Inbox**: Connect up to 4 mail services (Gmail, Outlook, Yahoo Mail, iCloud) in separate tabs with real-time push updates.
- **Explainable Threat Scoring**: Every decision provides exact rule IDs (e.g. `R-SND-05`, `R-URL-02`), plain-English descriptions, matched evidence snippets, and point contributions.
- **Deterministic Rule Engine**: 6 core detection groups (`KW`, `SND`, `URL`, `CAP`, `PUN`, `ATT`, `CMB`, `CUS`, `LST`) with customizable point weights and group caps.
- **Multi-Scope Scanning**: Single message, ticked items, entire provider tab, or all connected mailboxes simultaneously in one batch.
- **Manual Scan Sandbox**: Paste and test arbitrary raw email text, URLs, and attachment filenames without saving to a mailbox.
- **5-Way Authentication**: Sign up and log in via ID + password, Google, Microsoft, Yahoo, or Apple (iCloud).
- **Customization & Themes**: Responsive design with light and dark modes, custom accent colors, table density controls, and live rule adjustments.
- **GDPR & Privacy First**: Strictly read-only mailbox scopes. Data export and one-click account wipe.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.11+ / Flask 3.x
- **Real-Time**: Flask-SocketIO (WebSocket & Polling fallbacks)
- **Database**: MongoDB 6.0+ / PyMongo (with mongomock for unit testing)
- **Authentication & Security**: Argon2id password hashing, Fernet token encryption, Authlib (OIDC/OAuth 2.0), Flask-Login, Flask-WTF (CSRF), Flask-Limiter
- **Frontend**: HTML5, Vanilla CSS Design System, Bootstrap 5.3, Bootstrap Icons, ES Modules

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
- Python 3.11+
- MongoDB instance (Local or free MongoDB Atlas cluster)

### 2. Setup Virtual Environment & Install Dependencies
```bash
# Clone or navigate to the repository
cd Mail_Shield

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Ensure `SECRET_KEY` and `FERNET_KEY` are configured.

### 4. Run the Application
```bash
python run.py
```
Open your browser and navigate to: **`http://localhost:5000`**

---

## 🧪 Running the Test Suite

Execute the complete pytest suite:
```bash
python -m pytest tests/ -v
```

---

## 🔒 Security & Privacy

- **Read-Only Scopes**: Mail Shield requests read-only permissions (`gmail.readonly`, `Mail.Read`, IMAP read). It never modifies, deletes, or sends emails from your provider.
- **Credential Protection**: Remote OAuth refresh tokens and app-specific passwords are encrypted at rest using AES-128-CBC / HMAC (Fernet).
- **Sandboxed Rendering**: HTML email rendering is sanitised and isolated in `<iframe sandbox>` with remote image blocking and script execution prevention.

---

## 📄 License
This project is open-source and intended for educational, research, and personal defense-in-depth email security applications.
