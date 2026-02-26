"""Data table components for equity and sales comparables — dark theme."""
import reflex as rx
from texas_equity_ai.state import AppState
from texas_equity_ai.styles import (
    glass_card_style, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER, BG_ELEVATED, ACCENT, FONT_MONO, SUCCESS, DANGER,
    SHADOW_SM,
)


# ── Helpers ────────────────────────────────────────────────────────
def _cell(text_var, color=TEXT_SECONDARY, mono=False, bold=False) -> rx.Component:
    """Standard table cell."""
    return rx.table.cell(
        rx.text(
            text_var,
            font_size="0.8rem",
            color=color,
            font_family=FONT_MONO if mono else "inherit",
            font_weight="700" if bold else "400",
            white_space="nowrap",
        ),
    )


def _header(*titles) -> rx.Component:
    return rx.table.header(
        rx.table.row(
            *[rx.table.column_header_cell(
                rx.text(t, font_size="0.7rem", font_weight="700",
                        text_transform="uppercase", letter_spacing="0.5px",
                        color=TEXT_MUTED, white_space="nowrap"),
            ) for t in titles],
        ),
    )


# ── Equity Comp Table ──────────────────────────────────────────────
def _equity_row(comp: dict) -> rx.Component:
    """Render one equity comp row with all columns."""
    return rx.table.row(
        _cell(comp["address"].to(str), color=TEXT_PRIMARY, bold=True),
        _cell(comp["property_type"].to(str)),
        _cell(comp["appraised_value"].to(str), color=ACCENT, mono=True, bold=True),
        _cell(comp["market_value"].to(str), mono=True),
        _cell(comp["building_area"].to(str), mono=True),
        _cell(comp["year_built"].to(str)),
        _cell(comp["value_per_sqft"].to(str), mono=True),
        _cell(comp["similarity_score"].to(str)),
        _cell(comp["neighborhood_code"].to(str)),
        _cell(comp["comp_source"].to(str)),
        _hover={
            "background": "rgba(37, 99, 235, 0.05)",
            "box_shadow": SHADOW_SM,
            "transform": "translateY(-1px)",
            "transition": "all 0.2s ease",
            "cursor": "pointer"
        },
    )


def equity_comp_table() -> rx.Component:
    """Render equity comps table from AppState."""
    return rx.box(
        rx.heading(
            "⚖️ Equity Comparable Properties",
            size="4", color=TEXT_PRIMARY, margin_bottom="4px",
        ),
        rx.text(
            AppState.equity_comps.length().to(str) + " comparable properties found",
            font_size="0.85rem", color=TEXT_MUTED, margin_bottom="12px",
        ),
        rx.box(
            rx.table.root(
                _header(
                    "Address", "Type", "Appraised", "Market",
                    "Sq Ft", "Year", "$/SqFt", "Similarity", "Nbhd", "Source",
                ),
                rx.table.body(
                    rx.foreach(AppState.equity_comps, _equity_row),
                ),
                width="100%",
            ),
            overflow_x="auto",
            width="100%",
        ),
        **glass_card_style,
    )


# ── Sales Comp Table ──────────────────────────────────────────────
def _sales_row(comp: dict) -> rx.Component:
    """Render one sales comp row."""
    price = comp["Sale Price"].to(str)
    price_display = rx.cond(price.contains("$"), price, "$" + price)

    return rx.table.row(
        _cell(comp["Address"].to(str), color=TEXT_PRIMARY, bold=True),
        rx.table.cell(rx.text(
            price_display, font_size="0.8rem", color=ACCENT,
            font_family=FONT_MONO, font_weight="700", white_space="nowrap",
        )),
        _cell(comp["Sale Date"].to(str)),
        _cell(comp["SqFt"].to(str), mono=True),
        _cell(comp["Price/SqFt"].to(str), mono=True),
        _cell(comp["Year Built"].to(str)),
        _cell(comp["Distance"].to(str)),
        _hover={
            "background": "rgba(37, 99, 235, 0.05)",
            "box_shadow": SHADOW_SM,
            "transform": "translateY(-1px)",
            "transition": "all 0.2s ease",
            "cursor": "pointer"
        },
    )


def sales_comp_table() -> rx.Component:
    """Render sales comps table from AppState."""
    return rx.box(
        rx.heading(
            "💰 Sales Comparable Properties",
            size="4", color=TEXT_PRIMARY, margin_bottom="4px",
        ),
        rx.text(
            AppState.sales_comps.length().to(str) + " recent sales found",
            font_size="0.85rem", color=TEXT_MUTED, margin_bottom="12px",
        ),
        rx.box(
            rx.table.root(
                _header(
                    "Address", "Sale Price", "Sale Date",
                    "Sq Ft", "$/Sq Ft", "Year Built", "Distance",
                ),
                rx.table.body(
                    rx.foreach(AppState.sales_comps, _sales_row),
                ),
                width="100%",
            ),
            overflow_x="auto",
            width="100%",
        ),
        **glass_card_style,
    )
