from rest_framework.routers import DefaultRouter

from .views import ItemViewSet, RecordingViewSet

router = DefaultRouter()
router.register("items", ItemViewSet, basename="item")
router.register("recordings", RecordingViewSet, basename="recording")

urlpatterns = router.urls
