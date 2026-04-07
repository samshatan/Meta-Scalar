"""
IncidentResponseEnv — core environment implementing the OpenEnv interface.

Methods
-------
reset(task_id, scenario_index) → Observation
step(action)                   → (Observation, Reward, done, info)
state()                        → EnvironmentState
grade()                        → grader result dict
"""

import copy

import uuid

from typing import Optional, Tuple, Dict, Any

from .models import (

    Action, ActionType, Observation, Reward, EnvironmentState,

    ServiceHealth, LogEntry, RemediationAction

)

from .tasks import TASKS, GRADERS

STEP_OVER_PENALTY = 0.02

class IncidentResponseEnv:

    """
    A simulation of a software-incident triage session.

    Episode lifecycle
    -----------------
    1. reset(task_id)  — start a fresh episode, returns initial Observation
    2. step(action)    — agent takes an action, receives Observation + Reward
       … repeat until done == True …
    3. grade()         — compute final grader score for the episode
    """

    def __init__(self):

        self._state: Optional[EnvironmentState] = None

    def reset(

        self,

        task_id: str = "alert_classification",

        scenario_index: int = 0,

    ) -> Observation:

        if task_id not in TASKS:

            raise ValueError(f"Unknown task_id '{task_id}'. Available: {list(TASKS)}")

        task = TASKS[task_id]

        scenarios = task["scenarios"]

        if scenario_index < 0 or scenario_index >= len(scenarios):

            raise ValueError(f"Invalid scenario_index {scenario_index} for task '{task_id}'. Must be between 0 and {len(scenarios) - 1}.")

        scenario = scenarios[scenario_index]

        obs = Observation(

            incident_id=scenario["incident_id"],

            task_id=task_id,

            task_description=task["description"],

            alerts=scenario["alerts"],

            available_services=scenario["available_services"],

            service_health=scenario["service_health"],

            visible_logs=[],

            classified=False,

            classification=None,

            investigations_done=[],

            remediation_applied=[],

            resolved=False,

            step=0,

            max_steps=scenario.get("max_steps", 12),

            message=(

                f"Incident {scenario['incident_id']} opened. "

                f"{len(scenario['alerts'])} alert(s) firing. "

                "Begin your investigation."

            ),

        )

        self._state = EnvironmentState(

            observation=obs,

            ground_truth=scenario["ground_truth"],

            episode_done=False,

            cumulative_score=0.0,

            step_history=[],

        )

        gt = scenario["ground_truth"]

        gt_rems = gt.get("correct_remediations", [])

        gt_rem_single = gt.get("correct_remediation", None)

        if gt_rem_single:

            gt_rems = gt_rems + [gt_rem_single]

        correct_remediation_values = frozenset(r.value for r in gt_rems)

        self._state.__dict__["_scenario"] = scenario

        self._state.__dict__["_task_id"] = task_id

        self._state.__dict__["_correct_remediation_values"] = correct_remediation_values

        return obs

    def step(self, action: Action) -> Tuple[Observation, Reward, bool, Dict[str, Any]]:

        if self._state is None:

            raise RuntimeError("Call reset() before step()")

        if self._state.episode_done:

            raise RuntimeError("Episode is done. Call reset() to start a new one.")

        obs = self._state.observation

        gt = self._state.ground_truth

        scenario = self._state.__dict__["_scenario"]

        log_map = scenario.get("log_map", {})

        obs.step += 1

        step_score = 0.0

        feedback_parts = []

        if action.action_type == ActionType.CLASSIFY:

            result = self._handle_classify(action, gt, obs)

            step_score = result["score"]

            feedback_parts.append(result["msg"])

        elif action.action_type == ActionType.INVESTIGATE:

            result = self._handle_investigate(action, log_map, obs)

            step_score = result["score"]

            feedback_parts.append(result["msg"])

        elif action.action_type == ActionType.REMEDIATE:

            result = self._handle_remediate(action, gt, obs)

            step_score = result["score"]

            feedback_parts.append(result["msg"])

        elif action.action_type == ActionType.ESCALATE:

            step_score = 0.05

            feedback_parts.append("Escalated to human team. Episode ends.")

            obs.resolved = True

            self._state.episode_done = True

        elif action.action_type == ActionType.RESOLVE:

            result = self._handle_resolve(action, gt, obs)

            step_score = result["score"]

            feedback_parts.append(result["msg"])

            obs.resolved = True

            self._state.episode_done = True

        else:

            feedback_parts.append(f"Unknown action type: {action.action_type}")

        over_budget = max(0, obs.step - obs.max_steps)

        if over_budget > 0:

            penalty = STEP_OVER_PENALTY * over_budget

            step_score = max(0.0, step_score - penalty)

            feedback_parts.append(f"[Over budget by {over_budget} step(s), penalty -{penalty:.2f}]")

        if obs.step >= obs.max_steps and not self._state.episode_done:

            self._state.episode_done = True

            obs.message = (

                " | ".join(feedback_parts) +

                " | Step budget exhausted — episode ending."

            )

        else:

            obs.message = " | ".join(feedback_parts)

        self._state.cumulative_score = max(

            -1.0,

            min(1.0, self._state.cumulative_score + step_score)

        )

        self._state.step_history.append({

            "step": obs.step,

            "action": action.model_dump(),

            "step_score": step_score,

            "cumulative": self._state.cumulative_score,

        })

        reward = Reward(

            score=round(step_score, 4),

            cumulative=round(self._state.cumulative_score, 4),

            breakdown={"raw_step_score": step_score},

            feedback=obs.message,

        )

        info = {

            "step": obs.step,

            "max_steps": obs.max_steps,

            "episode_done": self._state.episode_done,

        }

        return obs, reward, self._state.episode_done, info

    def state(self) -> EnvironmentState:

        if self._state is None:

            raise RuntimeError("Call reset() before state()")

        return self._state

    def grade(self) -> Dict[str, Any]:

        if self._state is None:

            raise RuntimeError("Call reset() before grade()")

        task_id = self._state.__dict__["_task_id"]

        grader = GRADERS[task_id]

        obs_dict = self._state.observation.model_dump()

        grade_state = {

            "ground_truth": self._state.ground_truth,

            "observation": obs_dict,

            "step_history": self._state.step_history,

            "max_steps": obs_dict["max_steps"],

        }

        return grader(grade_state)

    def _handle_classify(self, action, gt, obs):

        if not action.category:

            return {"score": 0.0, "msg": "classify action requires 'category' field."}

        obs.classified = True

        obs.classification = action.category.value

        correct = action.category.value == gt["category"].value

        score = 0.30 if correct else 0.0

        msg = (

            f"Classified as '{action.category.value}'. "

            f"{'Correct ✓' if correct else 'Incorrect ✗ — keep investigating.'}"

        )

        return {"score": score, "msg": msg}

    def _handle_investigate(self, action, log_map, obs):

        if not action.service_name:

            return {"score": 0.0, "msg": "investigate action requires 'service_name' field."}

        svc = action.service_name

        if svc not in obs.available_services:

            return {

                "score": 0.0,

                "msg": f"Service '{svc}' not found. Available: {obs.available_services}"

            }

        if svc in obs.investigations_done:

            return {"score": -0.05, "msg": f"Already investigated '{svc}' — no new information."}

        obs.investigations_done.append(svc)

        new_logs = log_map.get(svc, [])

        obs.visible_logs = obs.visible_logs + new_logs

        score = 0.10

        has_errors = any(l.level == "ERROR" for l in new_logs)

        if has_errors:

            score = 0.15

        msg = f"Investigated '{svc}' — {len(new_logs)} log entries retrieved."

        return {"score": score, "msg": msg}

    def _handle_remediate(self, action, gt, obs):

        if not action.service_name or not action.remediation_action:

            return {

                "score": 0.0,

                "msg": "remediate requires 'service_name' and 'remediation_action'."

            }

        if action.service_name not in obs.investigations_done:

            return {

                "score": 0.0,

                "msg": f"Cannot remediate '{action.service_name}' without investigating it first."

            }

        rem_val = action.remediation_action.value

        if rem_val in obs.remediation_applied:

            return {"score": -0.05, "msg": f"Remediation '{rem_val}' already applied."}

        obs.remediation_applied.append(rem_val)

        correct_values = self._state.__dict__["_correct_remediation_values"]

        correct = rem_val in correct_values

        score = 0.20 if correct else -0.10

        msg = (

            f"Remediation '{rem_val}' applied to '{action.service_name}'. "

            f"{'Effective ✓' if correct else 'Ineffective — this may not address the root cause.'}"

        )

        return {"score": score, "msg": msg}

    def _handle_resolve(self, action, gt, obs):

        if not action.resolution_summary:

            return {

                "score": 0.0,

                "msg": "resolve action requires 'resolution_summary'.",

            }

        summary = action.resolution_summary

        obs.resolution_summary = summary

        score = 0.10

        keywords = gt.get("resolution_keywords", [])

        if keywords:

            lower_sum = summary.lower()

            hits = sum(1 for k in keywords if k in lower_sum)

            score += 0.15 * (hits / len(keywords))

        msg = (

            f"Incident resolved. Summary: '{summary[:120]}...'"

            if len(summary) > 120

            else f"Incident resolved. Summary: '{summary}'"

        )

        return {"score": score, "msg": msg}
