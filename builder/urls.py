from rest_framework.routers import DefaultRouter
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import *

router = DefaultRouter()
router.register(r'chatbots', ChatbotViewSet, basename='chatbot')
router.register(r'nodes', NodeViewSet, basename='node')
router.register(r'connections', ConnectionViewSet, basename='connection')
router.register(r'uploaded-files', UploadedFileViewSet, basename='uploadedfile')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/register/', RegisterView.as_view(), name='auth_register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='auth_login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]


