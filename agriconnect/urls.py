from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    path('', include('core.urls')),
    path('', include('users.urls')),
    path('', include('produce.urls')),
    path('', include('orders.urls')),
    path('', include('logistics.urls')),
    path('', include('ai.urls')),
    path('', include('payments.urls')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
