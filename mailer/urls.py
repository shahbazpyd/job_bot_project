from django.urls import path
from .views import send_application_view, recent_logs_partial, lead_harvester_view, followup_action_view

urlpatterns = [
    path('', send_application_view, name='send_application'),
    path('leads/', lead_harvester_view, name='lead_harvester'),
    path('recent-logs/', recent_logs_partial, name='recent_logs_partial'),
    path('followups/action/', followup_action_view, name='followup_action'),
]
