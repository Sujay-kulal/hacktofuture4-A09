from collections import Counter

def deduplicate_logs(normalized_logs):
    """
    Takes a list of normalized logs and counts their occurrences.
    Returns a collections.Counter object mapping {log_signature: count}.
    This drastically reduces the payload size. 1000 identical lines become 1 dictionary entry.
    """
    return Counter(normalized_logs)
