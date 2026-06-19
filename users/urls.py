from django.urls import path
from . import views

urlpatterns = [
    path('api/register/', views.UserRegisterView.as_view(), name='api-register'),
    path('api/login/', views.UserLoginView.as_view(), name='api-login'),
    path('api/logout/', views.UserLogoutView.as_view(), name='api-logout'),
    path('api/profile/', views.UserProfileView.as_view(), name='api-profile'),
    path('api/users/list/', views.UserListView.as_view(), name='api-users-list'),
    
    # Connections
    path('api/connections/', views.ConnectionListView.as_view(), name='api-connections'),
    path('api/connections/request/', views.ConnectionRequestView.as_view(), name='api-connection-request'),
    path('api/connections/respond/', views.ConnectionRespondView.as_view(), name='api-connection-respond'),
    path('api/connections/delete/<int:pk>/', views.ConnectionDeleteView.as_view(), name='api-connection-delete'),
    
    # Messaging
    path('api/messages/chats/', views.ChatListView.as_view(), name='api-chat-list'),
    path('api/messages/history/<int:other_user_id>/', views.MessageHistoryView.as_view(), name='api-message-history'),
    path('api/messages/send/', views.MessageSendView.as_view(), name='api-message-send'),
    
    # Notifications
    path('api/notifications/', views.NotificationListView.as_view(), name='api-notifications'),
    path('api/notifications/<int:pk>/', views.NotificationDetailView.as_view(), name='api-notification-detail'),
]

