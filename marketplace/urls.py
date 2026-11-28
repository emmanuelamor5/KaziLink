from django.contrib.auth.views import LogoutView
from django.urls import path

from . import job_views, views
from .models import User

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.roles, {"action": "signup"}, name="signup"),
    path("signup/freelancer/", views.signup, {"role": User.Role.FREELANCER}, name="signup_freelancer"),
    path("signup/hirer/", views.signup, {"role": User.Role.HIRER}, name="signup_hirer"),
    path("login/", views.roles, {"action": "login"}, name="login"),
    path("login/freelancer/", views.AccountLoginView.as_view(role=User.Role.FREELANCER), name="login_freelancer"),
    path("login/hirer/", views.AccountLoginView.as_view(role=User.Role.HIRER), name="login_hirer"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("account/password/", views.AccountPasswordChangeView.as_view(), name="password_change"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("jobs/new/", views.create_job, name="create_job"),
    path("jobs/<int:pk>/", job_views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/apply/", job_views.apply_for_job, name="apply_for_job"),
    path("jobs/<int:pk>/review/", job_views.job_review, name="job_review"),
    path("jobs/<int:pk>/delete/", job_views.delete_listing, name="delete_listing"),
    path("applications/<int:pk>/", job_views.application_status, name="application_status"),
    path("applications/<int:pk>/candidate/", job_views.candidate_detail, name="candidate_detail"),
    path("applications/<int:pk>/resume/", job_views.download_resume, name="download_resume"),
    path("applications/<int:pk>/respond/", job_views.respond_to_invitation, name="respond_to_invitation"),
]
