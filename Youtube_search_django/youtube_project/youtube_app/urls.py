from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import EmailAuthenticationForm


app_name = 'youtube_app'

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
    # 送信先メールアドレス入力画面
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='youtube_app/password_reset.html',
        email_template_name='youtube_app/password_reset_email.html',
        subject_template_name="youtube_app/password_reset_subject.txt",
        success_url='/password_reset/done/'
    ), name='password_reset'),
    # メール送信完了画面
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='youtube_app/password_reset_done.html'
    ), name='password_reset_done'),

    # リセット用リンククリック後のパスワード入力画面
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='youtube_app/password_reset_confirm.html',
        success_url='/reset/done/'
    ), name='password_reset_confirm'),

    # パスワード変更完了画面
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='youtube_app/password_reset_complete.html'
    ), name='password_reset_complete'),
]

