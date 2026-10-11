# 📝 Mail Shield — Assumptions & Implementation Notes

This document logs implementation assumptions made during development to adhere strictly to the Blueprint specifications without ambiguity.

1. **Deterministic Rule Engine Purity**:
   - The rule engine (`app/engine/`) is implemented in pure Python with zero database, network, or Flask dependencies.
   - Domain splitting utilizes `tldextract` with standard regex fallback for offline execution consistency.
   - Long phrase keywords in `app/engine/rules/keywords.py` take precedence over sub-strings within matched character spans to prevent duplicate counting in the same category.

2. **Multi-Mailbox Provider Adapters**:
   - The application includes both the production-ready adapter interfaces (`app/mail/providers/base.py`) and a mock fixture provider (`app/mail/providers/mock.py`) loaded with realistic phishing, suspicious, and clean newsletters across Gmail, Outlook, Yahoo, and iCloud.
   - This enables full end-to-end multi-mailbox testing, batch scanning, live UI stream simulation, and demonstration without requiring immediate active developer console approval.

3. **Storage & Cryptography**:
   - Mailbox credentials and app passwords are encrypted using AES-128-CBC / HMAC (Fernet) with keys stored strictly outside the database via environment variables.
   - Passwords use Argon2id with memory cost and time cost tuned for production security.
   - All email content is stored with ownership indexing (`user_id`) to strictly enforce multi-tenant isolation.
