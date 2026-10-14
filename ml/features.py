"""Text preparation shared by training and serving (they must match exactly)."""
import re

from rules import normalize


def prepare_text(description: str) -> str:
    """Upper-case, drop '*', and collapse digit runs to '0'.

    Store numbers, phone numbers and reference codes (`#01961`, `714-500-2400`) differ on
    every transaction but say nothing about the category, so we blur them.
    """
    return re.sub(r"\d+", "0", normalize(description))
