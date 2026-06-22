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
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Route.objects.all()
        solution_id = self.request.query_params.get("solution_id")
        if solution_id:
            queryset = queryset.filter(solution_id=solution_id)
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return RouteDetailSerializer
        return RouteSerializer

    @action(detail=True, methods=["get"])
    def stops(self, request, pk=None):
        route = self.get_object()
        stops = route.stops.select_related("tree")
        return Response(RouteStopSerializer(stops, many=True).data)

    @action(detail=False, methods=["get"])
    def geojson(self, request):
        solution_id = request.query_params.get("solution_id")
        routes = Route.objects.filter(solution_id=solution_id) if solution_id else Route.objects.none()
        features = []
        for route in routes.prefetch_related("stops__tree"):
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
    permission_classes = [IsAuthenticated]

    def post(self, request, stop_id):
        stop = get_object_or_404(RouteStop, id=stop_id)
        stop.visited = True
        stop.visited_at = timezone.now()
        stop.notes = request.data.get("notes", stop.notes)
        stop.save(update_fields=["visited", "visited_at", "notes"])
        return Response(RouteStopSerializer(stop).data)
