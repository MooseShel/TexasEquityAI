"""
Main dashboard page — dark-themed premium UI.
Handles account input, protest generation, and results display (5 tabs).
"""
import reflex as rx
import json
from texas_equity_ai.state import AppState
from texas_equity_ai.styles import (
    main_content_style, card_style, glass_card_style, hero_banner_style,
    primary_button_style, secondary_button_style, input_style,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER, BORDER_GLOW, RADIUS, RADIUS_SM, RADIUS_LG,
    BG_SURFACE, BG_ELEVATED, BG_CARD,
    SUCCESS, SUCCESS_BG, WARNING, WARNING_BG, DANGER, DANGER_BG,
    INFO_BG, INFO_TEXT, SEVERITY_COLORS, SEVERITY_EMOJI,
    PRIMARY, PRIMARY_GLOW, ACCENT, GRADIENT_PRIMARY, GRADIENT_SUBTLE,
    FONT_MONO, SHADOW_SM, SHADOW_MD, SHADOW_GLOW,
    terminal_style,
)
from texas_equity_ai.components.metric_card import metric_card
from texas_equity_ai.components.property_card import property_card
from texas_equity_ai.components.comp_table import equity_comp_table, sales_comp_table
from texas_equity_ai.components.agent_log import agent_log
from texas_equity_ai.components.map_view import map_view
from texas_equity_ai.components.image_gallery import image_gallery


# ── Hero Banner ────────────────────────────────────────────────────
def hero_banner() -> rx.Component:
    """Top banner with key metrics — premium dark glass design."""
    return rx.box(
        # Background glow effect
        rx.box(
            position="absolute",
            top="-50%",
            right="-20%",
            width="400px",
            height="400px",
            background=f"radial-gradient(circle, {PRIMARY_GLOW} 0%, transparent 70%)",
            pointer_events="none",
        ),
        rx.heading(
            "🎯 Protest Packet Results",
            size="6",
            color="white",
            margin_bottom="20px",
            position="relative",
        ),
        rx.grid(
            # Current Appraised
            _kpi_card("🏠", "CURRENT APPRAISED", AppState.fmt_appraised, color="#F87171"),
            # Target Protest Value
            _kpi_card("🎯", "TARGET PROTEST VALUE", AppState.fmt_target_protest, color=SUCCESS,
                       delta=AppState.fmt_savings),
            # Equity Target
            _kpi_card("⚖️", "EQUITY TARGET", AppState.fmt_justified, color=ACCENT),
            # Sales Target
            _kpi_card("💰", "SALES TARGET", AppState.fmt_market, color="#A78BFA"),
            columns=rx.breakpoints(initial="2", md="4"),
            spacing="3",
            position="relative",
        ),
        **hero_banner_style,
    )


def _kpi_card(icon: str, label: str, value: rx.Var, color: str = "white",
              delta: rx.Var | str = "") -> rx.Component:
    """Individual KPI card inside the hero banner."""
    return rx.box(
        rx.text(
            icon + " " + label,
            font_size="0.6rem",
            color="rgba(255,255,255,0.5)",
            font_weight="700",
            letter_spacing="0.8px",
            text_transform="uppercase",
            margin_bottom="6px",
        ),
        rx.text(
            value,
            font_size="1.3rem",
            font_weight="800",
            color=color,
            font_family=FONT_MONO,
        ),
        rx.cond(
            delta != "",
            rx.text(
                delta,
                font_size="0.8rem",
                color=SUCCESS,
                font_weight="600",
                margin_top="2px",
            ),
        ),
        padding="16px",
        background="rgba(255,255,255,0.05)",
        border="1px solid rgba(255,255,255,0.08)",
        border_radius=RADIUS_SM,
        backdrop_filter="blur(8px)",
        transition="all 0.3s ease",
        _hover={
            "background": "rgba(255,255,255,0.08)",
            "border": "1px solid rgba(255,255,255,0.15)",
            "transform": "translateY(-2px)",
        },
    )


