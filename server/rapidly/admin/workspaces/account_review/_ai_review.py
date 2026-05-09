"""AI-review verdict rendering component for the admin workspace-review workflow.

Displays the AI validation verdict (PASS / FAIL / UNCERTAIN) along with
risk score, violated policy sections, assessment text, appeal status,
and action buttons when an appeal is pending.
"""

import contextlib
from collections.abc import Generator
from typing import Any

from tagflow import tag, text

from ...components import button
from ..forms import ApproveWorkspaceAppealForm

# ---------------------------------------------------------------------------
# Style look-up tables
# ---------------------------------------------------------------------------

_VERDICT_BADGE_STYLES: dict[str, str] = {
    "PASS": "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    "FAIL": "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    "UNCERTAIN": "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
}

_NO_REVIEW_BADGE = "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300"

_RISK_THRESHOLDS: list[tuple[float, str]] = [
    (0.3, "text-green-600"),
    (0.7, "text-yellow-600"),
]
_RISK_HIGH_COLOR = "text-red-600"
_RISK_FALLBACK_COLOR = "text-gray-600"

_APPEAL_BADGE_MAP: dict[str, tuple[str, str]] = {
    "approved": (
        "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
        "Approved",
    ),
    "rejected": (
        "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
        "Rejected",
    ),
}
_APPEAL_DEFAULT_BADGE = (
    "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    "Under Review",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_verdict(review: Any) -> str:
    """Normalise the verdict to a plain string."""
    raw = review.verdict
    return raw.value if hasattr(raw, "value") else str(raw)


def _risk_color(score: float) -> str:
    for threshold, color in _RISK_THRESHOLDS:
        if score < threshold:
            return color
    return _RISK_HIGH_COLOR


def _render_paragraphs(body: str) -> None:
    """Split *body* on double-newlines and render each as a ``<p>``."""
    parts = body.split("\n\n")
    for idx, paragraph in enumerate(parts):
        stripped = paragraph.strip()
        if stripped:
            cls = "mb-1" if idx < len(parts) - 1 else ""
            with tag.p(classes=cls):
                text(stripped)


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------


class AIReviewVerdict:
    """Component for displaying AI-generated workspace review assessment."""

    def __init__(
        self,
        review: Any = None,
        workspace: Any = None,
        request: Any = None,
    ) -> None:
        self.review = review
        self.workspace = workspace
        self.request = request

    # -- derived properties --

    @property
    def verdict_text(self) -> str:
        if not self.review:
            return "NOT REVIEWED"
        return _extract_verdict(self.review)

    @property
    def verdict_classes(self) -> str:
        if not self.review:
            return _NO_REVIEW_BADGE
        return _VERDICT_BADGE_STYLES.get(
            _extract_verdict(self.review), _NO_REVIEW_BADGE
        )

    @property
    def risk_score_color(self) -> str:
        if not self.review:
            return _RISK_FALLBACK_COLOR
        return _risk_color(self.review.risk_score)

    # -- private rendering helpers --

    @contextlib.contextmanager
    def _render_metric_row(
        self, label: str, value: str, highlight: bool = False, color_class: str = ""
    ) -> Generator[None]:
        base = "flex items-center justify-between py-2 px-3 rounded-lg"
        modifier = (
            " bg-blue-50 dark:bg-blue-900/20"
            if highlight
            else " hover:bg-gray-50 dark:hover:bg-gray-800"
        )
        with tag.div(classes=base + modifier):
            with tag.span(
                classes="text-sm font-medium text-gray-700 dark:text-gray-300"
            ):
                text(label)
            with tag.span(
                classes=f"text-sm font-semibold {color_class or 'text-gray-900 dark:text-gray-100'}"
            ):
                text(value)
        yield

    def _render_section_divider(self) -> Any:
        return tag.div(classes="mt-3 pt-3 border-t border-gray-200")

    def _render_section_heading(self, title: str) -> None:
        with tag.div(classes="mb-2"):
            with tag.span(
                classes="text-sm font-medium text-gray-700 dark:text-gray-300"
            ):
                text(title)

    def _render_text_block(self, body: str) -> None:
        with tag.div(
            classes="text-sm text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-800 p-2 rounded max-h-32 overflow-y-auto"
        ):
            _render_paragraphs(body)

    def _render_violations(self) -> None:
        with self._render_section_divider():
            self._render_section_heading("Violations")
            with tag.div(classes="space-y-1"):
                for section in self.review.violated_sections:
                    with tag.div(
                        classes="bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300 text-sm px-2 py-1 rounded"
                    ):
                        text(section)

    def _render_assessment(self) -> None:
        with self._render_section_divider():
            self._render_section_heading("Assessment")
            self._render_text_block(self.review.reason)

    def _render_appeal_section(self) -> None:
        with self._render_section_divider():
            self._render_section_heading("Appeal Status")

            # Resolve badge
            decision = getattr(self.review, "appeal_decision", None)
            if decision:
                badge_cls, status_label = _APPEAL_BADGE_MAP.get(
                    decision, _APPEAL_DEFAULT_BADGE
                )
            else:
                badge_cls, status_label = _APPEAL_DEFAULT_BADGE

            with tag.div(classes="mb-2"):
                with tag.span(classes=f"badge text-xs {badge_cls}"):
                    text(status_label)

            # Submission date
            with self._render_metric_row(
                "Submitted",
                self.review.appeal_submitted_at.strftime("%m/%d/%y %I:%M %p"),
            ):
                pass

            # Review date
            reviewed_at = getattr(self.review, "appeal_reviewed_at", None)
            if reviewed_at:
                with self._render_metric_row(
                    "Reviewed", reviewed_at.strftime("%m/%d/%y %I:%M %p")
                ):
                    pass

            # Appeal reason
            appeal_reason = getattr(self.review, "appeal_reason", None)
            if appeal_reason:
                with tag.div(classes="mt-2"):
                    self._render_section_heading("Appeal Reason")
                    self._render_text_block(appeal_reason)

            # Decision actions (pending appeals only)
            if self.workspace and self.request and decision is None:
                self._render_appeal_actions()

    def _render_appeal_actions(self) -> None:
        with self._render_section_divider():
            with tag.div(classes="text-center mb-3"):
                with tag.h4(
                    classes="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1"
                ):
                    text("Appeal Decision")
                with tag.p(classes="text-xs text-gray-600 dark:text-gray-400"):
                    text("Review the appeal and make a decision")

            with ApproveWorkspaceAppealForm.render(
                method="POST",
                action=str(self.request.url),
                classes="space-y-4",
            ):
                with tag.div(classes="flex gap-2 justify-center mt-4"):
                    with button(
                        name="action",
                        type="submit",
                        variant="primary",
                        value="approve_appeal",
                        size="sm",
                    ):
                        text("Approve Appeal")
                    with button(
                        name="action",
                        type="submit",
                        variant="error",
                        value="deny_appeal",
                        size="sm",
                    ):
                        text("Deny Appeal")

    def _render_timeout_indicator(self) -> None:
        with self._render_section_divider():
            with tag.div(
                classes="bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded p-2"
            ):
                with tag.div(classes="flex items-center gap-1"):
                    with tag.span(classes="text-yellow-600 text-sm"):
                        text("⚠️")
                    with tag.span(
                        classes="text-yellow-800 dark:text-yellow-300 text-sm font-medium"
                    ):
                        text("Timed Out")

    # -- public API --

    @contextlib.contextmanager
    def render(self) -> Generator[None]:
        """Render the AI review verdict component (compact version)."""
        with tag.div(classes="card-body"):
            with tag.h2(classes="card-title flex items-center gap-2"):
                text("AI Review")
                if self.review:
                    with tag.span(classes=f"badge text-xs {self.verdict_classes}"):
                        text(self.verdict_text)

            if not self.review:
                with tag.div(classes="text-center py-6"):
                    with tag.div(classes="text-gray-400 mb-2 text-2xl"):
                        text("🤖")
                    with tag.p(classes="text-gray-600 dark:text-gray-400 text-sm"):
                        text("AI review pending")
            else:
                # Metrics
                with tag.div(classes="space-y-2 mt-4"):
                    with self._render_metric_row(
                        "Risk Score",
                        f"{self.review.risk_score:.2f}",
                        highlight=(self.review.risk_score >= 0.7),
                        color_class=self.risk_score_color,
                    ):
                        pass
                    if self.review.validated_at:
                        with self._render_metric_row(
                            "Reviewed",
                            self.review.validated_at.strftime("%m/%d/%y"),
                        ):
                            pass

                # Optional sections
                if self.review.violated_sections:
                    self._render_violations()

                if self.review.reason:
                    self._render_assessment()

                if getattr(self.review, "appeal_submitted_at", None):
                    self._render_appeal_section()

                if self.review.timed_out:
                    self._render_timeout_indicator()

        yield
