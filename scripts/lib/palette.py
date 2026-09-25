"""Series palette. Hex values come straight from the episode brief."""

HEX = {
    # Bolt
    "bolt_black": "#151517",
    "bolt_white": "#EDEAE3",
    "bolt_tan": "#C7813A",
    "bolt_eye": "#6B3A1A",
    "tongue": "#E8788A",
    "hardhat": "#F5B51B",
    "rams_orange": "#F55314",
    "reflective": "#C9CCD1",
    # Mittens
    "tabby": "#E8872F",
    "tabby_stripe": "#C4621C",
    "cream": "#F1E3C8",
    "cat_eye": "#5DA83A",
    "pink_nose": "#E9899A",
    # Pickles
    "raccoon": "#8E9095",
    "mask": "#1E1E22",
    "hivis": "#C8E534",
    "headphones": "#E84A8C",
    # Set
    "rack_blue": "#2F63B8",
    "rack_orange": "#F07A1C",
    "concrete": "#8F8E8A",
    "walkway": "#3F9E62",
    "walk_edge": "#F2C12E",
    "line_white": "#F2F0EA",
    # Forklift
    "fl_yellow": "#F2B825",
    "fl_dark": "#2A211E",
    "tyre": "#1B1918",
    "kraft": "#B98B55",
    "card_white": "#F3F1EC",
    "cardboard": "#C9A56E",
    "brass": "#C9A24A",
    "screen_teal": "#1FB5A5",
    "alert_red": "#F0402A",
    "caption_cream": "#F4ECD8",
}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(name_or_hex, alpha=1.0):
    """Linear RGBA tuple for Blender from a palette key or '#RRGGBB'."""
    h = HEX.get(name_or_hex, name_or_hex).lstrip("#")
    vals = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(srgb_to_linear(v) for v in vals) + (alpha,)


def srgb255(name_or_hex):
    """(r, g, b) 0-255 for Pillow UI work."""
    h = HEX.get(name_or_hex, name_or_hex).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def kelvin(temp):
    """Approximate blackbody colour (linear RGB) for a colour temperature."""
    import math
    t = temp / 100.0
    if t <= 66:
        r = 255
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    else:
        r = 329.698727446 * ((t - 60) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60) ** -0.0755148492)
        b = 255
    clamp = lambda v: max(0.0, min(255.0, v)) / 255.0
    return tuple(srgb_to_linear(clamp(v)) for v in (r, g, b))
