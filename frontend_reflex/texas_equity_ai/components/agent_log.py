"""Live agent log display — terminal-style dark panel."""
import reflex as rx
from texas_equity_ai.styles import (
    BORDER, RADIUS_SM, ACCENT, TEXT_SECONDARY, TEXT_MUTED, FONT_MONO,
    BG_ELEVATED,
)

# Dark terminal colors
_TERM_BG = "#0D1117"
_TERM_TEXT = "#8B949E"
_TERM_HEADER = "#161B22"


def agent_log(logs: rx.Var[list[str]], is_generating: rx.Var[bool]) -> rx.Component:
    """Render a terminal-style log panel showing agent activity."""
    return rx.box(
        # Header bar — macOS traffic light dots
        rx.hstack(
            rx.hstack(
                rx.box(width="10px", height="10px", border_radius="50%", background="#EF4444"),
                rx.box(width="10px", height="10px", border_radius="50%", background="#F59E0B"),
                rx.box(width="10px", height="10px", border_radius="50%", background="#10B981"),
                spacing="2",
            ),
            rx.text(
                "agent_pipeline.log",
                font_family=FONT_MONO,
                font_size="0.7rem",
                color=TEXT_MUTED,
            ),
            spacing="3",
            align_items="center",
            padding="8px 14px",
            background=_TERM_HEADER,
            border_bottom=f"1px solid {BORDER}",
            border_top_left_radius=RADIUS_SM,
            border_top_right_radius=RADIUS_SM,
        ),

        # Spinner while generating
        rx.cond(
            is_generating,
            rx.hstack(
                rx.spinner(size="3", color=ACCENT),
                rx.text(
                    "Processing...",
                    font_weight="600",
                    color=ACCENT,
                    font_family=FONT_MONO,
                    font_size="0.8rem",
                ),
                spacing="2",
                align_items="center",
                padding="8px 14px",
                background=_TERM_BG,
            ),
        ),

        # Log output — plain dark text panel, NOT rx.code_block
        rx.cond(
            logs.length() > 0,
            rx.box(
                rx.text(
                    logs.join("\n"),
                    font_family=FONT_MONO,
                    font_size="0.8rem",
                    color=_TERM_TEXT,
                    white_space="pre-wrap",
                    word_break="break-word",
                    line_height="1.65",
                ),
                background=_TERM_BG,
                padding="14px",
                max_height="300px",
                overflow_y="auto",
                border_bottom_left_radius=RADIUS_SM,
                border_bottom_right_radius=RADIUS_SM,
                border=f"1px solid {BORDER}",
                border_top="none",
            ),
        ),
        width="100%",
        border_radius=RADIUS_SM,
    )
