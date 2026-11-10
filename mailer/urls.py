from django.urls import path
from .views import send_application_view, recent_logs_partial, lead_harvester_view

urlpatterns = [
    path('', send_application_view, name='send_application'),
    path('leads/', lead_harvester_view, name='lead_harvester'),
    path('recent-logs/', recent_logs_partial, name='recent_logs_partial'),
]
