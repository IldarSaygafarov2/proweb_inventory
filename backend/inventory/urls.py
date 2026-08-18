from django.urls import path

from .views import InventoryView

urlpatterns = [
    path("api/inventory/", InventoryView.as_view()),
]
