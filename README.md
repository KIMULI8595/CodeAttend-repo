# CodeAttend

CodeAttend is a Django attendance management system for internship programmes. Interns register through a public portal, remain locked while approval is pending, and gain access only after an authorised administrator approves them.

## Core workflow

1. An intern registers at `/interns/register/`.
2. The new account is created with `PENDING` status and cannot authenticate.
3. An administrator signs in at `/accounts/admin/login/`.
4. The administrator reviews registrations at `/interns/pending/` and approves or rejects each intern.
5. Approval activates the account and creates the intern's QR identifier.
6. The intern signs in at `/accounts/intern/login/` and is sent to `/attendance/intern/dashboard/`.
7. Staff use the administration dashboard at `/attendance/dashboard/`.
8. Logout is available in every authenticated dashboard and returns each role to its own login page.

## Features

- Separate intern and administration login interfaces
- Intern registration with duplicate checks and Django password validation
- Administrator approval and rejection workflow
- Pending, active, rejected, suspended, and deactivated account states
- Role-aware dashboards and navigation
- Password visibility toggles on login and registration forms
- Secure POST-only logout
- GPS/geofenced check-in and check-out with accuracy validation
- QR-code attendance scanning
- Batch and session assignment
- Manual attendance management and audit history
- Attendance analytics and CSV, Excel, and PDF exports
- In-app notifications
- Responsive templates
- Automated authentication, GPS, geofence, QR, and attendance tests
- Environment-based production security settings

## Installation

Create and activate a Python virtual environment, then run:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The custom superuser manager automatically creates new administrators with an `ACTIVE` account status. Migration `accounts.0005_activate_staff_accounts` also activates staff accounts created by older project versions.

## Initial configuration

After creating the superuser:

1. Open `/admin/` and create at least one Batch.
2. Create at least one Session.
3. Create an Attendance Location with its latitude, longitude, radius, and acceptable GPS accuracy.
4. Review pending interns from `/interns/pending/`.
5. Assign approved interns to a batch and session through Django admin.

## Access points

- Portal selector: `/`
- Intern registration: `/interns/register/`
- Intern login: `/accounts/intern/login/`
- Administration login: `/accounts/admin/login/`
- Intern dashboard: `/attendance/intern/dashboard/`
- Staff dashboard: `/attendance/dashboard/`
- Pending approvals: `/interns/pending/`
- GPS attendance: `/attendance/gps/`
- QR scanner: `/attendance/scanner/`
- Django admin: `/admin/`

## Validation

Run the full project validation suite:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

The supplied project was validated with all 76 tests passing.

## Production

Copy `.env.example` to `.env` and provide values through your deployment environment. Never use the development secret key in production. Set `DJANGO_DEBUG=False`, configure allowed hosts and trusted origins, use HTTPS, configure a production email backend, and use a managed database such as PostgreSQL.


-0.6072071935591176, 30.662120252271297