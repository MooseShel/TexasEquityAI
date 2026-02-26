"""
QR code report viewer page — replaces the ?account= routing from app.py lines 58–188.
Now lives at a proper URL: /report/[account]
"""
import reflex as rx
from texas_equity_ai.state import AppState
from texas_equity_ai.styles import (
    card_style, hero_banner_style, TEXT_MAIN, TEXT_MUTED, BORDER,
    RADIUS_SM, SUCCESS, WARNING, DANGER,
)
from texas_equity_ai.components.metric_card import metric_card


class ReportState(rx.State):
    """State specific to the report viewer page."""
    # NOTE: 'account' is provided automatically by the dynamic route /report/[account]
    property_data: dict = {}
    protest_data: dict = {}
    loading: bool = True
    error: str = ""

    @rx.var
    def has_data(self) -> bool:
        return bool(self.property_data)

    async def load_report_data(self):
        """Load report data from Supabase when page opens."""
        self.loading = True
        yield

        try:
            from backend.db.supabase_client import supabase_service

            # Get property
            prop = await supabase_service.get_property_by_account(self.account)
            if prop:
                self.property_data = prop
            else:
                self.error = f"Property not found for account: {self.account}"
                self.loading = False
                yield
                return

            # Get latest protest
            protest = await supabase_service.get_latest_protest(self.account)
            if protest:
                self.protest_data = protest

        except Exception as e:
            self.error = f"Failed to load report: {str(e)}"

        self.loading = False
        yield


def _safe_currency(val) -> str:
    try:
        return f"${float(val):,.0f}"
    except Exception:
        return "N/A"


def report_page() -> rx.Component:
    """The public report viewer page."""
    return rx.box(
        # Header
        rx.box(
            rx.hstack(
                rx.heading("🤠 Texas Equity AI", size="5"),
                rx.text("Property Tax Protest Report", color=TEXT_MUTED),
                align_items="center",
                spacing="3",
            ),
            padding="16px 24px",
            background="white",
            border_bottom=f"1px solid {BORDER}",
            margin_bottom="24px",
        ),

        rx.box(
            # Loading
            rx.cond(
                ReportState.loading,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text("Loading report...", color=TEXT_MUTED),
                        align_items="center",
                        spacing="3",
                    ),
                    min_height="300px",
                ),
            ),

            # Error
            rx.cond(
                ReportState.error != "",
                rx.callout(
                    rx.text(ReportState.error),
                    icon="triangle_alert",
                    color_scheme="red",
                ),
            ),

            # Report content
            rx.cond(
                ReportState.has_data,
                rx.box(
                    # Property address
                    rx.heading(
                        ReportState.property_data["address"].to(str),
                        size="6",
                        margin_bottom="4px",
                    ),
                    rx.text(
                        "Account: " + ReportState.property_data["account_number"].to(str),
                        color=TEXT_MUTED,
                        margin_bottom="24px",
                    ),

                    # Key metrics
                    rx.grid(
                        metric_card(
                            "Current Appraised",
                            ReportState.property_data["appraised_value"].to(str),
                        ),
                        metric_card(
                            "Year Built",
                            ReportState.property_data["year_built"].to(str),
                        ),
                        metric_card(
                            "Building Area",
                            ReportState.property_data["building_area"].to(str) + " sqft",
                        ),
                        columns=rx.breakpoints(initial="1", sm="3"),
                        spacing="4",
                        width="100%",
                        margin_bottom="24px",
                    ),

                    # Protest summary
                    rx.cond(
                        ReportState.protest_data.contains("narrative"),
                        rx.box(
                            rx.heading("Protest Summary", size="4", margin_bottom="8px"),
                            rx.callout(
                                rx.text(
                                    ReportState.protest_data["narrative"].to(str),
                                    white_space="pre-wrap",
                                ),
                                icon="file_text",
                                color_scheme="blue",
                            ),
                            **card_style,
                        ),
                    ),
                ),
            ),

            max_width="800px",
            margin="0 auto",
            padding="0 24px",
        ),

        background="#F8FAFC",
        min_height="100vh",
    )