# ── Tab: Overview ──────────────────────────────────────────────────
def tab_overview() -> rx.Component:
    return rx.box(
        # Property details card
        rx.cond(
            AppState.property_data.contains("address"),
            property_card(),
        ),

        # Metric grid
        rx.grid(
            metric_card(
                label="Tax Savings",
                value=AppState.fmt_tax_savings,
                icon="💸",
                delta=AppState.fmt_savings,
                delta_color=SUCCESS,
            ),
            metric_card(
                label="Equity Gap",
                value=AppState.fmt_justified,
                icon="⚖️",
            ),
            metric_card(
                label="Market Value",
                value=AppState.fmt_market,
                icon="📈",
            ),
            columns=rx.breakpoints(initial="1", sm="2", md="3"),
            spacing="4",
            margin_top="16px",
            margin_bottom="16px",
        ),

        # Annual savings callout
        rx.cond(
            AppState.total_savings > 0,
            rx.box(
                rx.hstack(
                    rx.text("📉", font_size="1.3rem"),
                    rx.text(
                        "Potential annual tax savings: " + AppState.fmt_tax_savings,
                        font_weight="700",
                        color=SUCCESS,
                        font_size="1.05rem",
                    ),
                    spacing="3",
                    align_items="center",
                ),
                background=SUCCESS_BG,
                border=f"1px solid rgba(16, 185, 129, 0.2)",
                border_radius=RADIUS_SM,
                padding="16px",
                margin_bottom="16px",
            ),
        ),

        # External obsolescence factors
        rx.cond(
            AppState.external_obsolescence_factors.length() > 0,
            rx.box(
                rx.heading("🏗️ External Obsolescence Factors", size="4", color=TEXT_PRIMARY, margin_bottom="12px"),
                rx.foreach(
                    AppState.external_obsolescence_factors,
                    _obs_factor_card,
                ),
                margin_top="12px",
            ),
        ),

        padding_top="8px",
    )


def _obs_factor_card(f: dict) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(f["type"].to(str), font_weight="700", color=TEXT_PRIMARY, flex="1"),
            rx.text(
                "-" + f["impact_pct"].to(str) + "%",
                font_weight="700",
                color=DANGER,
                font_family=FONT_MONO,
            ),
            width="100%",
            justify="between",
        ),
        rx.text(f["description"].to(str), color=TEXT_SECONDARY, font_size="0.85rem", margin_top="4px"),
        **glass_card_style,
        margin_bottom="8px",
    )


# ── Tab: Comparables ──────────────────────────────────────────────
def tab_comparables() -> rx.Component:
    return rx.box(
        # Map — rendered via computed var URL
        rx.cond(
            AppState.map_url != "",
            rx.box(
                rx.heading("🗺️ Property & Comp Locations", size="4", color=TEXT_PRIMARY, margin_bottom="8px"),
                rx.image(
                    src=AppState.map_url,
                    width="100%",
                    border_radius=RADIUS_SM,
                    alt="Property location map",
                    border=f"1px solid {BORDER}",
                ),
                # Legend
                rx.hstack(
                    rx.box(width="12px", height="12px", border_radius="50%", background="#EF4444"),
                    rx.text("Subject Property", font_size="0.8rem", color=TEXT_SECONDARY),
                    rx.box(width="16px"),
                    rx.box(width="12px", height="12px", border_radius="50%", background=PRIMARY),
                    rx.text("Comparable Properties", font_size="0.8rem", color=TEXT_SECONDARY),
                    margin_top="8px",
                    spacing="2",
                    align_items="center",
                ),
                **glass_card_style,
                margin_bottom="20px",
            ),
        ),

        # Equity comps
        rx.cond(
            AppState.equity_comps.length() > 0,
            rx.box(
                equity_comp_table(),
                margin_bottom="20px",
            ),
        ),

        # Sales comps
        rx.cond(
            AppState.sales_comps.length() > 0,
            rx.box(
                sales_comp_table(),
                margin_bottom="20px",
            ),
        ),

        rx.cond(
            (AppState.equity_comps.length() == 0) & (AppState.sales_comps.length() == 0),
            rx.box(
                rx.hstack(
                    rx.text("ℹ️", font_size="1.2rem"),
                    rx.text("No comparable data available. The analysis may still be running.", color=TEXT_SECONDARY),
                    spacing="2",
                    align_items="center",
                ),
                background=INFO_BG,
                border=f"1px solid rgba(59, 130, 246, 0.15)",
                border_radius=RADIUS_SM,
                padding="16px",
            ),
        ),
        padding_top="8px",
    )


