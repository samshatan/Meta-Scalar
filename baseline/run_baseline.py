"""
Baseline inference script for the Incident Response OpenEnv environment.

Runs a GPT-4o-mini agent against all three tasks using a simple ReAct loop.
Scores are printed to stdout as JSON when called with --output json.

Usage
-----
  export OPENAI_API_KEY=sk-...
  python baseline/run_baseline.py
  python baseline/run_baseline.py --output json
  python baseline/run_baseline.py --model gpt-4o --task alert_classification
"""



import argparse

import json

import os

import sys

import time

from typing import Dict, Any, List, Optional



import requests



                                                              

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))



from environment.env import IncidentResponseEnv

from environment.models import Action, ActionType, IncidentCategory, RemediationAction

from environment.tasks import TASKS, GRADERS



try:

    from openai import OpenAI

except ImportError:

    OpenAI = None                                 





                                                                               

               

                                                                               



SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) acting as an AI agent
inside an incident response simulation.

Your goal is to diagnose and resolve production incidents as efficiently as possible.

## Available Actions (output as JSON)

You MUST respond with a single JSON object matching one of these schemas:

1. Classify the incident:
   {"action_type": "classify", "category": "<category>"}
   Categories: database_connection | memory_leak | network_partition |
               dependency_failure | resource_exhaustion | configuration_error

2. Investigate a service (fetch its logs):
   {"action_type": "investigate", "service_name": "<name>"}

3. Apply a remediation:
   {"action_type": "remediate",
    "service_name": "<name>",
    "remediation_action": "<action>"}
   Remediations: restart_service | scale_up | flush_cache | rollback_deployment |
                 update_config | kill_long_running_query | increase_connection_pool |
                 restore_network_policy | clear_disk_space | rotate_credentials

4. Resolve the incident:
   {"action_type": "resolve", "resolution_summary": "<summary>"}

5. Escalate (last resort):
   {"action_type": "escalate", "escalation_reason": "<reason>"}

## Strategy
- Start by reading the alerts and service health carefully.
- Investigate suspicious services before classifying.
- Look for the ROOT CAUSE service, not just the symptom.
- Apply the most targeted remediation for the root cause.
- Resolve with a clear summary mentioning what failed and what was fixed.
- Do NOT re-investigate a service you have already investigated.
- Do NOT apply the same remediation twice.

