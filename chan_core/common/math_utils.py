"""Basic mathematical predicates on price intervals."""


def overlap(low_a: float, high_a: float, low_b: float, high_b: float) -> bool:
    """Closed-interval overlap: max(low) <= min(high)."""
    return max(low_a, low_b) <= min(high_a, high_b)


def strict_overlap(low_a: float, high_a: float, low_b: float, high_b: float) -> bool:
    """Strict overlap: max(low) < min(high)."""
    return max(low_a, low_b) < min(high_a, high_b)
