"""Multi-image gallery component — replaces st.image() + st.columns()."""
import reflex as rx
import os
from texas_equity_ai.styles import BORDER, RADIUS_SM


def image_gallery(image_paths: list[str], labels: list[str] | None = None) -> rx.Component:
    """Render a responsive image gallery with optional labels."""
    default_labels = ["Front", "Left 45°", "Right 45°"]
    if labels is None:
        labels = default_labels

    valid_images = []
    for i, path in enumerate(image_paths):
        if path:
            label = labels[i] if i < len(labels) else f"Angle {i + 1}"
            valid_images.append((path, label))

    if not valid_images:
        return rx.callout(
            "No Street View images available for this property.",
            icon="triangle_alert",
            color_scheme="yellow",
        )

    items = []
    for path, label in valid_images:
        items.append(
            rx.box(
                rx.image(
                    src=rx.get_upload_url(path) if not path.startswith("http") else path,
                    width="100%",
                    border_radius=RADIUS_SM,
                    border=f"1px solid {BORDER}",
                    object_fit="cover",
                    alt=label,
                ),
                rx.text(
                    label,
                    text_align="center",
                    font_size="0.85rem",
                    margin_top="4px",
                    color="#64748B",
                ),
            )
        )

    return rx.grid(
        *items,
        columns=rx.breakpoints(initial="1", sm="2", md=str(len(valid_images))),
        spacing="4",
        width="100%",
    )
