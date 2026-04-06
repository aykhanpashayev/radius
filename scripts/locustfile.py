"""
Locust load test scenario for the Radius REST API.

Simulates a mix of dashboard user activity:
  - 60% read identities / scores (most common dashboard view)
  - 20% read incidents (analyst workflow)
  - 10% read audit log (compliance review)
  - 10% read events / trust relationships (investigation workflow)

All requests use a pre-obtained Cognito JWT passed via the LOAD_TEST_JWT
environment variable. The API base URL comes from LOAD_TEST_API_URL.

Set these before running:
    export LOAD_TEST_JWT="eyJraWQ..."
    export LOAD_TEST_API_URL="https://abc123.execute-api.us-east-1.amazonaws.com/prod"
    locust -f scripts/locustfile.py --headless -u 20 -r 2 -t 5m
"""

import os
from locust import HttpUser, task, between, events


API_URL = os.environ.get("LOAD_TEST_API_URL", "")
JWT     = os.environ.get("LOAD_TEST_JWT", "")


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    if not API_URL:
        raise SystemExit("ERROR: Set LOAD_TEST_API_URL before running the load test.")
    if not JWT:
        raise SystemExit("ERROR: Set LOAD_TEST_JWT before running the load test.")


class RadiusDashboardUser(HttpUser):
    """Simulates a security analyst using the Radius dashboard."""

    # Wait 1–5 seconds between requests (think time)
    wait_time = between(1, 5)

    host = API_URL

    @property
    def _auth_headers(self):
        return {"Authorization": f"Bearer {JWT}"}

    # ------------------------------------------------------------------
    # High-frequency: identity and score reads (dashboard home page)
    # ------------------------------------------------------------------

    @task(4)
    def list_identities(self):
        self.client.get("/identities", headers=self._auth_headers, name="/identities")

    @task(4)
    def list_scores(self):
        self.client.get("/scores", headers=self._auth_headers, name="/scores")

    # ------------------------------------------------------------------
    # Medium-frequency: incident list (analyst alert queue)
    # ------------------------------------------------------------------

    @task(2)
    def list_incidents(self):
        self.client.get("/incidents", headers=self._auth_headers, name="/incidents")

    @task(1)
    def list_incidents_open(self):
        self.client.get(
            "/incidents?status=open",
            headers=self._auth_headers,
            name="/incidents?status=open",
        )

    # ------------------------------------------------------------------
    # Low-frequency: event history, trust relationships, audit log
    # ------------------------------------------------------------------

    @task(1)
    def list_events(self):
        self.client.get("/events", headers=self._auth_headers, name="/events")

    @task(1)
    def list_trust_relationships(self):
        self.client.get(
            "/trust-relationships",
            headers=self._auth_headers,
            name="/trust-relationships",
        )

    @task(1)
    def get_remediation_config(self):
        self.client.get(
            "/remediation/config",
            headers=self._auth_headers,
            name="/remediation/config",
        )

    @task(1)
    def list_remediation_audit(self):
        self.client.get(
            "/remediation/audit",
            headers=self._auth_headers,
            name="/remediation/audit",
        )
