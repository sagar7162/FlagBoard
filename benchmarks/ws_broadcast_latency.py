"""
Measures how long it takes a flag toggle to reach every connected dashboard
WebSocket client.

Usage:
    python benchmarks/ws_broadcast_latency.py [N_CLIENTS]
    python benchmarks/ws_broadcast_latency.py 50
"""

import asyncio
import sys
import time

import uuid
import httpx
import websockets

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

def seed(client: httpx.Client) -> tuple[str, str, str]:
    """Create one org + member user + flag. Returns (org_id, token, flag_id)."""

    run_id = uuid.uuid4().hex[:8]

    # Create a unique user for every benchmark run
    signup = client.post(
        "/auth/signup",
        json={
            "email": f"wsbench-{run_id}@example.com",
            "password": "correct-horse-battery-staple",
        },
    )

    if signup.status_code not in (200, 201):
        raise RuntimeError(
            f"Signup failed: HTTP {signup.status_code}: {signup.text}"
        )

    token = signup.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    org_response = client.post(
        "/orgs",
        json={"name": f"WS Bench Org {run_id}"},
        headers=headers,
    )

    if org_response.status_code not in (200, 201):
        raise RuntimeError(
            f"Organization creation failed: "
            f"HTTP {org_response.status_code}: {org_response.text}"
        )

    org = org_response.json()

    project_response = client.post(
        f"/orgs/{org['id']}/projects",
        json={
            "name": f"WS Bench Project {run_id}",
            "key": f"wsbench-{run_id}",
        },
        headers=headers,
    )

    if project_response.status_code not in (200, 201):
        raise RuntimeError(
            f"Project creation failed: "
            f"HTTP {project_response.status_code}: {project_response.text}"
        )

    project = project_response.json()

    flag_response = client.post(
        f"/projects/{project['id']}/flags",
        json={
            "key": f"ws_bench_flag_{run_id}",
            "name": "WS Bench Flag",
        },
        headers=headers,
    )

    if flag_response.status_code not in (200, 201):
        raise RuntimeError(
            f"Flag creation failed: "
            f"HTTP {flag_response.status_code}: {flag_response.text}"
        )

    flag = flag_response.json()

    return org["id"], token, flag["id"]

async def open_clients(org_id: str, token: str, n: int):
    """Open n concurrent authenticated dashboard sockets for the org."""

    uri = f"{WS_URL}/ws/orgs/{org_id}?token={token}"
    return await asyncio.gather(*(websockets.connect(uri) for _ in range(n)))


async def wait_for_broadcast(sockets, timeout: float = 5.0):
    """Wait for every socket to receive one message; return receipt timestamps."""

    async def wait_one(ws):
        await ws.recv()
        return time.perf_counter()

    return await asyncio.gather(*(asyncio.wait_for(wait_one(ws), timeout) for ws in sockets))


async def main(n: int) -> None:
    with httpx.Client(base_url=BASE_URL) as client:
        org_id, token, flag_id = seed(client)

        sockets = await open_clients(org_id, token, n)
        try:
            # Give the server a beat to finish registering every connection
            # before firing the toggle, so we're not measuring connect time.
            await asyncio.sleep(0.2)

            toggle_start = time.perf_counter()
            recv_task = asyncio.create_task(wait_for_broadcast(sockets))
            # Fire the toggle from a worker thread so the sync httpx call
            # doesn't block the event loop that's timing the receives.
            await asyncio.to_thread(
                client.patch,
                f"/flags/{flag_id}/environments/production/toggle",
                json={"enabled": True},
                headers={"Authorization": f"Bearer {token}"},
            )
            recv_times = await recv_task
            latencies_ms = sorted((t - toggle_start) * 1000 for t in recv_times)
        finally:
            await asyncio.gather(*(ws.close() for ws in sockets), return_exceptions=True)

    print(f"Connected clients: {n}")
    print(f"Fastest delivery: {latencies_ms[0]:.1f} ms")
    print(f"Median delivery: {latencies_ms[len(latencies_ms) // 2]:.1f} ms")
    print(f"Slowest delivery (all {n} clients received): {latencies_ms[-1]:.1f} ms")


if __name__ == "__main__":
    n_clients = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    asyncio.run(main(n_clients))