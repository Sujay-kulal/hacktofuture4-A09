def summarize_clusters(clusters):
    """
    Formats the clustered logs into a compact list, sorting by frequency.
    Returns a dictionary containing the text summary and numerical metadata.
    """
    # Sort clusters by count descending
    sorted_clusters = sorted(clusters, key=lambda x: x["count"], reverse=True)
    
    # Limit to top 5 issues to keep token size predictable and low
    top_clusters = sorted_clusters[:5]
    
    summary_text = []
    total_errors = sum(c["count"] for c in clusters)
    
    if not top_clusters:
        summary_text.append("No errors detected in this window.")
    else:
        for c in top_clusters:
            # e.g., "- DB_TIMEOUT (x1200, services: auth, payment)"
            services_str = ", ".join(c["services"])
            summary_text.append(f"- {c['cluster_name']} (x{c['count']}, services: {services_str})")
            
    return {
        "text": "\n".join(summary_text),
        "total_errors": total_errors,
        "unique_clusters": len(clusters),
        "top_clusters_data": top_clusters
    }
