import reflex as rx
from texas_equity_ai.styles import BG_CARD, RADIUS_SM, BORDER

def _skeleton_card(height: str) -> rx.Component:
    """A generic rounded card wrapper with a skeleton block inside."""
    return rx.box(
        rx.skeleton(width="100%", height=height),
        padding="16px",
        border_radius=RADIUS_SM,
        border=f"1px solid {BORDER}",
        background=BG_CARD,
    )

def skeleton_loader() -> rx.Component:
    """Animated skeleton layout representing the Executive Report structure."""
    return rx.vstack(
        # Hero KPI skeletons (5 columns on desktop, 2 on mobile)
        rx.grid(
            _skeleton_card("80px"),
            _skeleton_card("80px"),
            _skeleton_card("80px"),
            _skeleton_card("80px"),
            _skeleton_card("80px"),
            columns=rx.breakpoints(initial="2", md="5"),
            spacing="4",
            width="100%",
            margin_bottom="32px",
        ),
        
        # Property Details Placeholder (Image + Details)
        rx.grid(
            _skeleton_card("200px"),
            rx.box(
                rx.skeleton(width="60%", height="24px", margin_bottom="12px"),
                rx.skeleton(width="40%", height="16px", margin_bottom="12px"),
                rx.skeleton(width="80%", height="16px", margin_bottom="12px"),
                rx.skeleton(width="70%", height="16px", margin_bottom="12px"),
                padding="16px",
                border_radius=RADIUS_SM,
                border=f"1px solid {BORDER}",
                background=BG_CARD,
                height="100%",
            ),
            columns=rx.breakpoints(initial="1", md="2"),
            spacing="4",
            width="100%",
            margin_bottom="32px",
        ),
        
        # Table placeholders
        rx.box(
            rx.skeleton(width="30%", height="32px", margin_bottom="24px"), # Table title
            # Header row
            rx.skeleton(width="100%", height="32px", margin_bottom="16px"),
            # Content rows
            rx.skeleton(width="100%", height="48px", margin_bottom="8px"),
            rx.skeleton(width="100%", height="48px", margin_bottom="8px"),
            rx.skeleton(width="100%", height="48px", margin_bottom="8px"),
            rx.skeleton(width="100%", height="48px", margin_bottom="8px"),
            rx.skeleton(width="100%", height="48px"),
            padding="24px",
            border_radius=RADIUS_SM,
            border=f"1px solid {BORDER}",
            background=BG_CARD,
            width="100%",
            margin_bottom="32px",
        ),
        
        # Another Table placeholder
        rx.box(
            rx.skeleton(width="30%", height="32px", margin_bottom="24px"),
            rx.skeleton(width="100%", height="32px", margin_bottom="16px"),
            rx.skeleton(width="100%", height="48px", margin_bottom="8px"),
            rx.skeleton(width="100%", height="48px", margin_bottom="8px"),
            rx.skeleton(width="100%", height="48px"),
            padding="24px",
            border_radius=RADIUS_SM,
            border=f"1px solid {BORDER}",
            background=BG_CARD,
            width="100%",
        ),
        
        width="100%",
        spacing="6",
        margin_top="24px",
    )
