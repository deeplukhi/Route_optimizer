from django.urls import path

from route_optimizer import views

urlpatterns = [
    path("health/", views.health_check, name="health_check"),
    path("optimize-route/", views.optimize_route, name="optimize_route"),
]
