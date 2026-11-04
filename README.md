# Hope Care Community - Flask & MongoDB Admin Panel Application

A modular, secure, and production-ready Admin Panel application built with **Python**, **Flask**, and **MongoDB (PyMongo)** to manage community volunteer/partner registrations and confidential prayer requests.

The application follows the **Application Factory**, **Blueprints**, **Service Layer**, and **Repository (Data Access) Layer** architectural pattern, cleanly separating business logic and database access from presentation.

---

## Architecture Overview

```
Browser / Client (Public or Admin)
         ↓
Flask Routes / Controllers  (app/routes/)
         ↓
Service Layer               (app/services/)
         ↓
Repository Layer            (app/repositories/)
         ↓
MongoDB Engine              (PyMongo / MongoDB)
         ↓
Jinja2 Admin Templates      (app/templates/)
```

### Key Modules

1. **Authentication & RBAC (`app/routes/auth.py`, `app/auth/`)**:
   - Secure password hashing using Scrypt/PBKDF2 via Werkzeug.
   - Flask-Login session management with HttpOnly cookies.
   - Role-Based Access Control (`Super Admin`, `Admin`, `Staff`).
   - Self-privilege elevation safeguards and password reset workflow.

2. **Dashboard (`app/routes/dashboard.py`, `app/services/dashboard_service.py`)**:
   - Real-time MongoDB aggregation metrics for volunteer and partner registrations.
   - Prayer request status metrics (new, pending, in prayer, completed).
   - Recent activity feeds (respecting prayer request confidentiality).

3. **Registration Management (`app/routes/registrations.py`, `app/services/registration_service.py`)**:
   - Unified `registrations` collection handling both **Volunteer** and **Partner** types via `registration_type`.
   - Comprehensive filtering (type, status, date), search, sorting, and pagination.
   - Status transitions (`New` &rarr; `Contacted` &rarr; `Approved` &rarr; `Active` &rarr; `Rejected` &rarr; `Inactive`).
   - Internal administrative notes history.
   - Delete/purge capability restricted to Super Admins.

4. **Prayer Request Management (`app/routes/prayer_requests.py`, `app/services/prayer_request_service.py`)**:
   - Public submission supporting both identified and **Anonymous** petitions.
   - Strict privacy safeguards: full prayer text visible only to authorized admin staff.
   - Workflow management (`New` &rarr; `In Review` &rarr; `Praying` &rarr; `Completed` &rarr; `Archived`).
   - Pastoral care notes timeline.

5. **User Management (`app/routes/users.py`, `app/services/user_service.py`)**:
   - Administrative user listing, creation, role modification, direct password reset, and activation toggling.
   - Enforced restriction: non-super-admins cannot view or alter administrators.

6. **Reports & Analytics (`app/routes/reports.py`, `app/services/report_service.py`)**:
   - Timeframe presets (`All Time`, `Today`, `This Week`, `This Month`, `This Year`, and `Custom Range`).
   - Registration breakdown and category volume analytics.

7. **Audit Logging (`app/routes/audit.py`, `app/services/audit_service.py`)**:
   - Immutable security log of administrative actions, logins, status changes, and record deletions.

---

## Directory Structure