Respond ONLY with valid JSON. No explanation, no markdown.
"""





                                                                               

                

                                                                               



class BaselineAgent:

    def __init__(self, model: str = "gpt-4o-mini"):

        api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key:

            raise RuntimeError("OPENAI_API_KEY environment variable not set.")

        if OpenAI is None:

            raise RuntimeError("openai package not installed. Run: pip install openai")

        self.client = OpenAI(api_key=api_key)

        self.model = model



    def pick_action(self, observation_text: str, history: List[Dict]) -> Dict[str, Any]:

        """Ask the LLM to pick the next action given the current observation."""

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]



        for h in history:

            messages.append({"role": "user",    "content": h["obs"]})



                                                                                                      

            content = h["action_json"] if "action_json" in h else json.dumps(h["action"])

            messages.append({"role": "assistant", "content": content})



        messages.append({"role": "user", "content": observation_text})



        response = self.client.chat.completions.create(

            model=self.model,

            messages=messages,

            temperature=0.0,

            max_tokens=300,

            response_format={"type": "json_object"},

        )

        return json.loads(response.choices[0].message.content)





def obs_to_text(obs_dict: Dict[str, Any]) -> str:

    """Convert an observation dict into a human-readable prompt string."""

    lines = [

        f"== INCIDENT: {obs_dict['incident_id']} ==",

        f"Task: {obs_dict['task_description']}",

        f"Step: {obs_dict['step']}/{obs_dict['max_steps']}",

        f"Message: {obs_dict['message']}",

        "",

        "=== ALERTS ===",

    ]

    for a in obs_dict.get("alerts", []):

        lines.append(f"  [{a['severity']}] {a['service']}: {a['message']}")

        if a.get("metrics"):

            lines.append(f"    Metrics: {a['metrics']}")



    lines.append("\n=== SERVICE HEALTH ===")

    for s in obs_dict.get("service_health", []):

        lines.append(

            f"  {s['name']}: {s['status']} | err_rate={s['error_rate']:.0%} "

            f"| p99={s['p99_latency_ms']:.0f}ms | pods={s['pod_count']}"

        )



    if obs_dict.get("visible_logs"):

        lines.append("\n=== RECENT LOGS ===")

        for l in obs_dict["visible_logs"][-20:]:                     

            lines.append(f"  [{l['timestamp']}] {l['service']} {l['level']}: {l['message']}")



    lines.append(f"\n=== AGENT PROGRESS ===")

    lines.append(f"  Classified: {obs_dict.get('classified')} ({obs_dict.get('classification', '-')})")

    lines.append(f"  Investigated: {obs_dict.get('investigations_done', [])}")

    lines.append(f"  Remediations: {obs_dict.get('remediation_applied', [])}")

    lines.append(f"\nAvailable services to investigate: {obs_dict.get('available_services', [])}")



    return "\n".join(lines)





def run_episode(

    env: IncidentResponseEnv,

    agent: Optional[BaselineAgent],

    task_id: str,

    scenario_index: int = 0,

    verbose: bool = True,

) -> Dict[str, Any]:

    """Run one episode and return the grader result."""

    obs = env.reset(task_id=task_id, scenario_index=scenario_index)

    obs_dict = obs.model_dump()



    history = []

    done = False

    cumulative_reward = 0.0



    if verbose:

        print(f"\n{'='*60}")

        print(f"Task: {task_id} | Scenario: {scenario_index}")

        print(f"Incident: {obs.incident_id}")

        print(f"{'='*60}")



    step_num = 0

    while not done:

        step_num += 1

        obs_text = obs_to_text(obs_dict)



        if agent is not None:

            try:

                action_dict = agent.pick_action(obs_text, history)

            except Exception as e:

                if verbose:

                    print(f"  [LLM error] {e} — resolving with fallback")

                action_dict = {

                    "action_type": "resolve",

                    "resolution_summary": "Unable to complete investigation due to API error."

                }

        else:

                                                             

            action_dict = _heuristic_action(obs_dict, task_id, step_num)



        try:

            action = Action(**action_dict)

        except Exception as e:

            if verbose:

                print(f"  [Invalid action] {e} — resolving")

            action = Action(

                action_type=ActionType.RESOLVE,

                resolution_summary="Agent produced invalid action — forced resolution."

            )



        if verbose:

            print(f"  Step {step_num}: {action.action_type.value}", end="")

            extra = action.category or action.service_name or action.remediation_action

            if extra:

                val = extra.value if hasattr(extra, "value") else extra

                print(f"({val})", end="")

            print()



        obs, reward, done, info = env.step(action)

        obs_dict = obs.model_dump()

        cumulative_reward = reward.cumulative



        history.append({"obs": obs_text, "action": action_dict, "action_json": json.dumps(action_dict)})



        if verbose:

            print(f"    Reward: {reward.score:+.3f} | Cumulative: {reward.cumulative:.3f}")

            print(f"    {reward.feedback}")



        if done:

            break

        time.sleep(0.1)                    



                        

    grader_result = env.grade()

    grader_result["task_id"] = task_id

    grader_result["scenario_index"] = scenario_index



    if verbose:

        print(f"\n── Grader Score: {grader_result['score']:.4f} ──")

        print(f"   Breakdown: {grader_result['breakdown']}")

        print(f"   Feedback:  {grader_result['feedback']}")



    return grader_result





def _heuristic_action(obs_dict: Dict, task_id: str, step: int) -> Dict:

    """Simple heuristic agent for smoke testing without an API key."""

    investigated = obs_dict.get("investigations_done", [])

    available = obs_dict.get("available_services", [])

    classified = obs_dict.get("classified", False)

    remediation_applied = obs_dict.get("remediation_applied", [])



                           

    for svc in available:

        if svc not in investigated:

            return {"action_type": "investigate", "service_name": svc}



                      

    if not classified:

                                         

        logs = obs_dict.get("visible_logs", [])

        log_text = " ".join(l["message"].lower() for l in logs)

        if "connection" in log_text or "pool" in log_text:

            cat = "database_connection"

        elif "memory" in log_text or "oom" in log_text or "heap" in log_text:

            cat = "memory_leak"

        elif "disk" in log_text or "exhausted" in log_text:

            cat = "resource_exhaustion"

        elif "config" in log_text or "permission" in log_text or "vault" in log_text:

            cat = "configuration_error"

        elif "network" in log_text or "partition" in log_text:

            cat = "network_partition"

        else:

            cat = "dependency_failure"

        return {"action_type": "classify", "category": cat}



                                                     

    if investigated and not remediation_applied:

        svc = investigated[0]

        logs = obs_dict.get("visible_logs", [])

        log_text = " ".join(l["message"].lower() for l in logs)

        if "connection pool" in log_text or "max_connections" in log_text:

            rem = "increase_connection_pool"

        elif "disk" in log_text or "space" in log_text:

            rem = "clear_disk_space"

        elif "config" in log_text or "vault" in log_text:

            rem = "update_config"

        elif "oom" in log_text or "memory" in log_text:

            rem = "restart_service"

        elif "cluster" in log_text:

            rem = "restart_service"

        else:

            rem = "restart_service"

        return {"action_type": "remediate", "service_name": svc, "remediation_action": rem}



                    

    return {

        "action_type": "resolve",

        "resolution_summary": (

            f"Investigated {investigated}. "

            f"Identified and applied remediation. Incident resolved."

        )

    }





                                                                               

      

                                                                               



def main():

    parser = argparse.ArgumentParser(description="Baseline inference for Incident Response OpenEnv")

    parser.add_argument("--model",  default="gpt-4o-mini", help="OpenAI model to use")

    parser.add_argument("--task",   default=None,           help="Run only this task")

    parser.add_argument("--output", default="human",        choices=["human", "json"])

    parser.add_argument("--heuristic", action="store_true", help="Use heuristic agent (no API key needed)")

    args = parser.parse_args()



    verbose = args.output == "human"



                 

    if args.heuristic or not os.environ.get("OPENAI_API_KEY"):

        agent = None

        if verbose:

            print("[INFO] No OPENAI_API_KEY found — using heuristic baseline agent.")

    else:

        agent = BaselineAgent(model=args.model)



    env = IncidentResponseEnv()

    task_ids = [args.task] if args.task else list(TASKS.keys())



    all_results = {}

    for task_id in task_ids:

        task = TASKS[task_id]

        scenario_results = []

        for idx in range(len(task["scenarios"])):

            result = run_episode(env, agent, task_id, scenario_index=idx, verbose=verbose)

            scenario_results.append(result)

            time.sleep(0.5)



        avg_score = sum(r["score"] for r in scenario_results) / len(scenario_results)

        all_results[task_id] = {

            "difficulty":      task["difficulty"],

            "avg_score":       round(avg_score, 4),

            "scenario_scores": [r["score"] for r in scenario_results],

            "breakdowns":      [r["breakdown"] for r in scenario_results],

        }



    if verbose:

        print("\n" + "="*60)

        print("BASELINE SUMMARY")

        print("="*60)

        for t, r in all_results.items():

            print(f"  {t} ({r['difficulty']}): {r['avg_score']:.4f}")

        overall = sum(r["avg_score"] for r in all_results.values()) / len(all_results)

        print(f"\n  Overall average: {overall:.4f}")

    else:

        print(json.dumps(all_results, indent=2))





if __name__ == "__main__":

    main()
