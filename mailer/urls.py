from django.urls import path
from .views import send_application_view

urlpatterns = [
    path('', send_application_view, name='send_application'),
]
