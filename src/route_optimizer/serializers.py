from rest_framework import serializers


class RouteOptimizationRequestSerializer(serializers.Serializer):
    start = serializers.CharField(max_length=255)
    end = serializers.CharField(max_length=255)
    starting_fuel_gallons = serializers.FloatField(
        min_value=0.1, required=False, default=50.0
    )
