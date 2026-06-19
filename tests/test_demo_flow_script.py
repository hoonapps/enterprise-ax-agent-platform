from __future__ import annotations

import json
import subprocess
import sys
from uuid import uuid4


def test_demo_flow_script_outputs_operating_summary() -> None:
    tenant_id = f"demo-test-{uuid4()}"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_demo_flow.py",
            "--tenant-id",
            tenant_id,
        ],
        capture_output=True,
        check=True,
        text=True,
    )

    body = json.loads(result.stdout)

    assert body["tenant_id"] == tenant_id
    assert len(body["ingested_documents"]) >= 1
    assert body["primary_run"]["status"] == "succeeded"
    assert body["primary_run"]["citation_count"] >= 1
    assert body["primary_diagnostics"]["quality_score"] > 0
    assert body["primary_evidence"]["evidence_hash"]
    assert body["replay"]["replayed_run_id"]
    assert body["action_run"]["tool_decisions"][0]["decision"] == "approval_required"
    assert body["scenario_run"]["status"] == "passed"
    assert body["scenario_run"]["metrics"]["step_count"] == 3
    assert len(body["scenario_history"]) >= 1
    assert len(body["pending_approvals"]) >= 1
    assert body["operations"]["summary"]["agent_run_count"] >= 6
    assert body["operations"]["summary"]["pending_approval_count"] >= 1
    assert body["operations"]["slo"]["run_count"] >= 6
    assert body["http_entrypoints"]["run_export"] == "GET /v1/agents/runs/export"