# ── Tab: Condition ─────────────────────────────────────────────────
def tab_condition() -> rx.Component:
    return rx.box(
        # Condition summary
        rx.cond(
            AppState.condition_summary_item.contains("issue"),
            rx.box(
                rx.heading("📸 Property Condition Assessment", size="4", color=TEXT_PRIMARY, margin_bottom="8px"),
                rx.text(
                    AppState.condition_summary_item["overall_condition"].to(str),
                    font_size="1.1rem",
                    font_weight="600",
                    color=ACCENT,
                    margin_bottom="16px",
                ),
                **glass_card_style,
                margin_bottom="16px",
            ),
        ),

        # Individual issues
        rx.cond(
            AppState.condition_issues.length() > 0,
            rx.box(
                rx.heading("🔍 Detected Issues", size="4", color=TEXT_PRIMARY, margin_bottom="12px"),
                rx.foreach(
                    AppState.condition_issues,
                    _condition_issue_card,
                ),
            ),
        ),

        # Image gallery — use rx.foreach since image_gallery uses Python for-loop
        rx.cond(
            AppState.all_image_paths.length() > 0,
            rx.box(
                rx.heading("📷 Street View Analysis", size="4", color=TEXT_PRIMARY, margin_bottom="8px", margin_top="24px"),
                rx.text("Annotated images with detected issues", color=TEXT_MUTED, font_size="0.85rem", margin_bottom="12px"),
                rx.grid(
                    rx.foreach(
                        AppState.all_image_paths,
                        _street_view_image,
                    ),
                    columns=rx.breakpoints(initial="1", sm="2", md="3"),
                    spacing="4",
                    width="100%",
                ),
            ),
        ),

        rx.cond(
            AppState.condition_issues.length() == 0,
            rx.box(
                rx.hstack(
                    rx.text("✅", font_size="1.2rem"),
                    rx.text("No condition issues detected. Property appears in good condition.", color=SUCCESS),
                    spacing="2",
                    align_items="center",
                ),
                background=SUCCESS_BG,
                border=f"1px solid rgba(16, 185, 129, 0.2)",
                border_radius=RADIUS_SM,
                padding="16px",
            ),
        ),
        padding_top="8px",
    )


def _street_view_image(path: rx.Var[str]) -> rx.Component:
    """Render a single street view image for rx.foreach."""
    return rx.box(
        rx.image(
            src=path,
            width="100%",
            border_radius=RADIUS_SM,
            border=f"1px solid {BORDER}",
            object_fit="cover",
            alt="Street View",
        ),
    )


def _condition_issue_card(issue: dict) -> rx.Component:
    severity = issue["severity"].to(str)
    return rx.box(
        rx.hstack(
            rx.text(issue["issue"].to(str), font_weight="700", color=TEXT_PRIMARY, flex="1"),
            rx.text(
                severity,
                font_weight="600",
                font_size="0.8rem",
                padding="2px 10px",
                border_radius="12px",
                background=WARNING_BG,
                color=WARNING,
            ),
            width="100%",
            justify="between",
            margin_bottom="8px",
        ),
        rx.text(issue["description"].to(str), color=TEXT_SECONDARY, font_size="0.9rem", margin_bottom="8px"),
        rx.hstack(
            rx.text("Deduction:", font_weight="500", color=TEXT_MUTED),
            rx.text(
                "$" + issue["deduction"].to(int).to(str),
                color=DANGER,
                font_weight="700",
                font_family=FONT_MONO,
            ),
            spacing="2",
        ),
        **glass_card_style,
        margin_bottom="8px",
    )


