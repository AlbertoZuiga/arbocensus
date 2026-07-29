from typing import Any

from apps.accounts.models import CustomUser
from apps.accounts.permissions import IsAdminRole, IsSurveyorRole
from apps.datasets import legacy
from apps.datasets.models import Dataset, Tree
from django.contrib.gis.geos import Point
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import osrm
from .models import Route, RouteStop, TreeObservation
from .progress import census_progress, census_progress_geojson
from .serializers import (
    DatasetQuerySerializer,
    RouteAssignSerializer,
    RouteDetailSerializer,
    RouteSerializer,
    RouteStopSerializer,
    SuggestAssignmentSerializer,
    TreeObservationInputSerializer,
    TreeObservationSerializer,
)
from .workload import suggest_assignment, surveyor_workload


class RouteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self) -> Any:
        if self.action in ("assign", "progress", "progress_geojson"):
            return [IsAdminRole()]
        if self.action == "my_route":
            return [IsSurveyorRole()]
        return [IsAuthenticated()]

    def get_queryset(self) -> Any:
        queryset = Route.objects.select_related(
            "surveyor", "solution"
        ).with_stop_counts()
        if self.request.user.role != CustomUser.Role.ADMIN:
            queryset = queryset.filter(surveyor=self.request.user)
        if self.action in ("retrieve", "geojson", "path"):
            queryset = queryset.prefetch_related("stops__tree")
        solution_id = self.request.query_params.get("solution_id")
        if solution_id:
            queryset = queryset.filter(solution_id=solution_id)
        return queryset

    def get_serializer_class(self) -> Any:
        if self.action == "retrieve":
            return RouteDetailSerializer
        return RouteSerializer

    @staticmethod
    def _stop_coordinates(route):
        return [
            [stop.tree.location.x, stop.tree.location.y] for stop in route.stops.all()
        ]

    @staticmethod
    def _stop_markers(route):
        return [
            {
                "tree_id": str(stop.tree.id),
                "coordinates": [stop.tree.location.x, stop.tree.location.y],
            }
            for stop in route.stops.all()
        ]

    @classmethod
    def _route_geometry(cls, route):
        stop_coordinates = cls._stop_coordinates(route)
        coordinates = osrm.fetch_route_path(stop_coordinates)
        return stop_coordinates, coordinates

    @action(detail=False, methods=["get"])
    def geojson(self, request):
        if not request.query_params.get("solution_id"):
            return Response(
                {"detail": "El parámetro solution_id es obligatorio."},
                status=400,
            )
        routes = list(self.get_queryset())
        paths = osrm.fetch_route_paths(
            [self._stop_coordinates(route) for route in routes]
        )
        features = []
        for route, coordinates in zip(routes, paths, strict=True):
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                    "properties": {
                        "route_number": route.route_number,
                        "total_trees": route.total_trees,
                        "travel_time_sec": route.travel_time_sec,
                        "total_service_time_sec": route.total_estimated_time_sec
                        - route.travel_time_sec,
                        "total_estimated_time_sec": route.total_estimated_time_sec,
                        "stops": self._stop_markers(route),
                    },
                }
            )
        return Response({"type": "FeatureCollection", "features": features})

    @action(detail=True, methods=["get"])
    def path(self, request, pk=None):
        route = self.get_object()
        _, coordinates = self._route_geometry(route)
        return Response({"type": "LineString", "coordinates": coordinates})

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

    def _dataset_id(self, request):
        query = DatasetQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data: Any = query.validated_data
        return get_object_or_404(Dataset, pk=data["dataset"]).id

    @action(detail=False, methods=["get"])
    def progress(self, request):
        return Response(census_progress(self._dataset_id(request)))

    @action(detail=False, methods=["get"], url_path="progress-geojson")
    def progress_geojson(self, request):
        return Response(census_progress_geojson(self._dataset_id(request)))

    @action(detail=False, methods=["get"], url_path="my-route")
    def my_route(self, request):
        routes = (
            Route.objects.select_related("surveyor")
            .prefetch_related("stops__tree")
            .with_stop_counts()
            .filter(surveyor=request.user, solution__published_at__isnull=False)
        )
        return Response(RouteSerializer(routes, many=True).data)


ORDER_ERROR = "Debes visitar los árboles anteriores primero."

# A visit that asserts the tree was seen must carry the evidence. `not_found` is exempt
# because there is no tree to photograph, and `other`/`unknown` assert nothing about it.
PHOTO_REQUIRED_STATUSES = frozenset(
    {TreeObservation.Status.ALIVE, TreeObservation.Status.REMOVED}
)
PHOTO_ERROR = "La fotografía es obligatoria para registrar este estado del árbol."


def _locked_stop(stop_id, user):
    return get_object_or_404(
        RouteStop.objects.select_related("tree", "route").select_for_update(
            of=("self",)
        ),
        id=stop_id,
        route__surveyor=user,
    )


