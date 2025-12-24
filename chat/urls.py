from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_page, name='chat_page'),
    path("start_session/<int:assignment_id>/", views.start_session, name="start_session"),
    path('student_response/<int:session_id>/', views.student_response, name='student_response'),
    path('advance_phase/<int:session_id>/', views.advance_phase, name='advance_phase'),]
