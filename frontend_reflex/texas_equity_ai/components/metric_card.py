"""Metric card — dark glass card with gradient accent border."""
import reflex as rx
from texas_equity_ai.styles import (
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER, RADIUS, BG_CARD, SHADOW_SM, SHADOW_GLOW, BORDER_GLOW,
    GRADIENT_PRIMARY, FONT_MONO,
)


def metric_card(
    label: str,
    value: rx.Var | str,
    icon: str = "",
    delta: rx.Var | str = "",
    delta_color: str = "",
    **kwargs,
) -> rx.Component:
    """Render a single KPI metric card with glass styling."""
    return rx.box(
        # Gradient top accent
        rx.box(
            height="3px",
            width="100%",
            background=GRADIENT_PRIMARY,
            border_top_left_radius=RADIUS,
            border_top_right_radius=RADIUS,
            position="absolute",
            top="0",
            left="0",
        ),
        rx.vstack(
            rx.hstack(
                rx.cond(
                    icon != "",
                    rx.text(icon, font_size="1.3rem"),
                ),
                rx.text(
                    label,
                    font_size="0.7rem",
                    text_transform="uppercase",
                    letter_spacing="0.8px",
                    color=TEXT_MUTED,
                    font_weight="600",
                ),
                spacing="2",
                align_items="center",
            ),
            rx.text(
                value,
                font_size="1.5rem",
                font_weight="800",
                color=TEXT_PRIMARY,
                font_family=FONT_MONO,
            ),
            rx.cond(
                delta != "",
                rx.text(
                    delta,
                    font_size="0.85rem",
                    font_weight="600",
                    color=delta_color if delta_color else TEXT_SECONDARY,
                ),
            ),
            spacing="1",
            align_items="flex-start",
            width="100%",
        ),
        position="relative",
        background=BG_CARD,
        backdrop_filter="blur(12px)",
        border=f"1px solid {BORDER}",
        border_radius=RADIUS,
        padding="20px",
        padding_top="24px",
        box_shadow=SHADOW_SM,
        transition="all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
        _hover={
            "box_shadow": SHADOW_GLOW,
            "border": f"1px solid {BORDER_GLOW}",
            "transform": "translateY(-3px)",
        },
        overflow="hidden",
        **kwargs,
    )
