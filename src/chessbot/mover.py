"""Map board squares to pixel coordinates for CDP clicks."""

FILES = "abcdefgh"

def square_to_xy(sq: str, rect: tuple[int, int, int, int], white_bottom: bool) -> tuple[int, int]:
    """Return the pixel center of *sq* for the given board rect and orientation."""
    left, top, w, h = rect
    cw, ch = w / 8, h / 8
    f = FILES.index(sq[0])
    r = int(sq[1]) - 1
    col = f if white_bottom else 7 - f
    row = 7 - r if white_bottom else r
    return (int(left + col * cw + cw / 2), int(top + row * ch + ch / 2))

def rect_center(rect):
    """Return the center pixel of *rect* as an (x, y) tuple."""
    return rect[0] + rect[2] / 2, rect[1] + rect[3] / 2
