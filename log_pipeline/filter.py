def filter_logs(log_line):
    """
    Drops INFO and DEBUG logs.
    Returns the log line if it's an ERROR or WARNING, otherwise returns None.
    This acts as our first layer of token-saving by dropping noise.
    """
    # Simple keyword-based filtering for performance
    if "ERROR" in log_line or "WARNING" in log_line or "WARN" in log_line:
        return log_line
    return None
