from django.urls import path
from .views import (
    send_application_view, 
    recent_logs_partial, 
    lead_harvester_view, 
    followup_action_view,
    generate_ai_hook_view,
    track_open_view,
    track_click_view,
    kanban_tracker_view,
    update_application_stage,
    update_application_details,
    create_application_view
)

urlpatterns = [
    path('', send_application_view, name='send_application'),
    path('leads/', lead_harvester_view, name='lead_harvester'),
    path('tracker/', kanban_tracker_view, name='kanban_tracker'),
    path('recent-logs/', recent_logs_partial, name='recent_logs_partial'),
    path('followups/action/', followup_action_view, name='followup_action'),
    path('api/generate-hook/', generate_ai_hook_view, name='generate_ai_hook'),
    path('api/applications/create/', create_application_view, name='create_application'),
    path('api/applications/<int:app_id>/update-stage/', update_application_stage, name='update_application_stage'),
    path('api/applications/<int:app_id>/update-details/', update_application_details, name='update_application_details'),
    path('track/open/<uuid:token>/', track_open_view, name='track_open'),
    path('track/click/<uuid:token>/', track_click_view, name='track_click'),
]
