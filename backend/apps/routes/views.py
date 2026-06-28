from typing import Any

from apps.accounts.permissions import IsAdminRole, IsSurveyorRole
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Route, RouteStop
from .serializers import (
    RouteAssignSerializer,
    RouteDetailSerializer,
    RouteSerializer,
    RouteStopSerializer,
)


class RouteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self) -> Any:
        if self.action == "assign":
            return [IsAdminRole()]
        if self.action == "my_route":
            return [IsSurveyorRole()]
        return [IsAuthenticated()]

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

    @action(detail=True, methods=["patch"])
    def assign(self, request, pk=None):
        route = self.get_object()
        serializer = RouteAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        route.surveyor = serializer.validated_data["surveyor_id"]
        route.save(update_fields=["surveyor"])
        return Response(RouteSerializer(route).data)

    @action(detail=False, methods=["get"], url_path="my-route")
    def my_route(self, request):
        routes = Route.objects.filter(surveyor=request.user)
        return Response(RouteSerializer(routes, many=True).data)


class RouteStopVisitView(APIView):
    permission_classes = [IsSurveyorRole]

    def post(self, request, stop_id):
        stop = get_object_or_404(RouteStop, id=stop_id, route__surveyor=request.user)
        if stop.visited:
            return Response(RouteStopSerializer(stop).data)
        if RouteStop.objects.filter(
            route=stop.route, sequence__lt=stop.sequence, visited=False
        ).exists():
            return Response(
                {"detail": "Debes visitar los árboles anteriores primero."},
                status=400,
            )
        stop.visited = True
        stop.visited_at = timezone.now()
        stop.notes = request.data.get("notes", stop.notes)
        stop.save(update_fields=["visited", "visited_at", "notes"])
        return Response(RouteStopSerializer(stop).data)
