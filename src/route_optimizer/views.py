from django.http import JsonResponse
from rest_framework.decorators import api_view


@api_view(["GET"])
def health_check(request):
    return JsonResponse({"status": "ok"})
