from typing import Any

from apps.accounts.models import CustomUser
from apps.accounts.permissions import IsAdminRole, IsSurveyorRole
from django.contrib.gis.geos import Point
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Route, RouteStop, TreeObservation
from .osrm import fetch_route_path
from .serializers import (
    RouteAssignSerializer,
    RouteDetailSerializer,
    RouteSerializer,
    RouteStopSerializer,
    TreeObservationInputSerializer,
    TreeObservationSerializer,
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
        queryset = Route.objects.select_related("surveyor", "solution")
        if self.request.user.role != CustomUser.Role.ADMIN:
            queryset = queryset.filter(surveyor=self.request.user)
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
        if not request.query_params.get("solution_id"):
            return Response(
                {"detail": "El parámetro solution_id es obligatorio."},
                status=400,
            )
        features = []
        for route in self.get_queryset():
            stop_coordinates = [
                [stop.tree.location.x, stop.tree.location.y]
                for stop in route.stops.all()
            ]
            coordinates = fetch_route_path(stop_coordinates)
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                    "properties": {
                        "route_number": route.route_number,
                        "total_trees": route.total_trees,
                        "travel_time_sec": route.travel_time_sec,
                        "stops": stop_coordinates,
                    },
                }
            )
        return Response({"type": "FeatureCollection", "features": features})

    @action(detail=True, methods=["patch"])
    def assign(self, request, pk=None):
        route = self.get_object()
        serializer = RouteAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        surveyor = serializer.validated_data["surveyor_id"]
        if surveyor is not None and route.solution.published_at is None:
            return Response(
                {"detail": "Solo se puede asignar sobre la solución publicada."},
                status=400,
            )
        route.surveyor = surveyor
        route.save(update_fields=["surveyor"])
        return Response(RouteSerializer(route).data)

    @action(detail=False, methods=["get"], url_path="my-route")
    def my_route(self, request):
        routes = (
            Route.objects.select_related("surveyor")
            .prefetch_related("stops__tree")
            .filter(surveyor=request.user, solution__published_at__isnull=False)
        )
        return Response(RouteSerializer(routes, many=True).data)


ORDER_ERROR = "Debes visitar los árboles anteriores primero."


class RouteStopVisitView(APIView):
    permission_classes = [IsSurveyorRole]

    def post(self, request, stop_id):
        stop = get_object_or_404(RouteStop, id=stop_id, route__surveyor=request.user)
        observation = TreeObservationInputSerializer(data=request.data)
        observation.is_valid(raise_exception=True)
        if stop.status != RouteStop.Status.PENDING:
            return Response(RouteStopSerializer(stop).data)
        if stop.has_pending_predecessor():
            return Response({"detail": ORDER_ERROR}, status=400)
        location = None
        lat = request.data.get("lat")
        lon = request.data.get("lon")
        if lat is not None and lon is not None:
            location = Point(float(lon), float(lat), srid=4326)
        stop.mark_visited(location=location, notes=request.data.get("notes"))
        data = observation.validated_data
        TreeObservation.objects.create(
            tree=stop.tree,
            route_stop=stop,
            status=data.get("status", TreeObservation.Status.ALIVE),
            photo=data.get("photo"),
            notes=data.get("notes", ""),
            created_by=request.user,
        )
        return Response(RouteStopSerializer(stop).data)


class RouteStopSkipView(APIView):
    permission_classes = [IsSurveyorRole]

    def post(self, request, stop_id):
        stop = get_object_or_404(RouteStop, id=stop_id, route__surveyor=request.user)
        observation = TreeObservationInputSerializer(data=request.data)
        observation.is_valid(raise_exception=True)
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"detail": "Debes indicar un motivo."}, status=400)
        if stop.status == RouteStop.Status.SKIPPED:
            return Response(RouteStopSerializer(stop).data)
        if stop.status == RouteStop.Status.VISITED:
            return Response({"detail": "El árbol ya fue visitado."}, status=400)
        if stop.has_pending_predecessor():
            return Response({"detail": ORDER_ERROR}, status=400)
        stop.mark_skipped(reason)
        data = observation.validated_data
        TreeObservation.objects.create(
            tree=stop.tree,
            route_stop=stop,
            status=data.get("status", TreeObservation.status_for_skip(reason)),
            photo=data.get("photo"),
            notes=data.get("notes", ""),
            created_by=request.user,
        )
        return Response(RouteStopSerializer(stop).data)


class TreeObservationListView(ListAPIView):
    serializer_class = TreeObservationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TreeObservation.objects.filter(
            tree_id=self.kwargs["tree_id"]
        ).select_related("created_by")
