"""Template rendering + PII safety for the notification service."""

from __future__ import annotations

from src.backend.services import notification_service


def test_render_template_substitutes_identifiers():
    out = notification_service.render_template(
        "Hi {full_name}, invoice {invoice_id} is due on {due_date}.",
        {"full_name": "Mere T.", "invoice_id": "INV-42", "due_date": "2026-05-01"},
    )
    assert out == "Hi Mere T., invoice INV-42 is due on 2026-05-01."


def test_render_template_missing_variable_yields_empty():
    """A renamed/missing variable should not crash dispatch."""
    out = notification_service.render_template(
        "Hi {full_name}. Balance: FJ${amount_fjd}.",
        {"full_name": "Apisai"},
    )
    assert out == "Hi Apisai. Balance: FJ$."


def test_render_template_strips_control_chars_and_crlf():
    """Header injection via CR/LF in a variable must be blocked."""
    out = notification_service.render_template(
        "Subject: {subject}",
        {"subject": "normal\r\nBcc: evil@example.com"},
    )
    # \r and other control chars are stripped; \n is preserved
    assert "\r" not in out
    assert "Bcc: evil@example.com" in out  # but it ends up on a new line, not a header


def test_render_template_truncates_extremely_long_values():
    variables = {"body": "x" * 10_000}
    out = notification_service.render_template("{body}", variables)
    assert len(out) == 500
    assert out.endswith("...")


def test_render_template_ignores_non_identifier_keys():
    """Non-identifier keys (dots, dashes) must be skipped, not crash."""
    out = notification_service.render_template(
        "Hi {name}",
        {"name": "ok", "user.email": "leak@example.com"},
    )
    assert out == "Hi ok"


def test_render_template_survives_malformed_braces():
    """A stray unmatched brace returns the literal template rather than raising."""
    out = notification_service.render_template("Hello {name", {"name": "Mere"})
    # format_map raises ValueError on unmatched brace — fallback returns literal
    assert out == "Hello {name"
