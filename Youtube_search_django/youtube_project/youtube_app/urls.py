from django.urls import path

from . import views

urlpatterns = [
    path('', views.search_view, name='search'),
    path('select/', views.select_video, name='select_video'),
]
