# EdgeStream API

**EdgeStream API** is a FastAPI backend service for the EdgeStream Hub appliance:  
a secure, extensible collector for logs, metrics, events, and network data.  
It manages sources, filters, destinations, certificates, VPN configs, and advanced system settings —  
with a JSON/REST API and YAML export pipeline managed by Ansible.

---

## ✨ Features

- **FastAPI service** with Gunicorn/Uvicorn workers.
- **SQLite (default) or SQLAlchemy-compatible RDBMS** backend.
- **CRUD APIs** for:
  - Sources & source parameters  
  - Filters  
  - Destinations, routes, parameters  
  - Certificates & VPN configs  
  - Networks (DNS, NTP, static routes/hosts, IP management)  
  - System & advanced settings  
  - Jobs & backups
- **Export pipeline** → generates consolidated YAML configs for Ansible.
- **Background task scheduler** with `fastapi.BackgroundTasks`.
- **Secure systemd service unit** with hardened defaults.
- **Database migrations** managed by Alembic.
- **Pluggable secrets/init** via `/opt/edgestream-api/bin/database_init.bin`.

---

## 📦 Project Layout

```
/opt/edgestream-api/
├── bin/                  # venv entrypoints + init scripts
│   ├── gunicorn
│   ├── uvicorn
│   ├── database_init.bin
│   └── ...
├── lib/python3.11/site-packages/app/
│   ├── core/
│   │   ├── crud/         # CRUD services
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   └── utils/        # helpers (security, deps, constants, etc.)
│   ├── main.py           # FastAPI entrypoint
│   └── ...
└── alembic/              # Alembic migration environment (optional)
```

---

## 🚀 Getting Started

### Requirements
- Python 3.11+
- FastAPI, SQLAlchemy, Alembic, Ansible Runner
- SQLite (default) or another supported DB engine

### Install
Clone the repo and install requirements into a venv:

```bash
git clone https://github.com/youruser/edgestream-api.git
cd edgestream-api
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### Database Initialization
On first boot, the included init script will:
- Create necessary state/secrets in `/etc/edgestream/`.
- Initialize the SQLite DB (or run Alembic migrations).

Manually run:
```bash
export SQLALCHEMY_DATABASE_URI=sqlite:////var/lib/edgestream/edgestream.db
/opt/edgestream-api/bin/database_init.bin
```

### Running the API
With Gunicorn (production):

```bash
gunicorn edgestream.main:edgestream   --workers 4   --worker-class uvicorn.workers.UvicornWorker   --bind 127.0.0.1:3001
```

Or with Uvicorn (development):

```bash
uvicorn edgestream.main:edgestream --reload --host 0.0.0.0 --port 3001
```

---

## ⚙️ Database Migrations

Edgestream API uses **Alembic** for schema evolution.

1. Initialize Alembic (already present if you cloned repo):
   ```bash
   alembic init alembic
   ```

2. Create a new migration when models change:
   ```bash
   alembic revision --autogenerate -m "describe change"
   ```

3. Apply migrations:
   ```bash
   alembic upgrade head
   ```

> SQLite is supported, but remember: foreign keys require `PRAGMA foreign_keys=ON`.

---

## 🛠 Systemd Service

A systemd unit is provided (`/etc/systemd/system/edgestream-api.service`)

Enable & start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable edgestream-api
sudo systemctl start edgestream-api
```

Logs go to `journalctl -u edgestream-api` and `/var/log/edgestream-api/`.

---

## 📤 Export & Ansible Integration

The API can export all managed settings (sources, transforms, certs, etc.) to  
YAML under `/var/lib/edgestream/export/`, then trigger an Ansible playbook:

- Export config only:
  ```bash
  curl -X POST http://localhost:3001/api/v1/export
  ```

- Export + run Ansible:
  ```bash
  curl -X POST http://localhost:3001/api/v1/export?run_playbook=true
  ```

Background tasks are tracked in the **tasks** table with states:
`pending → running → completed/failed`.

---

## 🔐 Security Notes

- Passwords are hashed with bcrypt (`passlib`).
- JWT signing secret + CLI/OTP tokens are auto-generated in
  `/etc/edgestream/edgestream-api.secrets`.
- Certificates and VPN configs are stored both in DB and on disk with correct ownership/permissions.

---

## 🤝 Contributing

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/foo`)
3. Commit changes (`git commit -am 'Add foo'`)
4. Push branch (`git push origin feature/foo`)
5. Open a Pull Request

---

## 📄 License

EdgeStream WebUI is licensed under the **Functional Source License 1.1,
ALv2 Future License (FSL-1.1-ALv2)**.

See:

- `LICENSE` for full terms  
- `COMMERCIAL.md` for commercial licensing requirements  