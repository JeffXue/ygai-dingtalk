from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/tasks/', include('apps.todo.urls')),
    path('channel/wechat/', include('apps.channel.wechat.urls')),
]
