from django.urls import path

from . import dev_views

urlpatterns = [
    path("", dev_views.console, name="dev-console"),
    path("<int:pk>/", dev_views.result, name="dev-result"),
]
