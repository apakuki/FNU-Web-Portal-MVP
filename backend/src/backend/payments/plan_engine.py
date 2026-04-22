"""Payment plan engine — generates instalment schedules and reminder triggers.

A schedule is a list of instalments with due dates and amounts. The engine
splits the invoice balance evenly across N instalments, with the final one
absorbing any rounding remainder so the sum exactly matches the balance.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal, TypedDict

from pydantic import BaseModel, Field


class Instalment(TypedDict):
    sequence: int
    due_date: str  # ISO date
    amount_cents: int
    status: Literal["upcoming", "paid", "overdue"]


class PaymentPlanSchedule(BaseModel):
    invoice_id: str
    total_cents: int
    paid_cents: int = 0
    balance_cents: int
    instalments: list[Instalment] = Field(default_factory=list)
    reminder_days_before: list[int] = Field(default_factory=lambda: [3, 1])
    deregistration_warning_week: int = 4


def generate_plan_schedule(
    invoice_id: str,
    total_cents: int,
    paid_cents: int,
    num_instalments: int,
    first_due_date: date,
    interval_days: int = 30,
) -> PaymentPlanSchedule:
    """Generate an evenly-split instalment schedule for the outstanding balance.

    Rounding remainder is added to the final instalment so the sum always
    equals the outstanding balance.
    """
    if num_instalments <= 0:
        raise ValueError("num_instalments must be positive")
    balance = total_cents - paid_cents
    if balance <= 0:
        return PaymentPlanSchedule(
            invoice_id=invoice_id,
            total_cents=total_cents,
            paid_cents=paid_cents,
            balance_cents=0,
            instalments=[],
        )

    base = balance // num_instalments
    remainder = balance - base * num_instalments

    instalments: list[Instalment] = []
    for i in range(num_instalments):
        amount = base + (remainder if i == num_instalments - 1 else 0)
        due = first_due_date + timedelta(days=interval_days * i)
        instalments.append(
            Instalment(
                sequence=i + 1,
                due_date=due.isoformat(),
                amount_cents=amount,
                status="upcoming",
            )
        )

    return PaymentPlanSchedule(
        invoice_id=invoice_id,
        total_cents=total_cents,
        paid_cents=paid_cents,
        balance_cents=balance,
        instalments=instalments,
    )


def apply_payment_to_schedule(
    schedule: PaymentPlanSchedule,
    amount_cents: int,
) -> PaymentPlanSchedule:
    """Mark instalments as paid, earliest first, until the payment is exhausted."""
    remaining = amount_cents
    new_instalments: list[Instalment] = []
    for inst in schedule.instalments:
        if remaining >= inst["amount_cents"] and inst["status"] == "upcoming":
            remaining -= inst["amount_cents"]
            new_instalments.append({**inst, "status": "paid"})
        else:
            new_instalments.append(inst)
    return schedule.model_copy(update={
        "instalments": new_instalments,
        "paid_cents": schedule.paid_cents + (amount_cents - remaining),
        "balance_cents": schedule.balance_cents - (amount_cents - remaining),
    })


def mark_overdue(schedule: PaymentPlanSchedule, today: date) -> PaymentPlanSchedule:
    """Return a new schedule with past-due instalments marked overdue."""
    new_instalments: list[Instalment] = []
    for inst in schedule.instalments:
        due = date.fromisoformat(inst["due_date"])
        if inst["status"] == "upcoming" and due < today:
            new_instalments.append({**inst, "status": "overdue"})
        else:
            new_instalments.append(inst)
    return schedule.model_copy(update={"instalments": new_instalments})


def get_due_reminders(schedule: PaymentPlanSchedule, today: date) -> list[Instalment]:
    """Return instalments whose due date falls within reminder_days_before."""
    reminders: list[Instalment] = []
    for inst in schedule.instalments:
        if inst["status"] != "upcoming":
            continue
        due = date.fromisoformat(inst["due_date"])
        days_until = (due - today).days
        if days_until in schedule.reminder_days_before:
            reminders.append(inst)
    return reminders
