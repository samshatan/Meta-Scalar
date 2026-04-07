"""
Smoke tests for the Incident Response OpenEnv environment.
Run: python -m pytest tests/test_env.py -v
"""

import sys

import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from environment.env import IncidentResponseEnv

from environment.models import Action, ActionType, IncidentCategory, RemediationAction

from environment.tasks import TASKS, GRADERS

@pytest.fixture

def env():

    return IncidentResponseEnv()

class TestTask1:

    def test_reset_returns_observation(self, env):

        obs = env.reset("alert_classification", 0)

        assert obs.task_id == "alert_classification"

        assert len(obs.alerts) > 0

        assert obs.step == 0

        assert obs.classified is False

        assert obs.visible_logs == []

    def test_investigate_reveals_logs(self, env):

        env.reset("alert_classification", 0)

        action = Action(action_type=ActionType.INVESTIGATE, service_name="postgres-primary")

        obs, reward, done, info = env.step(action)

        assert len(obs.visible_logs) > 0

        assert "postgres-primary" in obs.investigations_done

        assert reward.score > 0

        assert not done

    def test_correct_classification_gives_reward(self, env):

        env.reset("alert_classification", 0)

        action = Action(

            action_type=ActionType.CLASSIFY,

            category=IncidentCategory.DATABASE_CONNECTION,

        )

        obs, reward, done, info = env.step(action)

        assert obs.classified is True

        assert obs.classification == "database_connection"

        assert reward.score == pytest.approx(0.30, abs=0.01)

    def test_wrong_classification_gives_zero(self, env):

        env.reset("alert_classification", 0)

        action = Action(

            action_type=ActionType.CLASSIFY,

            category=IncidentCategory.MEMORY_LEAK,

        )

        obs, reward, done, info = env.step(action)

        assert reward.score == 0.0

    def test_grader_correct_episode(self, env):

        env.reset("alert_classification", 0)

        env.step(Action(action_type=ActionType.INVESTIGATE, service_name="postgres-primary"))

        env.step(Action(action_type=ActionType.CLASSIFY, category=IncidentCategory.DATABASE_CONNECTION))

        result = env.grade()

        assert 0.0 <= result["score"] <= 1.0

        assert result["breakdown"]["classification_correct"] == 1.0

        assert result["score"] > 0.5

    def test_grader_wrong_classification(self, env):

        env.reset("alert_classification", 0)

        env.step(Action(action_type=ActionType.CLASSIFY, category=IncidentCategory.MEMORY_LEAK))

        result = env.grade()

        assert result["breakdown"]["classification_correct"] == 0.0

        assert result["score"] == 0.0

    def test_grader_score_in_range(self, env):

        """Grader must always return score in [0.0, 1.0]."""

        for scenario_idx in range(len(TASKS["alert_classification"]["scenarios"])):

            env.reset("alert_classification", scenario_idx)

            result = env.grade()

            assert 0.0 <= result["score"] <= 1.0

class TestTask2:

    def test_reset(self, env):

        obs = env.reset("root_cause_analysis", 0)

        assert len(obs.alerts) >= 2

        assert obs.max_steps == 12

    def test_full_episode_partial_credit(self, env):

        env.reset("root_cause_analysis", 0)

        env.step(Action(action_type=ActionType.INVESTIGATE, service_name="checkout-service"))

        env.step(Action(action_type=ActionType.INVESTIGATE, service_name="auth-service"))

        env.step(Action(action_type=ActionType.CLASSIFY, category=IncidentCategory.CONFIGURATION_ERROR))

        obs, reward, done, _ = env.step(Action(

            action_type=ActionType.RESOLVE,

            resolution_summary="auth-service crashed due to missing VAULT_ROLE config."

        ))

        assert done

        result = env.grade()

        assert result["score"] >= 0.60

        assert result["breakdown"]["classification"] == 1.0

        assert result["breakdown"]["investigation"] == 1.0

        assert result["breakdown"]["root_identified"] == 1.0

    def test_penalty_for_reinvestigation(self, env):

        env.reset("root_cause_analysis", 0)

        env.step(Action(action_type=ActionType.INVESTIGATE, service_name="checkout-service"))

        _, reward, _, _ = env.step(Action(action_type=ActionType.INVESTIGATE, service_name="checkout-service"))

        assert reward.score < 0

    def test_grader_score_in_range(self, env):

        for _ in range(3):

            env.reset("root_cause_analysis", 0)

            result = env.grade()

            assert 0.0 <= result["score"] <= 1.0

