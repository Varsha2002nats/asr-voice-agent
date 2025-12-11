def parse_bool(value: str) -> bool:
    """
    Parses a string into a boolean value.

    Args:
        value (str): The string to parse.

    Returns:
        bool: The parsed boolean value.

    Raises:
        ValueError: If the string cannot be parsed into a boolean.
    """
    true_values = {"true", "1", "yes", "y", "on"}
    false_values = {"false", "0", "no", "n", "off"}

    value_lower = value.strip().lower()
    if value_lower in true_values:
        return True
    elif value_lower in false_values:
        return False
    else:
        raise ValueError(f"Cannot parse '{value}' into a boolean.")
