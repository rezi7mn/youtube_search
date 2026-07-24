from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import EmailAuthenticationForm

urlpatterns = [
    path('', views.search_view, name='search'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('select/', views.select_video, name='select_video'),
    path('history/', views.history_view, name='history'),
    path('recommendations/', views.recommendations_view, name='recommendations'),
    path('login/google/', views.google_login, name='google_login'),
    path('login/google/callback/', views.google_callback, name='google_callback'),
]

