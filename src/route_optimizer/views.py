from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from route_optimizer.serializers import RouteOptimizationRequestSerializer
from route_optimizer.services import routing_service


@api_view(["GET"])
def health_check(request):
    return JsonResponse({"status": "ok"})


@api_view(["POST"])
def optimize_route(request):
    serializer = RouteOptimizationRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    route = routing_service.build_route(
        serializer.validated_data["start"],
        serializer.validated_data["end"],
    )

    return Response(
        {
            "route": route,
            "fuel_stops": [],
            "total_fuel_cost": "$0.00",
        }
    )
