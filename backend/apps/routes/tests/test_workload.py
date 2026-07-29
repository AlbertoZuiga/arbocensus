import pytest
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.routes.models import Route
from apps.routes.workload import (
    route_utilization,
    suggest_assignment,
    surveyor_workload,
)
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def make_published_solution(make_dataset_with_trees):
    def _make(coords, max_route_time_sec=3600):
        dataset, trees = make_dataset_with_trees(coords)
        config = RoutingConfig.objects.create(
            dataset=dataset,
            min_route_time_sec=1,
            max_route_time_sec=max_route_time_sec,
        )
        job = OptimizationJob.objects.create(config=config)
        solution = RoutingSolution.objects.create(job=job, total_routes=len(coords))
        solution.publish()
        return solution, trees

    return _make


def _make_route(solution, trees, surveyor, total_estimated_time_sec=1800):
    route_number = solution.routes.count() + 1
    return Route.objects.create(
        solution=solution,
        route_number=route_number,
        total_trees=len(trees),
        surveyor=surveyor,
        total_estimated_time_sec=total_estimated_time_sec,
    )


def _admin_client():
    client = APIClient()
    client.force_authenticate(user=CustomUserFactory(role="admin"))
    return client


def _surveyor_client():
    user = CustomUserFactory(role="surveyor")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestRouteUtilization:
    def test_normalizes_by_max_route_time_sec(self, make_published_solution):
        solution_a, trees_a = make_published_solution(
            [(-70.65, -33.45)], max_route_time_sec=3600
        )
        solution_b, trees_b = make_published_solution(
            [(-70.66, -33.46)], max_route_time_sec=7200
        )
        surveyor = CustomUserFactory(role="surveyor")
        route_a = _make_route(
            solution_a, trees_a, surveyor, total_estimated_time_sec=1800
        )
        route_b = _make_route(
            solution_b, trees_b, surveyor, total_estimated_time_sec=3600
        )

        assert route_utilization(route_a) == pytest.approx(0.5)
        assert route_utilization(route_b) == pytest.approx(0.5)

    def test_returns_one_for_saturated_route(self, make_published_solution):
        solution, trees = make_published_solution(
            [(-70.65, -33.45)], max_route_time_sec=3600
        )
        surveyor = CustomUserFactory(role="surveyor")
        route = _make_route(solution, trees, surveyor, total_estimated_time_sec=3600)
        assert route_utilization(route) == pytest.approx(1.0)


class TestSurveyorWorkload:
    def test_cumulative_deficit_underdone_positive(self, make_published_solution):
        solution, trees = make_published_solution(
            [(-70.65, -33.45), (-70.66, -33.46)], max_route_time_sec=3600
        )
        ana = CustomUserFactory(username="ana_wl", role="surveyor")
        bob = CustomUserFactory(username="bob_wl", role="surveyor")
        # Ana: 3600s = 1.0x, Bob: 1800s = 0.5x
        # fair_share = 0.75x  →  ana = -0.25 (over), bob = +0.25 (under)
        _make_route(solution, trees[:1], ana, total_estimated_time_sec=3600)
        _make_route(solution, trees[1:], bob, total_estimated_time_sec=1800)

        result = surveyor_workload()
        by_user = {r["username"]: r for r in result}

        assert by_user["bob_wl"]["cumulative_deficit"] == pytest.approx(0.25, abs=0.001)
        assert by_user["ana_wl"]["cumulative_deficit"] == pytest.approx(
            -0.25, abs=0.001
        )

    def test_ignores_unpublished_solutions(self, make_dataset_with_trees):
        dataset, trees = make_dataset_with_trees([(-70.65, -33.45)])
        config = RoutingConfig.objects.create(
            dataset=dataset, min_route_time_sec=1, max_route_time_sec=3600
        )
        job = OptimizationJob.objects.create(config=config)
        solution = RoutingSolution.objects.create(job=job, total_routes=1)
        # not published
        surveyor = CustomUserFactory(role="surveyor")
        Route.objects.create(
            solution=solution,
            route_number=1,
            total_trees=1,
            surveyor=surveyor,
            total_estimated_time_sec=1800,
        )

        result = surveyor_workload()
        assert all(r["surveyor_id"] != str(surveyor.id) for r in result)

    def test_ignores_routes_without_surveyor(self, make_published_solution):
        solution, trees = make_published_solution([(-70.65, -33.45)])
        Route.objects.create(
            solution=solution,
            route_number=1,
            total_trees=1,
            total_estimated_time_sec=1800,
        )
        assert surveyor_workload() == []