```text
hope/
├── app/
│   ├── __init__.py               # Application factory (create_app)
│   ├── config.py                 # Centralized configuration (dev, test, prod)
│   ├── extensions.py             # Flask extensions (LoginManager, user_loader)
│   ├── commands.py               # Custom CLI commands (init-db, create-superadmin)
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py         # PyMongo client pooling & lifecycle
│   │   └── indexes.py            # MongoDB index initialization
│   │
│   ├── models/
│   │   └── user.py               # User model with Flask-Login integration
│   │
│   ├── repositories/
│   │   ├── user_repository.py
│   │   ├── registration_repository.py
│   │   ├── prayer_request_repository.py
│   │   └── audit_repository.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── registration_service.py
│   │   ├── prayer_request_service.py
│   │   ├── dashboard_service.py
│   │   ├── report_service.py
│   │   └── audit_service.py
│   │
│   ├── auth/
│   │   ├── decorators.py         # @role_required, @super_admin_required
│   │   └── permissions.py        # RBAC permissions dictionary
│   │
│   ├── routes/
│   │   ├── public.py             # Public landing, /register, /prayer-request
│   │   ├── auth.py               # Admin login, logout, password recovery
│   │   ├── dashboard.py          # Admin metrics overview
│   │   ├── registrations.py      # Registration management
│   │   ├── prayer_requests.py    # Confidential prayer request management
│   │   ├── users.py              # Super Admin user management
│   │   ├── reports.py            # Analytics & date filtering
│   │   └── audit.py              # Audit trail log
│   │
│   ├── templates/
│   │   ├── base.html             # High-end responsive admin master layout
│   │   ├── public/               # Public frontend placeholders
│   │   ├── auth/                 # Sign in & password reset pages
│   │   ├── dashboard/            # Metrics overview
│   │   ├── registrations/        # List & detail views
│   │   ├── prayer_requests/      # List & confidential detail views
│   │   ├── users/                # User CRUD views
│   │   ├── reports/              # Analytics views
│   │   ├── audit/                # Audit trail views
│   │   └── errors/               # 403, 404, 500 error pages
│   │
│   └── static/
│       └── css/
│           └── admin.css         # Modern design system & styles
│
├── tests/
│   ├── conftest.py               # Pytest fixtures & isolated test db
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_factory.py
│   ├── test_auth.py
│   ├── test_users.py
│   ├── test_dashboard.py
│   ├── test_registrations.py
│   ├── test_prayer_requests.py
│   ├── test_reports.py
│   └── test_audit.py
│
├── .env                          # Local environment variables (gitignored)
├── .env.example                  # Environment template
├── .gitignore
├── requirements.txt
├── run.py                        # Application entry point
└── README.md
```

---

## Setup & Running Locally

### 1. Prerequisites

- Python 3.10+
- MongoDB 6+ running locally on `localhost:27017` (or MongoDB Atlas URI)

### 2. Environment Setup

```bash
# Activate existing virtual environment
source env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Verify Database Connectivity & Initialize Indexes

```bash
# Check connectivity and round-trip latency to the database
flask --app run.py check-db

# Ensure all MongoDB indexes are created
flask --app run.py init-db
```

### 4. Seed or Create a Super Admin User

```bash
flask --app run.py create-superadmin --email admin@hopecommunity.org --password AdminPassword123! --name "Hope Super Admin"
```

### 5. Start the Application

```bash
python run.py
```

The application will be running at `http://127.0.0.1:5000`:
- **Admin Portal**: `http://127.0.0.1:5000/admin/login`
- **Public Portal**: `http://127.0.0.1:5000/`
- **Public Registration**: `http://127.0.0.1:5000/register`
- **Public Prayer Request**: `http://127.0.0.1:5000/prayer-request`

---

## Default Seeded Admin Credentials

For development and evaluation:

- **Email**: `admin@hopecommunity.org`
- **Password**: `AdminPassword123!`
- **Role**: `Super Admin`

---

## Running the Automated Test Suite

The test suite runs against in-memory isolated `mongomock` storage, executing without touching live databases:

```bash
pytest tests/ -v
```

All 34 tests covering authentication, RBAC, registrations, prayer requests, aggregations, and audit logging will execute.

---

## Integrating Designer's Frontend Later

The public routes in `app/routes/public.py` accept both HTML form submissions (`application/x-www-form-urlencoded`) and JSON API requests (`application/json`):

1. **Static Assets**: Place the designer's CSS, images, and JS scripts into `app/static/css/`, `app/static/images/`, and `app/static/js/`.
2. **Templates**: Replace `app/templates/public/index.html`, `register.html`, and `prayer_request.html` with the designer's HTML files.
3. Form fields map directly to:
   - `/register`: `registration_type` (`volunteer` or `partner`), `name`, `email`, `phone`, `organization_name`, `address`, `city`, `skills`, `message`.
   - `/prayer-request`: `request_text`, `category`, `is_anonymous` (`true`/`false`), `name`, `email`, `phone`, `preferred_contact`.