# ── Tab: Protest Packet ────────────────────────────────────────────
def tab_protest() -> rx.Component:
    return rx.box(
        # Value explanation
        rx.box(
            rx.hstack(
                rx.text("ℹ️", font_size="1.2rem"),
                rx.text(
                    "The AI Protest Value is the lowest of Equity Uniformity, Sales Comparison, and Current Appraisal, minus physical condition deductions.",
                    color=INFO_TEXT,
                    font_size="0.9rem",
                ),
                spacing="2",
                align_items="center",
            ),
            background=INFO_BG,
            border=f"1px solid rgba(59, 130, 246, 0.15)",
            border_radius=RADIUS_SM,
            padding="16px",
            margin_bottom="16px",
        ),

        # Savings banner
        rx.cond(
            AppState.total_savings > 0,
            rx.box(
                rx.hstack(
                    rx.text("✅", font_size="1.3rem"),
                    rx.text(
                        "Recommended protest value: " + AppState.fmt_target_protest
                        + " — Potential annual savings: "
                        + AppState.fmt_tax_savings,
                        font_weight="700",
                        color=SUCCESS,
                        font_size="1rem",
                    ),
                    spacing="3",
                    align_items="center",
                ),
                background=SUCCESS_BG,
                border=f"1px solid rgba(16, 185, 129, 0.2)",
                border_radius=RADIUS_SM,
                padding="16px",
                margin_bottom="16px",
            ),
        ),

        # PDF Download
        rx.cond(
            AppState.pdf_path != "",
            rx.link(
                rx.button(
                    rx.hstack(
                        rx.icon("download", size=18),
                        rx.text("Download Complete Protest Packet"),
                        spacing="2",
                        align_items="center",
                    ),
                    background=GRADIENT_PRIMARY,
                    color="white",
                    border="none",
                    border_radius=RADIUS_SM,
                    font_weight="700",
                    min_height="48px",
                    width="100%",
                    cursor="pointer",
                    box_shadow=f"0 4px 14px {PRIMARY_GLOW}",
                    _hover={
                        "transform": "translateY(-2px)",
                        "box_shadow": SHADOW_GLOW,
                        "filter": "brightness(1.1)",
                    },
                ),
                href=AppState.pdf_path,
                is_external=True,
                width="100%",
                margin_bottom="16px",
            ),
        ),

        rx.cond(
            AppState.pdf_error != "",
            rx.box(
                rx.hstack(
                    rx.text("⚠️", font_size="1.2rem"),
                    rx.text("PDF Generation Failed: " + AppState.pdf_error, color=DANGER),
                    spacing="2",
                    align_items="center",
                ),
                background=DANGER_BG,
                border=f"1px solid rgba(239, 68, 68, 0.2)",
                border_radius=RADIUS_SM,
                padding="16px",
            ),
        ),

        # Narrative
        rx.cond(
            AppState.narrative != "",
            rx.box(
                rx.heading("📝 Full Narrative", size="4", color=TEXT_PRIMARY, margin_bottom="12px"),
                rx.box(
                    rx.text(AppState.narrative, white_space="pre-wrap", color=TEXT_SECONDARY, line_height="1.7"),
                    background=BG_ELEVATED,
                    border=f"1px solid {BORDER}",
                    border_radius=RADIUS_SM,
                    padding="20px",
                ),
                margin_top="16px",
            ),
        ),
        padding_top="8px",
    )


# ── Tab: Debug ─────────────────────────────────────────────────────
def tab_debug() -> rx.Component:
    return rx.box(
        rx.box(
            rx.hstack(
                rx.text("🐛", font_size="1.1rem"),
                rx.text("Raw generation data for debugging.", color=TEXT_SECONDARY, font_size="0.9rem"),
                spacing="2",
                align_items="center",
            ),
            background=INFO_BG,
            border=f"1px solid rgba(59, 130, 246, 0.15)",
            border_radius=RADIUS_SM,
            padding="12px",
            margin_bottom="16px",
        ),
        rx.accordion.root(
            rx.accordion.item(
                header="Raw Property Data",
                content=rx.code_block(
                    AppState.property_data.to(str),
                    language="json",
                    show_line_numbers=True,
                    theme="dark",
                ),
            ),
            rx.accordion.item(
                header="Raw Equity Data",
                content=rx.code_block(
                    AppState.equity_data.to(str),
                    language="json",
                    show_line_numbers=True,
                    theme="dark",
                ),
            ),
            rx.accordion.item(
                header="Vision Detections",
                content=rx.code_block(
                    AppState.vision_data.to(str),
                    language="json",
                    show_line_numbers=True,
                    theme="dark",
                ),
            ),
            collapsible=True,
            width="100%",
        ),
        padding_top="8px",
    )


