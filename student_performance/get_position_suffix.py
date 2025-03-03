def get_position_suffix(position):
    # Get the last two digits to check for special cases like 11th, 12th, 13th, etc.
    if 11 <= position % 100 <= 13:
        suffix = 'th'
    else:
        # Use the last digit to determine the appropriate suffix (1st, 2nd, 3rd, etc.)
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(position % 10, 'th')
    
    return f"{position}{suffix}"
