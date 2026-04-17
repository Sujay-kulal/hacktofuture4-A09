import re

def cluster_logs(deduplicated_counts):
    """
    Applies rules to group similar log signatures into broad categories.
    Extracts or associates affected services.
    
    Returns a list of dictionaries: 
    [{"cluster_name": "DB_TIMEOUT", "count": 120, "services": ["auth", "payment"], "samples": [...]}]
    """
    clusters = {}
    
    # Simple predefined rules for clustering (NO LLM Used here)
    RULES = {
        "DB_TIMEOUT": ["db timeout", "database timeout", "query timeout", "connection timeout"],
        "API_FAILURE": ["api failure", "500 internal", "bad gateway", "connection refused"],
        "OOM_ERROR": ["out of memory", "oom", "memory limit exceeded"]
    }
    
    for log_sig, count in deduplicated_counts.items():
        matched_cluster = "UNKNOWN_ERROR"
        log_lower = log_sig.lower()
        
        # 1. Determine cluster
        for cluster_name, keywords in RULES.items():
            if any(kw in log_lower for kw in keywords):
                matched_cluster = cluster_name
                break
                
        # 2. Extract service name (skipping log levels like ERROR or WARNING)
        service = "unknown_service"
        matches = re.findall(r'\[([a-zA-Z0-9_\-]+)\]', log_sig)
        for match in matches:
            if match not in ["ERROR", "WARNING", "WARN", "INFO", "DEBUG"]:
                service = match
                break
        
        # 3. Aggregate into the cluster hashmap
        if matched_cluster not in clusters:
            clusters[matched_cluster] = {
                "cluster_name": matched_cluster,
                "count": 0,
                "services": set(),
                "samples": set()
            }
            
        clusters[matched_cluster]["count"] += count
        clusters[matched_cluster]["services"].add(service)
        clusters[matched_cluster]["samples"].add(log_sig)
        
    # 4. Format outputs for JSON serialization/readability
    for c in clusters.values():
        c["services"] = list(c["services"])
        # We only keep a couple of samples so we don't blow up the token count
        c["samples"] = list(c["samples"])[:1]
        
    return list(clusters.values())
