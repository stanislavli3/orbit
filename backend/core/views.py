import os

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions


class HealthCheckView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({
            "status": "ok",
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        }, status=status.HTTP_200_OK)