class TestTask3:

    def test_reset(self, env):

        obs = env.reset("full_incident_response", 0)

        assert len(obs.alerts) >= 3

        assert obs.max_steps == 20

    def test_full_optimal_episode(self, env):

        env.reset("full_incident_response", 0)

        for svc in ["redis-cluster", "ml-feature-store", "api-gateway"]:

            env.step(Action(action_type=ActionType.INVESTIGATE, service_name=svc))

        env.step(Action(action_type=ActionType.CLASSIFY, category=IncidentCategory.RESOURCE_EXHAUSTION))

        env.step(Action(

            action_type=ActionType.REMEDIATE,

            service_name="redis-cluster",

            remediation_action=RemediationAction.CLEAR_DISK_SPACE,

        ))

        env.step(Action(

            action_type=ActionType.REMEDIATE,

            service_name="ml-feature-store",

            remediation_action=RemediationAction.RESTART_SERVICE,

        ))

        env.step(Action(

            action_type=ActionType.RESOLVE,

            resolution_summary=(

                "Platform outage caused by disk exhaustion on redis-cluster and "

                "ml-feature-store. Cleared disk space on redis, restarted feature "

                "store. Cluster recovered, all services healthy."

            )

        ))

        result = env.grade()

        assert result["score"] >= 0.75

        assert result["breakdown"]["classification"] == 1.0

        assert result["breakdown"]["root_coverage"] == 1.0

        assert result["breakdown"]["remediation"] >= 0.8

    def test_wrong_remediation_penalised(self, env):

        env.reset("full_incident_response", 0)

        env.step(Action(action_type=ActionType.INVESTIGATE, service_name="redis-cluster"))

        _, reward, _, _ = env.step(Action(

            action_type=ActionType.REMEDIATE,

            service_name="redis-cluster",

            remediation_action=RemediationAction.SCALE_UP,

        ))

        assert reward.score < 0

    def test_step_budget_enforced(self, env):

        env.reset("full_incident_response", 0)

        done = False

        steps = 0

        while not done and steps < 25:

            _, _, done, _ = env.step(Action(

                action_type=ActionType.INVESTIGATE,

                service_name="api-gateway"

            ))

            steps += 1

        assert done

        assert steps <= 21

    def test_grader_all_scores_in_range(self, env):

        for scenario_idx in range(len(TASKS["full_incident_response"]["scenarios"])):

            env.reset("full_incident_response", scenario_idx)

            result = env.grade()

            assert 0.0 <= result["score"] <= 1.0

            for k, v in result["breakdown"].items():

                assert 0.0 <= v <= 1.0, f"breakdown[{k}]={v} out of range"

class TestSpecCompliance:

    def test_state_returns_after_reset(self, env):

        env.reset("alert_classification", 0)

        s = env.state()

        assert s.observation is not None

        assert s.ground_truth is not None

        assert s.episode_done is False

    def test_reset_before_step_raises(self, env):

        with pytest.raises(RuntimeError):

            env.step(Action(action_type=ActionType.CLASSIFY, category=IncidentCategory.MEMORY_LEAK))

    def test_step_after_done_raises(self, env):

        env.reset("alert_classification", 0)

        env.step(Action(action_type=ActionType.RESOLVE, resolution_summary="Done."))

        with pytest.raises(RuntimeError):

            env.step(Action(action_type=ActionType.INVESTIGATE, service_name="postgres-primary"))

    def test_reset_clears_state(self, env):

        env.reset("alert_classification", 0)

        env.step(Action(action_type=ActionType.CLASSIFY, category=IncidentCategory.DATABASE_CONNECTION))

        obs = env.reset("alert_classification", 0)

        assert obs.classified is False

        assert obs.step == 0

        assert obs.visible_logs == []

    def test_invalid_task_raises(self, env):

        with pytest.raises(ValueError):

            env.reset("nonexistent_task")

    def test_all_tasks_present(self):

        assert "alert_classification"  in TASKS

        assert "root_cause_analysis"   in TASKS

        assert "full_incident_response" in TASKS

    def test_all_graders_callable(self):

        for task_id in TASKS:

            assert callable(GRADERS[task_id])

    def test_invalid_scenario_index_raises_valueerror(self, env):

        with pytest.raises(ValueError, match="Invalid scenario_index"):

            env.reset("alert_classification", -1)

        with pytest.raises(ValueError, match="Invalid scenario_index"):

            env.reset("alert_classification", 99)

    def test_cumulative_reward_non_decreasing_good_actions(self, env):

        env.reset("root_cause_analysis", 0)

        prev = 0.0

        good_actions = [

            Action(action_type=ActionType.INVESTIGATE, service_name="checkout-service"),

            Action(action_type=ActionType.INVESTIGATE, service_name="auth-service"),

            Action(action_type=ActionType.CLASSIFY, category=IncidentCategory.CONFIGURATION_ERROR),

        ]

        for action in good_actions:

            _, reward, done, _ = env.step(action)

            assert reward.cumulative >= prev - 0.001

            prev = reward.cumulative

            if done:

                break
