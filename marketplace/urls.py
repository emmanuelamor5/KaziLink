from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views
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
    path("dashboard/", views.dashboard, name="dashboard"),
    path("jobs/new/", views.create_job, name="create_job"),
]
