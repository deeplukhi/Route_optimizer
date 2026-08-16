from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from route_optimizer.exceptions import RouteImpossibleError
from route_optimizer.fuel_data import FUEL_PRICES
from route_optimizer.serializers import RouteOptimizationRequestSerializer
from route_optimizer.services import optimization_service, routing_service


@api_view(["GET"])
def health_check(request):
    return JsonResponse({"status": "ok"})


@api_view(["POST"])
def optimize_route(request):
    serializer = RouteOptimizationRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    route = routing_service.build_route(data["start"], data["end"])

    try:
        stops, total_cost = optimization_service.optimize_route(
            FUEL_PRICES,
            route,
            data["starting_fuel_gallons"],
        )
    except RouteImpossibleError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "route": route,
            "fuel_stops": stops,
            "total_fuel_cost": optimization_service.format_currency(total_cost),
        }
    )
