"""Data table components for equity and sales comparables — dark theme."""
import reflex as rx
from texas_equity_ai.state import AppState
from texas_equity_ai.styles import (
    glass_card_style, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER, BG_ELEVATED, ACCENT, FONT_MONO,
)


def _equity_row(comp: dict) -> rx.Component:
    """Render one equity comp row with dark styling."""
    val = comp["appraised_value"].to(str)
    sqft = comp["building_area"].to(str)
    year = comp["year_built"].to(str)

    return rx.table.row(
        rx.table.cell(rx.text(comp["address"].to(str), font_size="0.85rem", color=TEXT_PRIMARY)),
        rx.table.cell(rx.text("$" + val, font_size="0.85rem", color=ACCENT, font_family=FONT_MONO, font_weight="600")),
        rx.table.cell(rx.text(sqft, font_size="0.85rem", color=TEXT_SECONDARY)),
        rx.table.cell(rx.text(year, font_size="0.85rem", color=TEXT_SECONDARY)),
    )


def equity_comp_table() -> rx.Component:
    """Render equity comps table from AppState."""
    return rx.box(
        rx.heading("⚖️ Equity Comparable Properties", size="4", color=TEXT_PRIMARY, margin_bottom="12px"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Address"),
                    rx.table.column_header_cell("Appraised Value"),
                    rx.table.column_header_cell("Sq Ft"),
                    rx.table.column_header_cell("Year Built"),
                ),
            ),
            rx.table.body(
                rx.foreach(AppState.equity_comps, _equity_row),
            ),
            width="100%",
        ),
        **glass_card_style,
    )


def _sales_row(comp: dict) -> rx.Component:
    """Render one sales comp row with dark styling."""
    val = comp["Sale Price"].to(str)
    date = comp["Sale Date"].to(str)
    sqft = comp["SqFt"].to(str)

    price_str = rx.cond(
        val.contains("$"),
        val,
        "$" + val
    )

    return rx.table.row(
        rx.table.cell(rx.text(comp["Address"].to(str), font_size="0.85rem", color=TEXT_PRIMARY)),
        rx.table.cell(rx.text(price_str, font_size="0.85rem", color=ACCENT, font_family=FONT_MONO, font_weight="600")),
        rx.table.cell(rx.text(date, font_size="0.85rem", color=TEXT_SECONDARY)),
        rx.table.cell(rx.text(sqft, font_size="0.85rem", color=TEXT_SECONDARY)),
    )


def sales_comp_table() -> rx.Component:
    """Render sales comps table from AppState."""
    return rx.box(
        rx.heading("💰 Sales Comparable Properties", size="4", color=TEXT_PRIMARY, margin_bottom="12px"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Address"),
                    rx.table.column_header_cell("Sale Price"),
                    rx.table.column_header_cell("Sale Date"),
                    rx.table.column_header_cell("Sq Ft"),
                ),
            ),
            rx.table.body(
                rx.foreach(AppState.sales_comps, _sales_row),
            ),
            width="100%",
        ),
        **glass_card_style,
    )
