"""Property details card — dark glass theme."""
import reflex as rx
from texas_equity_ai.state import AppState
from texas_equity_ai.styles import (
    glass_card_style, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER, ACCENT, RADIUS_SM, BG_ELEVATED,
)


def _detail_row(label: str, value: rx.Var) -> rx.Component:
    return rx.box(
        rx.text(
            label,
            font_size="0.7rem",
            text_transform="uppercase",
            letter_spacing="0.8px",
            color=TEXT_MUTED,
            font_weight="600",
            margin_bottom="4px",
        ),
        rx.text(
            value.to(str),
            font_size="1.05rem",
            font_weight="600",
            color=TEXT_PRIMARY,
        ),
        padding="12px",
        background=BG_ELEVATED,
        border_radius=RADIUS_SM,
    )


def property_card() -> rx.Component:
    """Render the property details card with dark glass styling."""
    return rx.box(
        rx.hstack(
            rx.box(
                rx.text(
                    "📍",
                    font_size="1.5rem",
                ),
                padding="8px",
                background="rgba(59, 130, 246, 0.1)",
                border_radius=RADIUS_SM,
            ),
            rx.box(
                rx.text(
                    AppState.property_data["address"].to(str),
                    font_size="1.2rem", font_weight="700",
                    color=TEXT_PRIMARY,
                ),
                rx.text(
                    "Account: " + AppState.property_data["account_number"].to(str),
                    font_size="0.85rem",
                    color=TEXT_SECONDARY,
                ),
            ),
            spacing="3",
            align_items="center",
            margin_bottom="16px",
            padding_bottom="16px",
            border_bottom=f"1px solid {BORDER}",
            width="100%",
        ),
        rx.grid(
            _detail_row("Year Built", AppState.property_data["year_built"]),
            _detail_row("Building Area", AppState.property_data["building_area"]),
            _detail_row("Neighborhood", AppState.property_data["neighborhood_code"]),
            _detail_row("District", AppState.property_data["district"]),
            columns=rx.breakpoints(initial="2", sm="3", md="4"),
            spacing="3",
        ),
        width="100%",
        overflow="hidden",
        **glass_card_style,
    )
