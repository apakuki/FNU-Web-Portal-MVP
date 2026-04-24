"""Locust load-test scenarios — exercises the student happy-path + public pages.

Baseline mix (approximates real usage):
- 40% public landing
- 20% login + auth/me cycle
- 25% authenticated dashboard loads
- 15% course list / timetable fetches

Run via ./scripts/loadtest.sh (wraps locust --headless).
"""

from __future__ import annotations

import random

from locust import HttpUser, between, task

STUDENT_EMAIL = "student@fnu.ac.fj"
STUDENT_PASSWORD = "student123"


class AnonymousUser(HttpUser):
    wait_time = between(0.5, 2.0)
    weight = 1

    @task(4)
    def landing(self) -> None:
        self.client.get("/", name="public-landing")

    @task(1)
    def apply(self) -> None:
        self.client.get("/apply", name="public-apply")

    @task(1)
    def health(self) -> None:
        self.client.get("/api/health", name="api-health")


class AuthenticatedStudentUser(HttpUser):
    wait_time = between(1.0, 3.0)
    weight = 2
    token: str | None = None

    def on_start(self) -> None:
        resp = self.client.post(
            "/api/auth/login",
            json={"email": STUDENT_EMAIL, "password": STUDENT_PASSWORD},
            name="auth-login",
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token")

    def _headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def me(self) -> None:
        self.client.get("/api/auth/me", headers=self._headers(), name="auth-me")

    @task(2)
    def timetable(self) -> None:
        self.client.get("/api/timetable", headers=self._headers(), name="timetable")

    @task(2)
    def my_courses(self) -> None:
        self.client.get("/api/my-courses", headers=self._headers(), name="my-courses")

    @task(1)
    def programme(self) -> None:
        self.client.get("/api/programme", headers=self._headers(), name="programme")

    @task(1)
    def chat(self) -> None:
        messages = [
            "What are the entry requirements for Bachelor of Nursing?",
            "When is the enrolment deadline?",
            "How do I pay my fees?",
        ]
        self.client.post(
            "/api/chat",
            json={"message": random.choice(messages)},
            headers=self._headers(),
            name="chat",
        )
