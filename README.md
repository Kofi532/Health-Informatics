# GlucoBridge

A Django web application for health informatics, including patient profiles, medical encounters, vital signs, and appointment tracking.

## Setup

1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run migrations:
   ```bash
   python manage.py migrate
   ```
4. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```
5. Start the development server:
   ```bash
   python manage.py runserver
   ```

## Features

- Patient profiles
- Medical records and vital signs
- Appointments
- Admin site registration

## Next steps

- Add user authentication and role-based access
- Connect to a production-ready database
- Implement APIs with Django REST Framework
- Add charting and analytics for patient data