class TestSurveyorWorkloadParticipants:
    def test_participant_with_no_routes_earns_positive_credit(
        self, make_published_solution
    ):
        """Scenario A/B/C: C is selected but gets no routes; deficit must decrease."""
        solution, trees = make_published_solution(
            [(-70.65, -33.45), (-70.66, -33.46), (-70.67, -33.47)],
            max_route_time_sec=3600,
        )
        ana = CustomUserFactory(username="ana_p", role="surveyor")
        bob = CustomUserFactory(username="bob_p", role="surveyor")
        carlos = CustomUserFactory(username="carlos_p", role="surveyor")

        # 6 routes * util 0.5 each = 3.0 total; 3 routes to Ana, 3 to Bob
        for _ in range(3):
            _make_route(solution, trees[:1], ana, total_estimated_time_sec=1800)
        for _ in range(3):
            _make_route(solution, trees[1:2], bob, total_estimated_time_sec=1800)

        solution.participants.set([ana, bob, carlos])

        result = surveyor_workload()
        by_user = {r["username"]: r for r in result}

        # total_util = 3.0, n = 3, fair_share = 1.0
        # ana: 1.5 routes * util 0.5 = 1.5 → deficit = 1.0 - 1.5 = -0.5
        # bob: 1.5 routes * util 0.5 = 1.5 → deficit = 1.0 - 1.5 = -0.5
        # carlos: 0 routes → deficit = 1.0 - 0 = +1.0
        assert by_user["carlos_p"]["cumulative_deficit"] == pytest.approx(
            1.0, abs=0.001
        )
        assert by_user["ana_p"]["cumulative_deficit"] == pytest.approx(-0.5, abs=0.001)
        assert by_user["bob_p"]["cumulative_deficit"] == pytest.approx(-0.5, abs=0.001)

    def test_census_deficits_sum_to_zero(self, make_published_solution):
        solution, trees = make_published_solution(
            [(-70.65, -33.45), (-70.66, -33.46)], max_route_time_sec=3600
        )
        ana = CustomUserFactory(username="ana_sum", role="surveyor")
        bob = CustomUserFactory(username="bob_sum", role="surveyor")
        carlos = CustomUserFactory(username="carlos_sum", role="surveyor")

        _make_route(solution, trees[:1], ana, total_estimated_time_sec=3000)
        _make_route(solution, trees[1:], bob, total_estimated_time_sec=1200)

        solution.participants.set([ana, bob, carlos])

        result = surveyor_workload()
        by_user = {r["username"]: r for r in result}

        total = sum(
            float(r["cumulative_deficit"])
            for r in [by_user["ana_sum"], by_user["bob_sum"], by_user["carlos_sum"]]
        )
        assert total == pytest.approx(0.0, abs=0.001)

    def test_backwards_compat_no_registered_participants(self, make_published_solution):
        """Solutions without registered participants fall back to surveyors-with-routes."""
        solution, trees = make_published_solution(
            [(-70.65, -33.45), (-70.66, -33.46)], max_route_time_sec=3600
        )
        ana = CustomUserFactory(username="ana_bc", role="surveyor")
        bob = CustomUserFactory(username="bob_bc", role="surveyor")
        _make_route(solution, trees[:1], ana, total_estimated_time_sec=3600)
        _make_route(solution, trees[1:], bob, total_estimated_time_sec=1800)
        # no participants set — legacy behavior

        result = surveyor_workload()
        by_user = {r["username"]: r for r in result}

        assert "ana_bc" in by_user
        assert "bob_bc" in by_user
        # fair_share = (1.0 + 0.5) / 2 = 0.75
        assert by_user["ana_bc"]["cumulative_deficit"] == pytest.approx(
            -0.25, abs=0.001
        )
        assert by_user["bob_bc"]["cumulative_deficit"] == pytest.approx(0.25, abs=0.001)

    def test_abc_scenario_deficit_does_not_freeze(self, make_published_solution):
        """
        Exact A/B/C scenario from the bug report:
        6 routes util 0.3 each, A gets 3, B gets 3, C gets 0.
        With participants registered, C accumulates +0.6 (fair_share), not 0.
        """
        solution, trees = make_published_solution(
            [(-70.65, -33.45)], max_route_time_sec=10
        )
        a = CustomUserFactory(username="a_abc", role="surveyor")
        b = CustomUserFactory(username="b_abc", role="surveyor")
        c = CustomUserFactory(username="c_abc", role="surveyor")

        for _ in range(3):
            _make_route(solution, trees, a, total_estimated_time_sec=3)
        for _ in range(3):
            _make_route(solution, trees, b, total_estimated_time_sec=3)

        solution.participants.set([a, b, c])

        result = surveyor_workload()
        by_user = {r["username"]: r for r in result}

        # total_util = 6 * 0.3 = 1.8, n = 3, fair_share = 0.6
        assert by_user["c_abc"]["cumulative_deficit"] == pytest.approx(0.6, abs=0.001)
        assert by_user["a_abc"]["cumulative_deficit"] == pytest.approx(-0.3, abs=0.001)
        assert by_user["b_abc"]["cumulative_deficit"] == pytest.approx(-0.3, abs=0.001)

    def test_surveyor_with_routes_outside_registered_set_is_counted(
        self, make_published_solution
    ):
        """Manual assignment outside the registered set must not inflate fair_share."""
        solution, trees = make_published_solution(
            [(-70.65, -33.45)], max_route_time_sec=10
        )
        a = CustomUserFactory(username="a_out", role="surveyor")
        b = CustomUserFactory(username="b_out", role="surveyor")
        c = CustomUserFactory(username="c_out", role="surveyor")

        _make_route(solution, trees, a, total_estimated_time_sec=3)
        _make_route(solution, trees, b, total_estimated_time_sec=6)

        solution.participants.set([a, c])

        result = surveyor_workload()
        by_user = {r["username"]: r for r in result}

        # total_util = 0.9 over {a, b, c} → fair_share = 0.3
        assert by_user["a_out"]["cumulative_deficit"] == pytest.approx(0.0, abs=0.001)
        assert by_user["b_out"]["cumulative_deficit"] == pytest.approx(-0.3, abs=0.001)
        assert by_user["c_out"]["cumulative_deficit"] == pytest.approx(0.3, abs=0.001)


