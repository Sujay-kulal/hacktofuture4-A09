import re

def normalize_log(log_line):
    """
    Removes timestamps, UUIDs, IP addresses, and numbers to create a consistent signature.
    This step is crucial because "Error user 123" and "Error user 456" 
    should count as the same error type.
    """
    # Remove ISO8601 timestamps
    log_line = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?', '<TIMESTAMP>', log_line)
    
    # Remove generic date/times like YYYY-MM-DD HH:MM:SS
    log_line = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d+)?', '<TIMESTAMP>', log_line)
    
    # Remove IP addresses
    log_line = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<IP>', log_line)
    
    # Remove UUIDs
    log_line = re.sub(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b', '<UUID>', log_line)
    
    # Remove standalone dynamic numbers
    log_line = re.sub(r'\b\d+\b', '<NUM>', log_line)
    
    return log_line.strip()