class RouteStopVisitView(APIView):
    permission_classes = [IsSurveyorRole]

    def post(self, request, stop_id):
        observation = TreeObservationInputSerializer(data=request.data)
        observation.is_valid(raise_exception=True)
        data: Any = observation.validated_data
        status = data.get("status", TreeObservation.Status.ALIVE)
        location = None
        lat = data.get("lat")
        lon = data.get("lon")
        if lat is not None and lon is not None:
            location = Point(lon, lat, srid=4326)
        with transaction.atomic():
            stop = _locked_stop(stop_id, request.user)
            if stop.status != RouteStop.Status.PENDING:
                return Response(RouteStopSerializer(stop).data)
            # After the ownership lookup, so a caller who does not own the stop keeps
            # getting a 404 instead of a hint that the stop exists.
            if status in PHOTO_REQUIRED_STATUSES and not data.get("photo"):
                return Response({"detail": PHOTO_ERROR}, status=400)
            if stop.has_pending_predecessor():
                return Response({"detail": ORDER_ERROR}, status=400)
            stop.mark_visited(location=location, notes=data.get("notes"))
            TreeObservation.objects.create(
                tree=stop.tree,
                route_stop=stop,
                status=status,
                photo=data.get("photo"),
                notes=data.get("notes", ""),
                created_by=request.user,
            )
        return Response(RouteStopSerializer(stop).data)


class RouteStopSkipView(APIView):
    permission_classes = [IsSurveyorRole]

    def post(self, request, stop_id):
        observation = TreeObservationInputSerializer(data=request.data)
        observation.is_valid(raise_exception=True)
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"detail": "Debes indicar un motivo."}, status=400)
        data: Any = observation.validated_data
        with transaction.atomic():
            stop = _locked_stop(stop_id, request.user)
            if stop.status == RouteStop.Status.SKIPPED:
                return Response(RouteStopSerializer(stop).data)
            if stop.status == RouteStop.Status.VISITED:
                return Response({"detail": "El árbol ya fue visitado."}, status=400)
            if stop.has_pending_predecessor():
                return Response({"detail": ORDER_ERROR}, status=400)
            stop.mark_skipped(reason)
            TreeObservation.objects.create(
                tree=stop.tree,
                route_stop=stop,
                status=data.get("status", TreeObservation.status_for_skip(reason)),
                photo=data.get("photo"),
                notes=data.get("notes", ""),
                created_by=request.user,
            )
        return Response(RouteStopSerializer(stop).data)


class WorkloadView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response(surveyor_workload())


class SuggestAssignmentView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request):
        from apps.optimization.models import RoutingSolution

        serializer = SuggestAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: Any = serializer.validated_data

        solution_id = data["solution_id"]
        surveyor_ids = [u.id for u in data["surveyor_ids"]]

        try:
            solution = RoutingSolution.objects.get(id=solution_id)
        except RoutingSolution.DoesNotExist:
            return Response({"detail": "Solución no encontrada."}, status=404)

        if solution.published_at is None:
            return Response(
                {"detail": "Solo se puede asignar sobre la solución publicada."},
                status=400,
            )

        assignments, balance = suggest_assignment(solution_id, surveyor_ids)
        return Response({"assignments": assignments, "balance": balance})


class TreeObservationListView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _legacy_history(tree):
        if tree.source not in legacy.SOURCES or tree.external_id is None:
            return []
        try:
            return legacy.tree_observations(tree.source, tree.external_id)
        except legacy.LegacyDatabaseNotConfiguredError:
            return None

    @staticmethod
    def _visible_trees(user):
        if user.role == CustomUser.Role.ADMIN:
            return Tree.objects.all()
        return Tree.objects.filter(routestop__route__surveyor=user).distinct()

    def get(self, request, tree_id):
        tree = get_object_or_404(self._visible_trees(request.user), id=tree_id)
        # The legacy history is read live: datasets loaded from frozen instance
        # CSVs never received the import-time TreeObservation snapshot, and the
        # same legacy tree lives in as many Tree rows as datasets hold it. Only
        # when the legacy database is unavailable does the snapshot stand in.
        live = self._legacy_history(tree)
        if tree.source in legacy.SOURCES and tree.external_id is not None:
            tree_ids = Tree.objects.filter(
                source=tree.source, external_id=tree.external_id
            ).values_list("id", flat=True)
        else:
            tree_ids = [tree_id]
        stored = TreeObservation.objects.filter(tree_id__in=tree_ids).select_related(
            "created_by"
        )
        if live is not None:
            stored = stored.exclude(source__in=legacy.SOURCES)
        entries = [
            (observation.observed_at, TreeObservationSerializer(observation).data)
            for observation in stored
        ]
        entries += [(row["observed_at"], row) for row in live or []]
        entries.sort(key=lambda entry: entry[0], reverse=True)
        return Response([data for _, data in entries])
