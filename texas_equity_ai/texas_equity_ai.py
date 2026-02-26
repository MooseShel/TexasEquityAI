"""
Main application entry point — routing, layout, and app creation.
"""
import reflex as rx
from texas_equity_ai.state import AppState
from texas_equity_ai.styles import base_page_style, FONT_FAMILY, GOOGLE_FONT_URL
from texas_equity_ai.components.sidebar import sidebar
from texas_equity_ai.pages.dashboard import dashboard
from texas_equity_ai.pages.report import report_page, ReportState


def layout(page_content: rx.Component) -> rx.Component:
    """Main layout with collapsible sidebar + content area."""
    return rx.box(
        # Google Fonts
        rx.el.link(
            rel="stylesheet",
            href=GOOGLE_FONT_URL,
        ),
        sidebar(),
        rx.box(
            page_content,
            margin_left=rx.cond(AppState.sidebar_collapsed, "64px", "300px"),
            padding="32px",
            flex="1",
            max_width="1200px",
            width="100%",
            transition="margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
        ),
        **base_page_style,
    )


def index() -> rx.Component:
    """Home page — the main dashboard."""
    return layout(dashboard())


def report_view() -> rx.Component:
    """Report viewer page — no sidebar for clean mobile view."""
    return report_page()


# ── Create app ─────────────────────────────────────────────────────
app = rx.App(
    theme=rx.theme(
        appearance="dark",
        has_background=True,
        radius="medium",
        accent_color="blue",
    ),
    style={
        "font_family": FONT_FAMILY,
    },
    head_components=[
        rx.el.link(rel="stylesheet", href=GOOGLE_FONT_URL),
        rx.el.meta(name="description", content="Texas Equity AI — AI-powered property tax protest automation for Texas homeowners"),
        rx.el.meta(name="viewport", content="width=device-width, initial-scale=1"),
    ],
)

app.add_page(index, route="/", title="Texas Equity AI — Property Tax Protest")
app.add_page(report_view, route="/report/[account]", title="Property Report | Texas Equity AI")
