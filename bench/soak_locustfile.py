from __future__ import annotations

from locust import HttpUser, between, task


class WorkUser(HttpUser):
    wait_time = between(0.0, 0.0)

    @task
    def work(self) -> None:
        self.client.get("/work?n=2000", name="/work")
