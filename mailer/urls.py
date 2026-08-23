from django.urls import path
from .views import send_application_view, recent_logs_partial

urlpatterns = [
    path('', send_application_view, name='send_application'),
    path('recent-logs/', recent_logs_partial, name='recent_logs_partial'),
]
