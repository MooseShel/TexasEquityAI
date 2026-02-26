"""File download component — replaces st.download_button()."""
import reflex as rx
from texas_equity_ai.styles import primary_button_style, secondary_button_style


def download_button(
    label: str,
    file_path: str,
    file_name: str = "",
    primary: bool = True,
    icon: str = "download",
) -> rx.Component:
    """
    Render a download button. In Reflex, we use rx.link pointing to 
    a backend API endpoint that serves the file.
    """
    style = primary_button_style if primary else secondary_button_style

    # Use the Reflex upload/download mechanism
    return rx.cond(
        file_path != "",
        rx.link(
            rx.button(
                rx.icon(icon, size=16),
                label,
                **style,
            ),
            href=file_path,
            is_external=True,
            download=file_name or True,
        ),
        rx.button(
            label,
            disabled=True,
            opacity="0.5",
            **style,
        ),
    )
