from django.urls import path
from . import views

urlpatterns = [
    path('webhook/', views.wechat_webhook_view, name='wechat_webhook'),
]
