def validate_input(data):
    """
    Validates the input data for the required parameters.

    Args:
        data (dict): The input data from the request.

    Returns:
        str or None: An error message if validation fails, or None if validation passes.
    """
    if not data:
        return "No data provided."

    if 'website_url' not in data:
        return "Missing 'website_url' in the request data."

    website_url = data['website_url']
    if not isinstance(website_url, str) or not website_url.strip():
        return "'website_url' must be a non-empty string."

    # Additional validation for the URL format can be added here
    # For example, you can check if the URL is valid using regex or urllib

    return None  # Return None if validation passes

