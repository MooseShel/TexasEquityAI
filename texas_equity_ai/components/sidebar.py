"""Sidebar component — collapsible dark themed with gradient accents."""
import reflex as rx
from texas_equity_ai.state import AppState, DISTRICT_OPTIONS
from texas_equity_ai.styles import (
    BORDER, BORDER_GLOW, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    primary_button_style, secondary_button_style, input_style,
    RADIUS_SM, BG_ELEVATED, PRIMARY, PRIMARY_GLOW, ACCENT, GRADIENT_PRIMARY,
    SUCCESS, DANGER, BG_DARK, BG_DARKEST,
)

# ── Sidebar dimensions ──────────────────────────────────────────
SIDEBAR_EXPANDED = "300px"
SIDEBAR_COLLAPSED = "64px"


def _collapsible_box(*children, **props) -> rx.Component:
    """A box that hides its content via CSS when sidebar is collapsed.
    Uses display:none instead of rx.cond to avoid DOM create/destroy lag.
    """
    return rx.box(
        *children,
        display=rx.cond(AppState.sidebar_collapsed, "none", "block"),
        **props,
    )


def _section_label(text: str) -> rx.Component:
    """Compact section label."""
    return rx.text(
        text,
        font_size="0.65rem",
        font_weight="700",
        text_transform="uppercase",
        letter_spacing="1.2px",
        color=TEXT_MUTED,
        margin_bottom="6px",
        margin_top="2px",
    )


def _glow_divider() -> rx.Component:
    """Thin glowing divider."""
    return rx.box(
        height="1px",
        width="100%",
        background=f"linear-gradient(90deg, transparent, {BORDER_GLOW}, transparent)",
        margin_y="12px",
        flex_shrink="0",
    )


def _toggle_button() -> rx.Component:
    """Hamburger / collapse toggle button at top of sidebar."""
    return rx.box(
        rx.icon(
            tag=rx.cond(AppState.sidebar_collapsed, "panel-left-open", "panel-left-close"),
            size=20,
            color=TEXT_SECONDARY,
        ),
        on_click=AppState.toggle_sidebar,
        cursor="pointer",
        padding="8px",
        border_radius=RADIUS_SM,
        display="flex",
        align_items="center",
        justify_content=rx.cond(AppState.sidebar_collapsed, "center", "flex-end"),
        width="100%",
        margin_bottom="8px",
        flex_shrink="0",
        _hover={
            "background": "rgba(59, 130, 246, 0.1)",
        },
    )


