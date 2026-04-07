import timeit
import time
from environment.env import IncidentResponseEnv
from environment.models import Action, ActionType, RemediationAction

def benchmark():
    env = IncidentResponseEnv()
    env.reset("root_cause_analysis", 0)

    # We need to investigate first so remediation isn't rejected early
    env._state.observation.investigations_done.append("auth-service")

    action = Action(
        action_type=ActionType.REMEDIATE,
        service_name="auth-service",
        remediation_action=RemediationAction.UPDATE_CONFIG,
    )

    gt = env._state.ground_truth
    obs = env._state.observation

    def run_one():
        # Clear remediation applied so it evaluates the full path
        obs.remediation_applied.clear()
        env._handle_remediate(action, gt, obs)

    # Warmup
    for _ in range(100):
        run_one()

    # Benchmark
    number = 100_000
    timer = timeit.Timer(run_one)
    elapsed = timer.timeit(number=number)

    print(f"Elapsed time for {number} calls: {elapsed:.4f} seconds")

if __name__ == "__main__":
    benchmark()