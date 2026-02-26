"""
Design system for Texas Equity AI — Premium dark theme with glassmorphism.
"""

# ── Colour palette — Light Theme ────────────────────────────────
BG_DARKEST = "#F8FAFC"
BG_DARK = "#F1F5F9"
BG_SURFACE = "#FFFFFF"
BG_ELEVATED = "#FFFFFF"
BG_CARD = "rgba(255, 255, 255, 0.8)"  # glass card base

PRIMARY = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
PRIMARY_GLOW = "rgba(37, 99, 235, 0.15)"
ACCENT = "#0EA5E9"
ACCENT_GLOW = "rgba(14, 165, 233, 0.15)"
GRADIENT_PRIMARY = "linear-gradient(135deg, #2563EB 0%, #0EA5E9 100%)"
GRADIENT_SUBTLE = "linear-gradient(135deg, rgba(37,99,235,0.08) 0%, rgba(14,165,233,0.05) 100%)"

TEXT_PRIMARY = "#0F172A"
TEXT_SECONDARY = "#475569"
TEXT_MUTED = "#64748B"
TEXT_MAIN = TEXT_PRIMARY  

BORDER = "rgba(15, 23, 42, 0.1)"
BORDER_GLOW = "rgba(37, 99, 235, 0.2)"
SURFACE = BG_SURFACE  

SUCCESS = "#059669"
SUCCESS_BG = "rgba(5, 150, 105, 0.1)"
WARNING = "#D97706"
WARNING_BG = "rgba(217, 119, 6, 0.1)"
DANGER = "#DC2626"
DANGER_BG = "rgba(220, 38, 38, 0.1)"
INFO_BG = "rgba(37, 99, 235, 0.08)"
INFO_TEXT = "#2563EB"
BACKGROUND = BG_DARKEST

RADIUS = "16px"
RADIUS_SM = "10px"
RADIUS_LG = "20px"
SHADOW_SM = "0 2px 4px rgba(15, 23, 42, 0.05)"
SHADOW_MD = "0 4px 12px rgba(15, 23, 42, 0.08)"
SHADOW_GLOW = f"0 0 15px {PRIMARY_GLOW}, 0 4px 12px rgba(15, 23, 42, 0.05)"

# ── Font stack ──────────────────────────────────────────────────────
FONT_FAMILY = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
FONT_SERIF = "'Playfair Display', Georgia, serif"
FONT_MONO = "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace"
GOOGLE_FONT_URL = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&family=Playfair+Display:wght@600;700&display=swap"

# ── Reusable style dictionaries ─────────────────────────────────────

base_page_style = {
    "font_family": FONT_FAMILY,
    "background": BG_DARKEST,
    "color": TEXT_PRIMARY,
    "min_height": "100vh",
    "display": "flex",
    "flex_direction": "column",
    "align_items": "center",
}

sidebar_style = {
    "width": "320px",
    "min_width": "320px",
    "background": f"linear-gradient(180deg, {BG_DARK} 0%, {BG_DARKEST} 100%)",
    "border_right": f"1px solid {BORDER}",
    "padding": "24px",
    "overflow_y": "auto",
    "height": "100vh",
    "position": "fixed",
    "left": "0",
    "top": "0",
}

main_content_style = {
    "flex": "1",
    "max_width": "1200px",
    "width": "100%",
}

card_style = {
    "background": BG_CARD,
    "backdrop_filter": "blur(12px)",
    "border": f"1px solid {BORDER}",
    "border_radius": RADIUS,
    "padding": "24px",
    "box_shadow": SHADOW_SM,
    "transition": "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
    "_hover": {
        "box_shadow": SHADOW_MD,
        "border": f"1px solid {BORDER_GLOW}",
    },
}

glass_card_style = {
    "background": "rgba(255, 255, 255, 0.6)",
    "backdrop_filter": "blur(16px)",
    "border": f"1px solid {BORDER}",
    "border_radius": RADIUS,
    "padding": "20px",
    "box_shadow": SHADOW_SM,
    "transition": "all 0.3s ease",
    "_hover": {
        "box_shadow": SHADOW_GLOW,
        "border": f"1px solid {BORDER_GLOW}",
        "transform": "translateY(-2px)",
    },
}

metric_card_style = {
    "background": BG_CARD,
    "backdrop_filter": "blur(12px)",
    "border": f"1px solid {BORDER}",
    "border_top": f"3px solid transparent",
    "border_image": f"{GRADIENT_PRIMARY} 1",
    "border_image_slice": "1",
    "border_radius": RADIUS,
    "padding": "20px",
    "box_shadow": SHADOW_SM,
    "transition": "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
    "_hover": {
        "transform": "translateY(-3px)",
        "box_shadow": SHADOW_GLOW,
    },
}

