"""
Main dashboard page — dark-themed premium UI.
Handles account input, protest generation, and results display (5 tabs).
"""
import reflex as rx
import json
from texas_equity_ai.state import AppState, DISTRICT_OPTIONS
from texas_equity_ai.styles import (
    main_content_style, card_style, glass_card_style, hero_banner_style,
    primary_button_style, secondary_button_style, input_style,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER, BORDER_GLOW, RADIUS, RADIUS_SM, RADIUS_LG,
    BG_SURFACE, BG_ELEVATED, BG_CARD,
    SUCCESS, SUCCESS_BG, WARNING, WARNING_BG, DANGER, DANGER_BG,
    INFO_BG, INFO_TEXT, SEVERITY_COLORS, SEVERITY_EMOJI,
    PRIMARY, PRIMARY_GLOW, ACCENT, GRADIENT_PRIMARY, GRADIENT_SUBTLE,
    FONT_MONO, FONT_SERIF, SHADOW_SM, SHADOW_MD, SHADOW_GLOW,
    terminal_style,
)
from texas_equity_ai.components.metric_card import metric_card
from texas_equity_ai.components.property_card import property_card
from texas_equity_ai.components.comp_table import equity_comp_table, sales_comp_table
from texas_equity_ai.components.agent_log import agent_log
from texas_equity_ai.components.map_view import map_view
from texas_equity_ai.components.image_gallery import image_gallery
from texas_equity_ai.components.skeleton_loader import skeleton_loader


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
            # AI Win Predictor
            _kpi_card("🤖", "AI WIN PREDICTOR", AppState.fmt_win_probability, color="#34D399"),
            columns=rx.breakpoints(initial="1", sm="2", md="5"),
            spacing="3",
            position="relative",
        ),
        # ── Methodology Badges ──────────────────────────────────────────
        rx.cond(
            AppState.adjustment_method_label != "",
            rx.hstack(
                rx.badge(
                    rx.icon("sparkles", size=12),
                    " Adjustments: ",
                    AppState.adjustment_method_label,
                    color_scheme="purple",
                    variant="surface",
                    size="1",
                ),
                rx.cond(
                    AppState.win_predictor_model != "",
                    rx.badge(
                        rx.icon("brain", size=12),
                        " Win Predictor: Hybrid ML (544K HCAD records)",
                        color_scheme="green",
                        variant="surface",
                        size="1",
                    ),
                ),
                spacing="2",
                margin_top="12px",
                flex_wrap="wrap",
                position="relative",
            ),
        ),
        # ── Equity Analysis Warning ─────────────────────────────────────
        rx.cond(
            (AppState.equity_analysis_status == "failed") | (AppState.equity_analysis_status == "no_gap"),
            rx.callout(
                AppState.equity_analysis_reason,
                icon="alert_triangle",
                color_scheme="yellow",
                margin_top="10px",
                size="1",
                position="relative",
            ),
        ),
        # ── Legal Disclaimer ────────────────────────────────────────────
        rx.text(
            "This analysis is for property tax protest purposes only. It does not constitute "
            "a certified appraisal under USPAP or Texas Occupations Code Ch. 1103. "
            "AI-predicted outcomes are based on historical data and do not guarantee results.",
            font_size="0.6rem",
            color="rgba(255,255,255,0.3)",
            margin_top="10px",
            position="relative",
            line_height="1.3",
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
            font_size=["1rem", "1.1rem", "1.3rem"],
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
        rx.heading("📊 Property Overview", size="7", font_family=FONT_SERIF, margin_bottom="24px", color=TEXT_PRIMARY),
        # Property details card
        rx.cond(
            AppState.property_data.contains("address"),
            rx.grid(
                rx.cond(
                    AppState.evidence_image_path != "",
                    rx.box(
                        rx.image(
                            src=rx.get_upload_url(AppState.evidence_image_path),
                            width="100%",
                            height="260px",
                            object_fit="cover",
                            border_radius=RADIUS_SM,
                            border=f"1px solid {BORDER}",
                            box_shadow=SHADOW_SM,
                        ),
                        rx.text(
                            "📷 Google Street View — imagery may not reflect current property condition or recent construction.",
                            font_size="0.7rem",
                            color=TEXT_MUTED,
                            font_style="italic",
                            margin_top="4px",
                            text_align="center",
                        ),
                    ),
                ),
                property_card(),
                columns=rx.cond(AppState.evidence_image_path != "", rx.breakpoints(initial="1", md="2"), "1"),
                spacing="6",
                align_items="stretch",
            )
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
        width="100%",
        overflow_x="hidden",
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


# ── Tab: Equity Comps ────────────────────────────────────────────
def tab_equity_comps() -> rx.Component:
    return rx.box(
        rx.heading("⚖️ Equity Comparables", size="7", font_family=FONT_SERIF, margin_bottom="24px", color=TEXT_PRIMARY),
        # Assessment summary callout
        rx.cond(
            AppState.equity_comps.length() > 0,
            rx.box(
                # Metrics row
                rx.hstack(
                    rx.box(
                        rx.text("Justified Value", font_size="0.75rem", color=TEXT_MUTED),
                        rx.text(
                            AppState.fmt_justified,
                            font_size="1.4rem", font_weight="700", color=TEXT_PRIMARY, font_family=FONT_MONO,
                        ),
                        flex="1",
                    ),
                    rx.box(
                        rx.text("Equity Savings", font_size="0.75rem", color=TEXT_MUTED),
                        rx.text(
                            AppState.fmt_equity_savings,
                            font_size="1.4rem", font_weight="700", color=SUCCESS, font_family=FONT_MONO,
                        ),
                        flex="1",
                    ),
                    rx.box(
                        rx.text("Est. Tax Savings", font_size="0.75rem", color=TEXT_MUTED),
                        rx.text(
                            AppState.fmt_tax_savings,
                            font_size="1.4rem", font_weight="700", color=ACCENT, font_family=FONT_MONO,
                        ),
                        flex="1",
                    ),
                    flex_wrap="wrap",
                    spacing="4",
                    width="100%",
                    margin_bottom="12px",
                ),
                # Contextual message — equity analysis status
                rx.cond(
                    AppState.equity_analysis_status == "success",
                    rx.callout(
                        "Equity over-assessment detected! Your appraised value exceeds the justified value floor of comparable properties. This supports a protest under Texas Tax Code §41.43(b)(1).",
                        icon="circle_check",
                        color_scheme="green",
                        margin_bottom="16px",
                    ),
                    rx.cond(
                        AppState.equity_analysis_status == "failed",
                        rx.callout(
                            rx.text(
                                "⚠️ Equity analysis could not be completed: ",
                                rx.text.strong(AppState.equity_analysis_reason),
                                " The equity target shown equals the current appraised value as a fallback.",
                            ),
                            icon="alert_triangle",
                            color_scheme="yellow",
                            margin_bottom="16px",
                        ),
                        rx.callout(
                            "No equity over-assessment found. Comparable properties support the current appraised value. The equity argument does not support a reduction at this time.",
                            icon="info",
                            color_scheme="blue",
                            margin_bottom="16px",
                        ),
                    ),
                ),
                # ML Methodology note
                rx.cond(
                    AppState.adjustment_method_label != "",
                    rx.callout(
                        rx.text(
                            "📊 Adjustment rates dynamically derived via ",
                            rx.text.strong(AppState.adjustment_method_label),
                            " from locally similar properties. This methodology produces market-derived "
                            "adjustment rates per USPAP Standards Rule 1-4.",
                        ),
                        icon="sparkles",
                        color_scheme="purple",
                        margin_bottom="16px",
                        size="1",
                    ),
                ),
                equity_comp_table(),
                margin_bottom="20px",
                width="100%",
                overflow="hidden",
            ),
            rx.callout(
                "No equity comparable data available yet.",
                icon="info",
                color_scheme="blue",
            ),
        ),
        # Map below table
        rx.cond(
            AppState.equity_map_url != "",
            rx.box(
                rx.heading("🗺️ Property & Comp Locations", size="4", color=TEXT_PRIMARY, margin_bottom="8px"),
                rx.image(
                    src=AppState.equity_map_url,
                    width="100%",
                    max_width="100%",
                    height="auto",
                    border_radius=RADIUS_SM,
                    alt="Property location map",
                    border=f"1px solid {BORDER}",
                ),
                rx.hstack(
                    rx.box(width="12px", height="12px", border_radius="50%", background="#EF4444"),
                    rx.text("Subject Property", font_size="0.8rem", color=TEXT_SECONDARY),
                    rx.box(width="16px"),
                    rx.box(width="12px", height="12px", border_radius="50%", background=PRIMARY),
                    rx.text("Comparable Properties", font_size="0.8rem", color=TEXT_SECONDARY),
                    margin_top="8px",
                    spacing="2",
                    align_items="center",
                    flex_wrap="wrap",
                ),
                **glass_card_style,
                width="100%",
                overflow="hidden",
            ),
        ),
        padding_top="8px",
        width="100%",
        overflow_x="hidden",
    )


# ── Tab: Sales Comps ─────────────────────────────────────────────
def tab_sales_comps() -> rx.Component:
    return rx.box(
        rx.heading("💰 Sales Comparables (Adjusted)", size="7", font_family=FONT_SERIF, margin_bottom="24px", color=TEXT_PRIMARY),
        # Assessment summary callout
        rx.cond(
            AppState.sales_comps.length() > 0,
            rx.box(
                # Metrics row
                rx.hstack(
                    rx.box(
                        rx.text("Median Sale Price", font_size="0.75rem", color=TEXT_MUTED),
                        rx.text(
                            AppState.fmt_sales_median_price,
                            font_size="1.4rem", font_weight="700", color=TEXT_PRIMARY, font_family=FONT_MONO,
                        ),
                        flex="1",
                    ),
                    rx.box(
                        rx.text("Comps Found", font_size="0.75rem", color=TEXT_MUTED),
                        rx.text(
                            AppState.sales_comps.length().to(str),
                            font_size="1.4rem", font_weight="700", color=TEXT_PRIMARY, font_family=FONT_MONO,
                        ),
                        flex="1",
                    ),
                    rx.box(
                        rx.text("Est. Tax Savings", font_size="0.75rem", color=TEXT_MUTED),
                        rx.text(
                            AppState.fmt_tax_savings,
                            font_size="1.4rem", font_weight="700", color=ACCENT, font_family=FONT_MONO,
                        ),
                        flex="1",
                    ),
                    flex_wrap="wrap",
                    spacing="4",
                    width="100%",
                    margin_bottom="12px",
                ),
                # Contextual message
                rx.cond(
                    AppState.sales_savings > 0,
                    rx.callout(
                        "Market over-appraisal detected! Your appraised value exceeds the median sale price of comparable sales. This supports a protest under Texas Tax Code §41.43(b)(3) and §23.01.",
                        icon="circle_check",
                        color_scheme="green",
                        margin_bottom="16px",
                    ),
                    rx.callout(
                        "No market over-appraisal found. Your appraised value is at or below the median sale price of comparable properties. Sales data does not independently support a reduction.",
                        icon="info",
                        color_scheme="blue",
                        margin_bottom="16px",
                    ),
                ),
                # Sales adjustment methodology note
                rx.callout(
                    "Sale prices have been professionally adjusted for size, depreciation, grade, "
                    "and land differences using ML-derived rates. Properties were enriched via "
                    "Supabase database cross-reference for complete adjustment data per USPAP SR 1-4.",
                    icon="sparkles",
                    color_scheme="purple",
                    margin_bottom="16px",
                    size="1",
                ),
                sales_comp_table(),
                margin_bottom="20px",
                width="100%",
                overflow="hidden",
            ),
            rx.callout(
                "No sales comparable data available yet.",
                icon="info",
                color_scheme="blue",
            ),
        ),
        # Map below table
        rx.cond(
            AppState.sales_map_url != "",
            rx.box(
                rx.heading("🗺️ Property & Comp Locations", size="4", color=TEXT_PRIMARY, margin_bottom="8px"),
                rx.image(
                    src=AppState.sales_map_url,
                    width="100%",
                    max_width="100%",
                    height="auto",
                    border_radius=RADIUS_SM,
                    alt="Property location map",
                    border=f"1px solid {BORDER}",
                ),
                rx.hstack(
                    rx.box(width="12px", height="12px", border_radius="50%", background="#EF4444"),
                    rx.text("Subject Property", font_size="0.8rem", color=TEXT_SECONDARY),
                    rx.box(width="16px"),
                    rx.box(width="12px", height="12px", border_radius="50%", background=PRIMARY),
                    rx.text("Comparable Properties", font_size="0.8rem", color=TEXT_SECONDARY),
                    margin_top="8px",
                    spacing="2",
                    align_items="center",
                    flex_wrap="wrap",
                ),
                **glass_card_style,
                width="100%",
                overflow="hidden",
            ),
        ),
        padding_top="8px",
        width="100%",
        overflow_x="hidden",
    )


# ── Tab: Condition ─────────────────────────────────────────────────
def tab_condition() -> rx.Component:
    return rx.box(
        rx.heading("📸 Condition Assessment", size="7", font_family=FONT_SERIF, margin_bottom="24px", color=TEXT_PRIMARY),
        # Status callout at top (like other tabs)
        rx.cond(
            AppState.condition_issues.length() > 0,
            rx.callout(
                "Condition issues detected. Deductions may apply based on physical deficiencies identified via street view analysis.",
                icon="triangle_alert",
                color_scheme="orange",
                margin_bottom="16px",
            ),
            rx.callout(
                "No condition issues detected. Property appears in good condition.",
                icon="circle_check",
                color_scheme="green",
                margin_bottom="16px",
            ),
        ),

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

        # Image gallery
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
        padding_top="8px",
        width="100%",
        overflow_x="hidden",
    )


def _street_view_image(path: rx.Var[str]) -> rx.Component:
    """Render a single street view image for rx.foreach."""
    return rx.box(
        rx.image(
            src=rx.get_upload_url(path),
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
        rx.text(issue["description"].to(str), color=TEXT_SECONDARY, font_size="0.85rem", margin_top="4px"),
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
        rx.heading("📦 Protest Packet", size="7", font_family=FONT_SERIF, margin_bottom="24px", color=TEXT_PRIMARY),
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
                href=rx.get_upload_url(AppState.pdf_path),
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

        # Pitch Deck
        rx.hstack(
            rx.button(
                "📄 Generate Pitch Deck",
                on_click=AppState.generate_pitch_deck,
                **secondary_button_style,
                flex="1",
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
                    flex="1",
                ),
            ),
            spacing="3",
            width="100%",
            margin_top="12px",
            margin_bottom="16px",
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
        rx.accordion.root(
            rx.accordion.item(
                header="Raw Property Data",
                content=rx.box(
                    rx.text(
                        AppState.debug_property_json,
                        font_family=FONT_MONO, font_size="0.75rem", color=TEXT_SECONDARY,
                        white_space="pre-wrap", word_break="break-word",
                    ),
                    background=BG_ELEVATED, padding="12px", border_radius=RADIUS_SM,
                    max_height="400px", overflow_y="auto",
                ),
            ),
            rx.accordion.item(
                header="Raw Equity Data",
                content=rx.box(
                    rx.text(
                        AppState.debug_equity_json,
                        font_family=FONT_MONO, font_size="0.75rem", color=TEXT_SECONDARY,
                        white_space="pre-wrap", word_break="break-word",
                    ),
                    background=BG_ELEVATED, padding="12px", border_radius=RADIUS_SM,
                    max_height="400px", overflow_y="auto",
                ),
            ),
            rx.accordion.item(
                header="Vision Detections",
                content=rx.box(
                    rx.text(
                        AppState.debug_vision_json,
                        font_family=FONT_MONO, font_size="0.75rem", color=TEXT_SECONDARY,
                        white_space="pre-wrap", word_break="break-word",
                    ),
                    background=BG_ELEVATED, padding="12px", border_radius=RADIUS_SM,
                    max_height="400px", overflow_y="auto",
                ),
            ),
            collapsible=True,
            width="100%",
        ),
        padding_top="8px",
        width="100%",
    )


# ── Monitor Tab ────────────────────────────────────────────────────
def tab_monitor() -> rx.Component:
    """Assessment monitor + anomaly scanner tab."""
    return rx.box(
        rx.hstack(
            # Anomaly Scanner
            rx.box(
                rx.heading("🔍 Anomaly Scanner", size="4", color=TEXT_PRIMARY, margin_bottom="8px"),
                rx.text("Find over-assessed properties in a neighborhood", font_size="0.85rem", color=TEXT_MUTED, margin_bottom="12px"),
                rx.input(
                    placeholder="Neighborhood code (e.g. 2604.71)",
                    value=AppState.scan_nbhd_code,
                    on_change=AppState.set_scan_nbhd_code,
                    **input_style,
                    margin_bottom="8px",
                ),
                rx.select(
                    DISTRICT_OPTIONS,
                    value=AppState.district_name,
                    on_change=AppState.set_district,
                    width="100%",
                    margin_bottom="8px",
                ),
                rx.button(
                    "📊 Run Scan",
                    on_click=AppState.run_anomaly_scan,
                    **secondary_button_style,
                    width="100%",
                ),
                # Scan results
                rx.cond(
                    AppState.scan_flagged.length() > 0,
                    rx.box(
                        # Stats summary
                        rx.hstack(
                            rx.text(
                                "🏘️ " + AppState.scan_stats["property_count"].to(str) + " properties scanned",
                                font_size="0.85rem", color=TEXT_SECONDARY, font_weight="600",
                            ),
                            rx.text(
                                "🚩 " + AppState.scan_flagged.length().to(str) + " flagged",
                                font_size="0.85rem", color=DANGER, font_weight="600",
                            ),
                            rx.text(
                                "Median: $" + AppState.scan_stats["median_pps"].to(str) + "/sqft",
                                font_size="0.85rem", color=ACCENT, font_weight="600",
                            ),
                            spacing="4",
                            flex_wrap="wrap",
                            margin_top="12px",
                            margin_bottom="8px",
                        ),
                        # Flagged properties table
                        rx.box(
                            rx.table.root(
                                rx.table.header(
                                    rx.table.row(
                                        rx.table.column_header_cell("Address", color=TEXT_PRIMARY),
                                        rx.table.column_header_cell("$/SqFt", color=TEXT_PRIMARY),
                                        rx.table.column_header_cell("Z-Score", color=TEXT_PRIMARY),
                                        rx.table.column_header_cell("Over-Assessment", color=TEXT_PRIMARY),
                                    ),
                                ),
                                rx.table.body(
                                    rx.foreach(AppState.scan_flagged, _scan_row),
                                ),
                                width="100%",
                            ),
                            max_height="300px",
                            overflow_y="auto",
                        ),
                    ),
                ),
                **glass_card_style,
                flex="1",
            ),
            # Assessment Monitor
            rx.box(
                rx.heading("🔔 Assessment Monitor", size="4", color=TEXT_PRIMARY, margin_bottom="8px"),
                rx.text("Track annual assessment changes for properties", font_size="0.85rem", color=TEXT_MUTED, margin_bottom="12px"),
                rx.input(
                    placeholder="Account (e.g. 0660460360030)",
                    value=AppState.watch_account,
                    on_change=AppState.set_watch_account,
                    **input_style,
                    margin_bottom="8px",
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
                            font_weight="600", font_size="0.85rem", color=ACCENT,
                            margin_top="12px", margin_bottom="8px",
                        ),
                        rx.foreach(AppState.watch_list, _watch_item),
                        rx.button(
                            "🔄 Refresh All",
                            on_click=AppState.refresh_watch_list,
                            **secondary_button_style,
                            width="100%",
                            margin_top="8px",
                        ),
                    ),
                ),
                **glass_card_style,
                flex="1",
            ),
            spacing="4",
            width="100%",
            align_items="flex-start",
            flex_direction=["column", "column", "row"],
        ),
        padding_top="8px",
        width="100%",
    )


def _watch_item(watch: dict) -> rx.Component:
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


def _scan_row(item: dict) -> rx.Component:
    """Render one flagged property row in the anomaly scanner results."""
    return rx.table.row(
        rx.table.cell(
            rx.text(item["address"].to(str), font_size="0.8rem", color=TEXT_PRIMARY, font_weight="600"),
        ),
        rx.table.cell(
            rx.text("$" + item["pps"].to(str), font_size="0.8rem", color=ACCENT, font_family=FONT_MONO),
        ),
        rx.table.cell(
            rx.text(item["z_score"].to(str), font_size="0.8rem", color=DANGER, font_family=FONT_MONO, font_weight="700"),
        ),
        rx.table.cell(
            rx.text("$" + item["estimated_over_assessment"].to(int).to(str), font_size="0.8rem", color=DANGER, font_family=FONT_MONO),
        ),
        _hover={"background": "rgba(239, 68, 68, 0.06)"},
    )


# ── Main dashboard page ───────────────────────────────────────────
def dashboard() -> rx.Component:
    """The main dashboard page — full-width, no sidebar."""
    return rx.box(
        # Header
        rx.hstack(
            rx.image(src="/logo.webp", width=["36px", "48px"], border_radius=RADIUS_SM),
            rx.box(
                rx.heading("Texas Equity AI", size="6", color=TEXT_PRIMARY, margin_bottom="0px", font_size=["1.2rem", "1.2rem", "1.5rem"]),
                rx.text("AI-powered property tax protest automation", color=TEXT_MUTED, font_size="0.85rem"),
            ),
            spacing="3",
            align_items="center",
            margin_bottom="24px",
        ),

        # Input section
        rx.box(
            # District + Account input row
            rx.hstack(
                rx.select(
                    DISTRICT_OPTIONS,
                    value=AppState.district_name,
                    on_change=AppState.set_district,
                    width=["100%", "100%", "160px"],
                ),
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
                        rx.hstack(
                            rx.spinner(size="2"),
                            rx.text("Generating..."),
                            spacing="2",
                            align_items="center",
                        ),
                        rx.hstack(
                            rx.icon("zap", size=16),
                            rx.text("Generate"),
                            spacing="2",
                            align_items="center",
                        ),
                    ),
                    on_click=AppState.start_generate,
                    loading=AppState.is_generating,
                    disabled=AppState.is_generating,
                    background=rx.cond(AppState.is_generating, "rgba(59, 130, 246, 0.5)", GRADIENT_PRIMARY),
                    color="white",
                    border="none",
                    border_radius=RADIUS_SM,
                    font_weight="700",
                    min_height="44px",
                    cursor=rx.cond(AppState.is_generating, "wait", "pointer"),
                    width="auto",
                    min_width="140px",
                    box_shadow=f"0 4px 14px {PRIMARY_GLOW}",
                    opacity=rx.cond(AppState.is_generating, "0.7", "1"),
                    _hover={
                        "transform": "translateY(-2px)",
                        "box_shadow": SHADOW_GLOW,
                        "filter": "brightness(1.1)",
                    },
                    _active={
                        "transform": "scale(0.95)",
                        "box_shadow": "none",
                    },
                ),
                # ── Cancel Search Button ──
                rx.cond(
                    AppState.is_generating,
                    rx.button(
                        rx.hstack(
                            rx.icon("x", size=16),
                            rx.text("Abort"),
                            spacing="2",
                            align_items="center",
                        ),
                        on_click=AppState.cancel_analysis,
                        background=DANGER_BG,
                        color=DANGER,
                        border=f"1px solid {DANGER}",
                        border_radius=RADIUS_SM,
                        font_weight="700",
                        min_height="44px",
                        cursor="pointer",
                        width="auto",
                        _hover={
                            "background": "rgba(239, 68, 68, 0.2)",
                            "transform": "translateY(-2px)",
                        },
                        _active={"transform": "scale(0.95)"},
                    ),
                ),
                width="100%",
                spacing="3",
                flex_direction=["column", "column", "row"],
                align_items=["stretch", "stretch", "center"],
            ),

            # Advanced Options accordion
            rx.accordion.root(
                rx.accordion.item(
                    header="⚙️ Advanced Options",
                    content=rx.box(
                        rx.hstack(
                            # Manual override fields
                            rx.box(
                                rx.text("Address Override", font_size="0.75rem", color="white", margin_bottom="2px"),
                                rx.input(
                                    placeholder="Override address",
                                    value=AppState.manual_address,
                                    on_change=AppState.set_manual_address,
                                    **input_style,
                                ),
                                flex="1",
                            ),
                            rx.box(
                                rx.text("Appraised Value", font_size="0.75rem", color="white", margin_bottom="2px"),
                                rx.input(
                                    placeholder="0",
                                    value=AppState.manual_value.to(str),
                                    on_change=AppState.set_manual_value,
                                    type="number",
                                    **input_style,
                                ),
                                flex="1",
                            ),
                            rx.box(
                                rx.text("Building Area (sqft)", font_size="0.75rem", color="white", margin_bottom="2px"),
                                rx.input(
                                    placeholder="0",
                                    value=AppState.manual_area.to(str),
                                    on_change=AppState.set_manual_area,
                                    type="number",
                                    **input_style,
                                ),
                                flex="1",
                            ),
                            # Tax rate + force fresh
                            rx.box(
                                rx.text("Tax Rate: " + AppState.tax_rate.to(str) + "%", font_size="0.75rem", color="white", margin_bottom="2px"),
                                rx.slider(
                                    value=[AppState.tax_rate],
                                    min=1.0,
                                    max=4.0,
                                    step=0.1,
                                    on_value_commit=AppState.set_tax_rate,
                                    width="100%",
                                ),
                                flex="1",
                            ),
                            rx.box(
                                rx.text(" ", font_size="0.75rem", margin_bottom="2px"),
                                rx.hstack(
                                    rx.switch(
                                        checked=AppState.force_fresh,
                                        on_change=AppState.toggle_force_fresh,
                                        size="1",
                                    ),
                                    rx.text("Force fresh", font_size="0.8rem", color="white"),
                                    spacing="2",
                                    align_items="center",
                                    min_height="36px",
                                ),
                                width="auto",
                            ),
                            spacing="3",
                            width="100%",
                            align_items="flex-end",
                            flex_wrap="wrap",
                        ),
                        padding="8px 0",
                    ),
                ),
                collapsible=True,
                width="100%",
                margin_top="8px",
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

        # Loading Skeleton
        rx.cond(
            AppState.is_generating,
            skeleton_loader(),
        ),

        # Results
        rx.cond(
            AppState.generation_complete,
            rx.box(
                hero_banner(),
                rx.vstack(
                    tab_overview(),
                    rx.divider(margin_y="0", border_color=BORDER),
                    tab_equity_comps(),
                    rx.divider(margin_y="0", border_color=BORDER),
                    tab_sales_comps(),
                    rx.divider(margin_y="0", border_color=BORDER),
                    tab_condition(),
                    rx.divider(margin_y="0", border_color=BORDER),
                    tab_protest(),
                    rx.divider(margin_y="0", border_color=BORDER),
                    rx.accordion.root(
                        rx.accordion.item(
                            header=rx.hstack(
                                rx.icon("wrench", size=18, color=TEXT_SECONDARY),
                                rx.text("Administrative & Debug Tools", font_weight="600"),
                                spacing="2",
                                align_items="center",
                            ),
                            content=rx.vstack(
                                tab_monitor(),
                                tab_debug(),
                                spacing="4",
                            ),
                        ),
                        collapsible=True,
                        width="100%",
                        margin_top="0",
                    ),
                    width="100%",
                    spacing="4",
                ),
            ),
        ),

        **main_content_style,
    )