class TestSolutionParticipantsEndpoint:
    def test_admin_sets_participants(self, make_published_solution):
        solution, _ = make_published_solution([(-70.65, -33.45)])
        surveyor = CustomUserFactory(role="surveyor")

        response = _admin_client().post(
            f"/api/routes/solutions/{solution.id}/participants/",
            {"participant_ids": [str(surveyor.id)]},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["participant_count"] == 1
        solution.refresh_from_db()
        assert solution.participants.filter(id=surveyor.id).exists()

    def test_empty_list_clears_participants(self, make_published_solution):
        solution, _ = make_published_solution([(-70.65, -33.45)])
        surveyor = CustomUserFactory(role="surveyor")
        solution.participants.set([surveyor])

        response = _admin_client().post(
            f"/api/routes/solutions/{solution.id}/participants/",
            {"participant_ids": []},
            format="json",
        )

        assert response.status_code == 200
        assert solution.participants.count() == 0

    def test_rejects_unpublished_solution(self, make_dataset_with_trees):
        dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
        from apps.optimization.models import (
            OptimizationJob,
            RoutingConfig,
            RoutingSolution,
        )

        config = RoutingConfig.objects.create(
            dataset=dataset, min_route_time_sec=1, max_route_time_sec=3600
        )
        job = OptimizationJob.objects.create(config=config)
        solution = RoutingSolution.objects.create(job=job, total_routes=1)
        surveyor = CustomUserFactory(role="surveyor")

        response = _admin_client().post(
            f"/api/routes/solutions/{solution.id}/participants/",
            {"participant_ids": [str(surveyor.id)]},
            format="json",
        )

        assert response.status_code == 404

    def test_surveyor_gets_403(self, make_published_solution):
        solution, _ = make_published_solution([(-70.65, -33.45)])
        surveyor = CustomUserFactory(role="surveyor")

        response = _surveyor_client().post(
            f"/api/routes/solutions/{solution.id}/participants/",
            {"participant_ids": [str(surveyor.id)]},
            format="json",
        )

        assert response.status_code == 403


class TestSuggestAssignment:
    def test_heavy_route_goes_to_candidate_with_highest_deficit(
        self, make_published_solution
    ):
        # Prior census: Ana overloaded, Bob underloaded
        prior, prior_trees = make_published_solution(
            [(-70.65, -33.45), (-70.66, -33.46)], max_route_time_sec=3600
        )
        ana = CustomUserFactory(username="ana_sg", role="surveyor")
        bob = CustomUserFactory(username="bob_sg", role="surveyor")
        _make_route(prior, prior_trees[:1], ana, total_estimated_time_sec=3600)
        _make_route(prior, prior_trees[1:], bob, total_estimated_time_sec=600)
        # fair_share = (1.0 + 0.167) / 2 ≈ 0.583
        # ana deficit = -0.417, bob deficit = +0.417

        new_solution, _ = make_published_solution(
            [(-70.67, -33.47), (-70.68, -33.48)], max_route_time_sec=3600
        )
        route_heavy = Route.objects.create(
            solution=new_solution,
            route_number=1,
            total_trees=1,
            total_estimated_time_sec=3000,
        )
        Route.objects.create(
            solution=new_solution,
            route_number=2,
            total_trees=1,
            total_estimated_time_sec=600,
        )

        assignments, _ = suggest_assignment(new_solution.id, [ana.id, bob.id])

        by_route = {a["route_id"]: a for a in assignments}
        assert by_route[str(route_heavy.id)]["surveyor_id"] == str(bob.id)

    def test_proposal_does_not_persist(self, make_published_solution):
        solution, _ = make_published_solution(
            [(-70.65, -33.45)], max_route_time_sec=3600
        )
        surveyor = CustomUserFactory(role="surveyor")
        route = Route.objects.create(
            solution=solution,
            route_number=1,
            total_trees=1,
            total_estimated_time_sec=1800,
        )

        suggest_assignment(solution.id, [surveyor.id])

        route.refresh_from_db()
        assert route.surveyor is None

    def test_all_routes_get_assigned(self, make_published_solution):
        solution, _ = make_published_solution(
            [(-70.65, -33.45), (-70.66, -33.46)], max_route_time_sec=3600
        )
        ana = CustomUserFactory(role="surveyor")
        bob = CustomUserFactory(role="surveyor")
        Route.objects.create(
            solution=solution,
            route_number=1,
            total_trees=1,
            total_estimated_time_sec=2000,
        )
        Route.objects.create(
            solution=solution,
            route_number=2,
            total_trees=1,
            total_estimated_time_sec=1500,
        )

        assignments, _ = suggest_assignment(solution.id, [ana.id, bob.id])

        assert len(assignments) == 2
        assigned_surveyors = {a["surveyor_id"] for a in assignments}
        assert assigned_surveyors == {str(ana.id), str(bob.id)}


class TestWorkloadEndpoint:
    def test_admin_gets_200(self):
        response = _admin_client().get("/api/routes/workload/")
        assert response.status_code == 200
        assert isinstance(response.data, list)

    def test_surveyor_gets_403(self):
        response = _surveyor_client().get("/api/routes/workload/")
        assert response.status_code == 403

    def test_unauthenticated_gets_401(self):
        response = APIClient().get("/api/routes/workload/")
        assert response.status_code == 401


class TestSuggestAssignmentEndpoint:
    def test_admin_can_suggest(self, make_published_solution):
        solution, _ = make_published_solution(
            [(-70.65, -33.45)], max_route_time_sec=3600
        )
        Route.objects.create(
            solution=solution,
            route_number=1,
            total_trees=1,
            total_estimated_time_sec=1800,
        )
        surveyor = CustomUserFactory(role="surveyor")

        response = _admin_client().post(
            "/api/routes/suggest-assignment/",
            {"solution_id": str(solution.id), "surveyor_ids": [str(surveyor.id)]},
            format="json",
        )

        assert response.status_code == 200
        assert "assignments" in response.data
        assert "balance" in response.data

    def test_surveyor_gets_403(self, make_published_solution):
        solution, _ = make_published_solution([(-70.65, -33.45)])
        surveyor = CustomUserFactory(role="surveyor")

        response = _surveyor_client().post(
            "/api/routes/suggest-assignment/",
            {"solution_id": str(solution.id), "surveyor_ids": [str(surveyor.id)]},
            format="json",
        )

        assert response.status_code == 403

    def test_rejects_unpublished_solution(self, make_dataset_with_trees):
        dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
        config = RoutingConfig.objects.create(
            dataset=dataset, min_route_time_sec=1, max_route_time_sec=3600
        )
        job = OptimizationJob.objects.create(config=config)
        solution = RoutingSolution.objects.create(job=job, total_routes=1)
        # not published
        surveyor = CustomUserFactory(role="surveyor")

        response = _admin_client().post(
            "/api/routes/suggest-assignment/",
            {"solution_id": str(solution.id), "surveyor_ids": [str(surveyor.id)]},
            format="json",
        )

        assert response.status_code == 400

    def test_rejects_inactive_surveyor(self, make_published_solution):
        solution, _ = make_published_solution([(-70.65, -33.45)])
        inactive = CustomUserFactory(role="surveyor", is_active=False)

        response = _admin_client().post(
            "/api/routes/suggest-assignment/",
            {"solution_id": str(solution.id), "surveyor_ids": [str(inactive.id)]},
            format="json",
        )

        assert response.status_code == 400