primary_button_style = {
    "background": GRADIENT_PRIMARY,
    "color": "white",
    "border": "none",
    "border_radius": RADIUS_SM,
    "font_weight": "600",
    "min_height": "44px",
    "width": "100%",
    "cursor": "pointer",
    "transition": "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
    "box_shadow": f"0 4px 14px {PRIMARY_GLOW}",
    "_hover": {
        "transform": "translateY(-2px)",
        "box_shadow": SHADOW_GLOW,
        "filter": "brightness(1.1)",
    },
}

secondary_button_style = {
    "background": "rgba(59, 130, 246, 0.08)",
    "color": ACCENT,
    "border": f"1px solid rgba(59, 130, 246, 0.25)",
    "border_radius": RADIUS_SM,
    "font_weight": "600",
    "min_height": "40px",
    "cursor": "pointer",
    "transition": "all 0.3s ease",
    "_hover": {
        "background": "rgba(59, 130, 246, 0.15)",
        "border": f"1px solid {PRIMARY}",
        "box_shadow": f"0 0 12px {PRIMARY_GLOW}",
    },
}

input_style = {
    "border_radius": RADIUS_SM,
    "border": f"1px solid {BORDER}",
    "background": BG_ELEVATED,
    "color": TEXT_PRIMARY,
    "font_size": "16px",
    "width": "100%",
    "_placeholder": {
        "color": "rgba(255, 255, 255, 0.5)",
    },
    "_focus": {
        "border": f"1px solid {PRIMARY}",
        "box_shadow": f"0 0 0 3px {PRIMARY_GLOW}",
    },
}

badge_strong = {
    "background": SUCCESS_BG,
    "color": SUCCESS,
    "padding": "4px 14px",
    "border_radius": "20px",
    "font_weight": "600",
    "font_size": "0.85rem",
    "border": f"1px solid rgba(16, 185, 129, 0.3)",
}

badge_moderate = {
    "background": WARNING_BG,
    "color": WARNING,
    "padding": "4px 14px",
    "border_radius": "20px",
    "font_weight": "600",
    "font_size": "0.85rem",
    "border": f"1px solid rgba(245, 158, 11, 0.3)",
}

badge_weak = {
    "background": DANGER_BG,
    "color": DANGER,
    "padding": "4px 14px",
    "border_radius": "20px",
    "font_weight": "600",
    "font_size": "0.85rem",
    "border": f"1px solid rgba(239, 68, 68, 0.3)",
}

tab_style = {
    "font_weight": "600",
    "padding": "8px 16px",
    "cursor": "pointer",
    "color": TEXT_SECONDARY,
    "border_radius": RADIUS_SM,
    "transition": "all 0.2s ease",
    "_hover": {
        "color": TEXT_PRIMARY,
        "background": "rgba(59, 130, 246, 0.08)",
    },
}

hero_banner_style = {
    "background": f"linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)",
    "color": "white",
    "padding": "28px",
    "border_radius": RADIUS_LG,
    "margin_bottom": "20px",
    "border": f"1px solid {BORDER}",
    "box_shadow": SHADOW_MD,
    "position": "relative",
    "overflow": "hidden",
}

divider_style = {
    "margin_y": "20px",
    "border_color": BORDER,
}

# ── Terminal / Log styles ───────────────────────────────────────────
terminal_style = {
    "background": "#0A0E17",
    "border": f"1px solid rgba(16, 185, 129, 0.2)",
    "border_radius": RADIUS,
    "padding": "16px",
    "font_family": FONT_MONO,
    "font_size": "0.85rem",
    "color": "#4ADE80",
    "max_height": "300px",
    "overflow_y": "auto",
}

# ── Table styles ────────────────────────────────────────────────────
table_header_style = {
    "background": BG_ELEVATED,
    "color": TEXT_SECONDARY,
    "font_weight": "600",
    "font_size": "0.75rem",
    "text_transform": "uppercase",
    "letter_spacing": "0.5px",
}

table_row_style = {
    "border_bottom": f"1px solid {BORDER}",
    "transition": "background 0.2s ease",
    "_hover": {
        "background": "rgba(59, 130, 246, 0.05)",
    },
}

table_row_alt_style = {
    **table_row_style,
    "background": "rgba(15, 23, 42, 0.3)",
}

# ── Severity color map ──────────────────────────────────────────────
SEVERITY_COLORS = {
    "High": DANGER,
    "Medium": WARNING,
    "Low": SUCCESS,
}

SEVERITY_EMOJI = {
    "High": "🔴",
    "Medium": "🟡",
    "Low": "🟢",
}
