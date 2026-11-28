# KaziLink

KaziLink is a Django project that connects hirers with local freelancers in Kenya. Hirers can post jobs, review applicants, and send interview invitations. Freelancers can browse listings, apply with a PDF résumé, and respond to invitations from their dashboard.

## Run locally on Windows

The project has been tested with Python 3.12 and Django 5.2.19. It uses SQLite, Django templates, CSS, and browser JavaScript. Open PowerShell in the inner `KaziLink` folder that contains `manage.py` and `requirements.txt`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Open [KaziLink on localhost](http://127.0.0.1:8000/). If you already have a virtual environment, start with the dependency installation command. Run `migrate` after pulling model changes.

## Demo

1. Register as a freelancer in four steps. Enter contact details, work profile, identification, and login details. Use a fictional document number such as `DEMO12345`. The dashboard displays the document type. The database stores a salted hash of the number.
2. Log out, then log in through the freelancer form with the same username and password.
3. Generate a one-time hirer requirement ID in a second terminal.

   ```powershell
   .\.venv\Scripts\python.exe manage.py issue_hirer_id
   ```

4. Register as a hirer in three steps. Enter the printed ID on **Hirer details**. Each ID works for one successful signup. Log out and use the hirer login form to show that the account persists.
5. Give both demo accounts **Can view job** through their groups in Django Admin. As the hirer, select **Post a job** and enter the title, description, neighbourhood, duration, pay in KES, and expectations. The listing appears under **Job listings** on both dashboards.

The hirer code is an administrator-issued invitation for this prototype. Document checks cover freelancer input format only. Use fictional personal information for the demo. Distance-based matching is a future milestone.

Use **Previous step** to return to an earlier signup step with your entries intact. Use **Previous page** to return to the last KaziLink page or the starting page for the current workflow. The glass interface uses SF Pro where the device provides it and Segoe UI on Windows.

## Sessions and authentication

KaziLink stores sessions in the database. By default, login and signup use a browser-session cookie. Select **Keep me signed in** at login to stay signed in for up to 14 days on that device. **Log out** ends the current session in either mode.

Use **Change password** on the dashboard to update your password. Django keeps the current session signed in and rejects other sessions when they next try to access your account.

## Django Admin

Apply migrations and create a superuser from PowerShell, then start the app.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Enter your username, email address, and password at the prompts. Sign in at [KaziLink Administration](http://127.0.0.1:8000/admin/).

- **Users** lists registered accounts by role. A superuser can change a role under **KaziLink profile**. Complete **Freelancer setup** when assigning Freelancer to an account without a profile. Assigning Hirer in the admin is direct approval by the superuser. People who register themselves as hirers still need a one-time code. Previous freelancer profiles and job posts are retained after a role change.
- **Jobs** lets authorized staff add, view, update, and delete job posts. Search by title, hirer username, or location.
- **Hirer access codes** shows when codes were issued and redeemed. Create codes using `manage.py issue_hirer_id`. The admin excludes document hashes and code digests.
- **Groups** lets a superuser assign model permissions to staff. For example, create a **Job reviewers** group with **Can view job**, then assign it to an active user with **Staff status**. The user can view job records. Grant **Can change job** to also allow edits.

For a fresh database, create **Freelancers** and **Hirers** in **Groups** and grant each group **Can view job** for marketplace jobs. To assign users in bulk, select only **Freelancers** and run **Add all freelancers to selected group**. Repeat with **Hirers** and **Add all hirers to selected group**. Run the actions again to include new accounts. Dashboard permissions work for regular accounts.

## Hiring workflow

1. Open a job from **Job listings**. The details show the hirer, location, duration, pay, and expectations. Opening a listing records a signed-in viewer once for the posting hirer.
2. As a freelancer, select **Apply** and upload a PDF résumé up to 5 MB. The application shows under **Your applications**. The résumé download is accessible to the applicant and the posting hirer.
3. As the hirer, select the job under **Your postings** to review viewers and applicants. Select an applicant to see their profile and résumé, open an email to them, or use **Approve and notify** with optional interview details in Kenya time.
4. The freelancer responds from **Your applications**. Each job can have one active invitation or accepted candidate at a time. A decline lets the hirer invite someone else.
5. After the freelancer accepts, **Delete listing** removes the job from the shared board and preserves its private hiring history.

## Checks

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test
```
