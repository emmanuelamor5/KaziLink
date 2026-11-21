# KaziLink

KaziLink is a Django semester project for people in Kenya who need a local job done and freelancers who have the skills and availability to do it. This milestone demonstrates Django forms, SQLite models, session authentication, and role-based access.

## Run locally on Windows

From the project directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Open [the landing page](http://127.0.0.1:8000/).

## Classroom demo

1. Register as a freelancer. Enter a neighbourhood, skills, availability, and an identification type. Use a fictional document number such as `DEMO12345`. The dashboard displays the type only. The database stores a salted hash of the number.
2. Log out, then log in through the freelancer form with the same username and password.
3. Generate a one-time hirer requirement ID in a second terminal.

   ```powershell
   .\.venv\Scripts\python.exe manage.py issue_hirer_id
   ```

4. Register as a hirer using the printed ID. Each ID works for one successful signup. Log out and use the hirer login form to show that the account persists.
5. Select **Post a job** and save a listing with a title, description, neighbourhood, duration, pay in KES and expectations. The hirer’s dashboard displays their saved posts.

The hirer code is an administrator-issued invitation for this prototype. Document checks cover freelancer input format only. Use fictional personal information for the demo. Distance-based matching and freelancer job browsing are future milestones.

## Checks

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test
```
