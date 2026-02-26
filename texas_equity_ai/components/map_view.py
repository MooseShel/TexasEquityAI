"""Map component using Google Static Maps API as the primary approach.
reflex-map (React-Map-GL/MapLibre) is available as an upgrade path but
Google Static Maps is simpler and avoids JS interop issues for v1.
"""
import reflex as rx
import os
from texas_equity_ai.styles import card_style, TEXT_MUTED


def _static_map_url(
    points: list[dict],
    size: str = "640x400",
    zoom: int | None = None,
) -> str:
    """Build a Google Static Maps API URL with markers."""
    api_key = os.getenv("GOOGLE_STREET_VIEW_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    base = "https://maps.googleapis.com/maps/api/staticmap"

    markers = []
    for pt in points:
        lat, lon = pt.get("lat", 0), pt.get("lon", 0)
        color = pt.get("marker_color", "blue")
        label = pt.get("label", "")[:1].upper()
        markers.append(f"markers=color:{color}%7Clabel:{label}%7C{lat},{lon}")

    marker_str = "&".join(markers)
    zoom_str = f"&zoom={zoom}" if zoom else ""

    return f"{base}?size={size}{zoom_str}&maptype=roadmap&{marker_str}&key={api_key}"


def map_view(
    subject: dict | None = None,
    comps: list[dict] | None = None,
    subject_color: str = "red",
    comp_color: str = "blue",
    legend_comp_label: str = "Comparable Properties",
) -> rx.Component:
    """
    Render a map showing subject property and comparables.

    Args:
        subject: dict with keys lat, lon, address
        comps: list of dicts with lat, lon, address
        subject_color: marker color for subject
        comp_color: marker color for comps
    """
    if not subject and not comps:
        return rx.callout(
            "Map unavailable — could not geocode property addresses.",
            icon="info",
            color_scheme="blue",
        )

    points = []
    if subject:
        points.append({**subject, "marker_color": subject_color, "label": "S"})
    for c in (comps or []):
        if c.get("lat") and c.get("lon"):
            points.append({**c, "marker_color": comp_color, "label": "C"})

    if not points:
        return rx.callout(
            "Map unavailable — could not geocode property addresses.",
            icon="info",
            color_scheme="blue",
        )

    url = _static_map_url(points)

    return rx.box(
        rx.image(
            src=url,
            width="100%",
            border_radius="8px",
            alt="Property location map",
        ),
        rx.hstack(
            rx.box(width="12px", height="12px", border_radius="50%", background=subject_color),
            rx.text("Subject Property", font_size="0.85rem", color=TEXT_MUTED),
            rx.box(width="16px"),
            rx.box(width="12px", height="12px", border_radius="50%", background=comp_color),
            rx.text(legend_comp_label, font_size="0.85rem", color=TEXT_MUTED),
            margin_top="8px",
            spacing="2",
            align_items="center",
        ),
    )
