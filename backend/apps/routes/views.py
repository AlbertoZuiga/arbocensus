from typing import Any

from apps.accounts.permissions import IsSurveyorRole
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Route, RouteStop
from .serializers import RouteDetailSerializer, RouteSerializer, RouteStopSerializer


class RouteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> Any:
        queryset = Route.objects.all()
        if self.action in ("retrieve", "geojson"):
            queryset = queryset.prefetch_related("stops__tree")
        solution_id = self.request.query_params.get("solution_id")
        if solution_id:
            queryset = queryset.filter(solution_id=solution_id)
        return queryset

    def get_serializer_class(self) -> Any:
        if self.action == "retrieve":
            return RouteDetailSerializer
        return RouteSerializer

    @action(detail=False, methods=["get"])
    def geojson(self, request):
        features = []
        for route in self.get_queryset():
            coordinates = [
                [stop.tree.location.x, stop.tree.location.y]
                for stop in route.stops.all()
            ]
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                    "properties": {
                        "route_number": route.route_number,
                        "total_trees": route.total_trees,
                        "travel_time_sec": route.travel_time_sec,
                    },
                }
            )
        return Response({"type": "FeatureCollection", "features": features})


class RouteStopVisitView(APIView):
    permission_classes = [IsSurveyorRole]

    def post(self, request, stop_id):
        stop = get_object_or_404(RouteStop, id=stop_id, route__surveyor=request.user)
        stop.visited = True
        stop.visited_at = timezone.now()
        stop.notes = request.data.get("notes", stop.notes)
        stop.save(update_fields=["visited", "visited_at", "notes"])
        return Response(RouteStopSerializer(stop).data)