# ── Main dashboard page ───────────────────────────────────────────
def dashboard() -> rx.Component:
    """The main dashboard page — dark theme."""
    return rx.box(
        # Input section
        rx.box(
            rx.hstack(
                rx.text("⚡", font_size="2rem"),
                rx.box(
                    rx.heading("Generate Protest Packet", size="7", color=TEXT_PRIMARY, margin_bottom="2px"),
                    rx.text(
                        "Enter an account number to generate a comprehensive AI-powered protest packet.",
                        color=TEXT_MUTED,
                    ),
                ),
                spacing="3",
                align_items="center",
                margin_bottom="24px",
            ),

            # Account input
            rx.hstack(
                rx.input(
                    placeholder=AppState.account_placeholder,
                    value=AppState.account_number,
                    on_change=AppState.set_account_number,
                    **input_style,
                    flex="1",
                    size="3",
                ),
                rx.button(
                    rx.cond(
                        AppState.is_generating,
                        rx.spinner(size="2"),
                        rx.hstack(
                            rx.icon("zap", size=16),
                            rx.text("Generate"),
                            spacing="2",
                            align_items="center",
                        ),
                    ),
                    on_click=AppState.generate_protest,
                    disabled=AppState.is_generating,
                    background=GRADIENT_PRIMARY,
                    color="white",
                    border="none",
                    border_radius=RADIUS_SM,
                    font_weight="700",
                    min_height="44px",
                    cursor="pointer",
                    width="auto",
                    min_width="140px",
                    box_shadow=f"0 4px 14px {PRIMARY_GLOW}",
                    _hover={
                        "transform": "translateY(-2px)",
                        "box_shadow": SHADOW_GLOW,
                        "filter": "brightness(1.1)",
                    },
                ),
                width="100%",
                spacing="3",
            ),

            # Error message
            rx.cond(
                AppState.error_message != "",
                rx.box(
                    rx.hstack(
                        rx.text("⚠️", font_size="1.1rem"),
                        rx.text(AppState.error_message, color=DANGER),
                        spacing="2",
                        align_items="center",
                    ),
                    background=DANGER_BG,
                    border=f"1px solid rgba(239, 68, 68, 0.2)",
                    border_radius=RADIUS_SM,
                    padding="12px",
                    margin_top="12px",
                ),
            ),

            # Agent logs — visible while generating, collapsed once results show
            rx.cond(
                AppState.agent_logs.length() > 0,
                rx.cond(
                    AppState.generation_complete,
                    # Collapsed accordion after completion
                    rx.accordion.root(
                        rx.accordion.item(
                            header="📋 Agent Pipeline Log",
                            content=rx.box(
                                agent_log(AppState.agent_logs, AppState.is_generating),
                            ),
                        ),
                        collapsible=True,
                        width="100%",
                        margin_top="12px",
                    ),
                    # Fully visible during generation
                    rx.box(
                        agent_log(AppState.agent_logs, AppState.is_generating),
                        margin_top="16px",
                    ),
                ),
            ),
            **glass_card_style,
            margin_bottom="24px",
        ),

        # Results
        rx.cond(
            AppState.generation_complete,
            rx.box(
                hero_banner(),
                rx.tabs.root(
                    rx.tabs.list(
                        rx.tabs.trigger("📊 Overview", value="overview"),
                        rx.tabs.trigger("⚖️ Comparables", value="comps"),
                        rx.tabs.trigger("📸 Condition", value="condition"),
                        rx.tabs.trigger("📦 Protest Packet", value="protest"),
                        rx.tabs.trigger("🐛 Debug", value="debug"),
                    ),
                    rx.tabs.content(tab_overview(), value="overview"),
                    rx.tabs.content(tab_comparables(), value="comps"),
                    rx.tabs.content(tab_condition(), value="condition"),
                    rx.tabs.content(tab_protest(), value="protest"),
                    rx.tabs.content(tab_debug(), value="debug"),
                    default_value="overview",
                ),
            ),
        ),

        **main_content_style,
    )