def sidebar() -> rx.Component:
    """Render the collapsible application sidebar with dark theme."""
    return rx.box(
        _toggle_button(),

        # ── Brand ──────────────────────────────────────────────────
        rx.box(
            rx.image(
                src="/logo.webp",
                width=rx.cond(AppState.sidebar_collapsed, "40px", "80%"),
                max_width="200px",
                margin_x="auto",
                margin_bottom="8px",
                border_radius=RADIUS_SM,
                display="block",
                transition="width 0.2s ease",
            ),
            _collapsible_box(
                rx.heading(
                    "Texas Equity AI",
                    size="4",
                    color=TEXT_PRIMARY,
                    margin_bottom="2px",
                    text_align="center",
                ),
                rx.text(
                    "🤠 Automating property tax protests in Texas.",
                    color=TEXT_SECONDARY,
                    font_size="0.8rem",
                    text_align="center",
                ),
            ),
            flex_shrink="0",
            margin_bottom="8px",
            text_align="center",
        ),

        # ── District Selector ──────────────────────────────────────
        _collapsible_box(
            _section_label("Appraisal District"),
            rx.select(
                DISTRICT_OPTIONS,
                value=AppState.district_name,
                on_change=AppState.set_district,
                width="100%",
            ),
            flex_shrink="0",
            margin_bottom="4px",
        ),

        _glow_divider(),

        # ── Settings ──────────────────────────────────────────────
        _collapsible_box(
            _section_label("Settings"),
            rx.hstack(
                rx.text("Tax Rate", font_size="0.8rem", color=TEXT_SECONDARY),
                rx.text(
                    AppState.tax_rate.to(str) + "%",
                    font_size="0.8rem",
                    color=ACCENT,
                    font_weight="700",
                ),
                width="100%",
                justify="between",
                margin_bottom="4px",
            ),
            rx.box(
                rx.slider(
                    value=[AppState.tax_rate],
                    min=1.0,
                    max=4.0,
                    step=0.1,
                    on_value_commit=AppState.set_tax_rate,
                    width="100%",
                ),
                width="100%",
                height="24px",
                margin_bottom="8px",
            ),
            rx.hstack(
                rx.switch(
                    checked=AppState.force_fresh,
                    on_change=AppState.toggle_force_fresh,
                    size="1",
                ),
                rx.text("Force fresh comps", font_size="0.8rem", color=TEXT_SECONDARY),
                spacing="2",
                align_items="center",
            ),
            flex_shrink="0",
        ),

        _glow_divider(),

        # ── Manual Override ────────────────────────────────────────
        _collapsible_box(
            rx.accordion.root(
                rx.accordion.item(
                    header="📝 Manual Data (Optional)",
                    content=rx.box(
                        rx.text("Address", font_size="0.75rem", color=TEXT_MUTED, margin_bottom="2px"),
                        rx.input(
                            placeholder="Override address",
                            value=AppState.manual_address,
                            on_change=AppState.set_manual_address,
                            **input_style,
                            margin_bottom="6px",
                        ),
                        rx.text("Appraised Value", font_size="0.75rem", color=TEXT_MUTED, margin_bottom="2px"),
                        rx.input(
                            placeholder="0",
                            value=AppState.manual_value.to(str),
                            on_change=AppState.set_manual_value,
                            type="number",
                            **input_style,
                            margin_bottom="6px",
                        ),
                        rx.text("Building Area (sqft)", font_size="0.75rem", color=TEXT_MUTED, margin_bottom="2px"),
                        rx.input(
                            placeholder="0",
                            value=AppState.manual_area.to(str),
                            on_change=AppState.set_manual_area,
                            type="number",
                            **input_style,
                        ),
                        padding="4px 0",
                    ),
                ),
                collapsible=True,
                width="100%",
            ),
            flex_shrink="0",
        ),

        _glow_divider(),

        # ── Tools ──────────────────────────────────────────────────
        _collapsible_box(
            _section_label("Tools"),

            # Anomaly Scanner
            rx.accordion.root(
                rx.accordion.item(
                    header="🔍 Anomaly Scanner",
                    content=rx.box(
                        rx.text("Find over-assessed properties", font_size="0.75rem", color=TEXT_MUTED, margin_bottom="6px"),
                        rx.input(
                            placeholder="Neighborhood code (e.g. 2604.71)",
                            value=AppState.scan_nbhd_code,
                            on_change=AppState.set_scan_nbhd_code,
                            **input_style,
                            margin_bottom="6px",
                        ),
                        rx.select(
                            DISTRICT_OPTIONS,
                            value=AppState.district_name,
                            on_change=AppState.set_district,
                            width="100%",
                            margin_bottom="6px",
                        ),
                        rx.button(
                            "📊 Run Scan",
                            on_click=AppState.run_anomaly_scan,
                            **secondary_button_style,
                            width="100%",
                        ),
                        rx.cond(
                            AppState.scan_results.contains("stats"),
                            rx.text("✅ Scan complete", font_size="0.8rem", color=SUCCESS, margin_top="4px"),
                        ),
                        padding="4px 0",
                    ),
                ),
                collapsible=True,
                width="100%",
                margin_bottom="6px",
            ),

            # Assessment Monitor
            rx.accordion.root(
                rx.accordion.item(
                    header="🔔 Assessment Monitor",
                    content=rx.box(
                        rx.text("Track annual assessment changes", font_size="0.75rem", color=TEXT_MUTED, margin_bottom="6px"),
                        rx.input(
                            placeholder="Account (e.g. 0660460360030)",
                            value=AppState.watch_account,
                            on_change=AppState.set_watch_account,
                            **input_style,
                            margin_bottom="6px",
                        ),
                        rx.button(
                            "➕ Add to Watch List",
                            on_click=AppState.add_to_watch_list,
                            **secondary_button_style,
                            width="100%",
                        ),
                        rx.cond(
                            AppState.watch_list.length() > 0,
                            rx.box(
                                rx.text(
                                    "Watching " + AppState.watch_list.length().to(str) + " properties",
                                    font_weight="600", font_size="0.8rem", color=ACCENT,
                                    margin_top="6px", margin_bottom="4px",
                                ),
                                rx.foreach(AppState.watch_list, _watch_item),
                                rx.button(
                                    "🔄 Refresh All",
                                    on_click=AppState.refresh_watch_list,
                                    **secondary_button_style,
                                    width="100%",
                                    margin_top="6px",
                                ),
                            ),
                        ),
                        padding="4px 0",
                    ),
                ),
                collapsible=True,
                width="100%",
                margin_bottom="6px",
            ),

            # Pitch Deck
            rx.button(
                "📄 Generate Pitch Deck",
                on_click=AppState.generate_pitch_deck,
                **secondary_button_style,
                width="100%",
                margin_top="4px",
                margin_bottom="4px",
            ),
            rx.cond(
                AppState.pitch_deck_path != "",
                rx.link(
                    rx.button(
                        "⬇️ Download Pitch Deck",
                        **secondary_button_style,
                        width="100%",
                    ),
                    href=rx.get_upload_url(AppState.pitch_deck_path),
                    is_external=True,
                    width="100%",
                ),
            ),
            flex_shrink="0",
        ),

        # ── Footer ────────────────────────────────────────────────
        rx.box(flex="1"),  # spacer pushes footer to bottom
        _collapsible_box(
            rx.text(
                "Texas Equity AI © 2025",
                font_size="0.65rem",
                color=TEXT_MUTED,
                text_align="center",
            ),
            flex_shrink="0",
        ),

        # ── Sidebar styles ────────────────────────────────────────
        width=rx.cond(AppState.sidebar_collapsed, SIDEBAR_COLLAPSED, SIDEBAR_EXPANDED),
        min_width=rx.cond(AppState.sidebar_collapsed, SIDEBAR_COLLAPSED, SIDEBAR_EXPANDED),
        background=f"linear-gradient(180deg, {BG_DARK} 0%, {BG_DARKEST} 100%)",
        border_right=f"1px solid {BORDER}",
        padding=rx.cond(AppState.sidebar_collapsed, "16px 8px", "24px"),
        overflow_y="auto",
        overflow_x="hidden",
        height="100vh",
        position="fixed",
        left="0",
        top="0",
        display="flex",
        flex_direction="column",
        transition="all 0.2s ease",
        z_index="50",
    )


def _watch_item(watch: dict) -> rx.Component:
    """Render a single watch list item."""
    return rx.hstack(
        rx.text(watch["account_number"].to(str), font_weight="600", font_size="0.8rem", color=TEXT_PRIMARY),
        rx.cond(
            watch.contains("change_pct"),
            rx.text(
                watch["change_pct"].to(str) + "%",
                font_size="0.8rem",
                color=rx.cond(watch["alert_triggered"], DANGER, SUCCESS),
            ),
        ),
        width="100%",
        justify="between",
        padding_y="3px",
        border_bottom=f"1px solid {BORDER}",
    )
