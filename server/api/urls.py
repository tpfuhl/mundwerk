from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ItemViewSet, ProfileView, RecordingViewSet, RegisterView

router = DefaultRouter()
router.register("items", ItemViewSet, basename="item")
router.register("recordings", RecordingViewSet, basename="recording")

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("profile/", ProfileView.as_view()),
    *router.urls,
]
