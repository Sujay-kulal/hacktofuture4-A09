import time
import argparse
from collector import tail_logs
from filter import filter_logs
from normalize import normalize_log
from deduplicate import deduplicate_logs
from cluster import cluster_logs
from summarize import summarize_clusters
from trigger import check_and_trigger_gemini

def run_pipeline(logfile, window_seconds=5, total_threshold=10, unique_threshold=2):
    print(f"==========================================")
    print(f"Starting Log Processing Pipeline")
    print(f"Reading from: {logfile}")
    print(f"Window: {window_seconds}s")
    print(f"Thresholds -> Total: {total_threshold}, Unique: {unique_threshold}")
    print(f"==========================================\n")
    
    log_generator = tail_logs(logfile)
    
    # State mechanism to buffer logs for the duration of the time window
    current_window_logs = []
    window_start_time = time.time()
    
    try:
        for raw_line in log_generator:
            # 1. Check if the current time window expired
            current_time = time.time()
            if current_time - window_start_time >= window_seconds:
                _process_window(current_window_logs, total_threshold, unique_threshold)
                # Reset window
                current_window_logs = []
                window_start_time = time.time()
                
            # 2. If we received a log line from the file, run it through the streaming stages
            if raw_line:
                filtered_line = filter_logs(raw_line)
                if filtered_line:
                    normalized_line = normalize_log(filtered_line)
                    current_window_logs.append(normalized_line)
                    
    except KeyboardInterrupt:
        print("\nPipeline stopped by user. Processing any remaining logs in buffer...")
        if current_window_logs:
            _process_window(current_window_logs, total_threshold, unique_threshold)

def _process_window(logs, total_threshold, unique_threshold):
    """Processes a batch of normalized logs that occurred within the time window."""
    if not logs:
        # Optimization: no errors, skip processing completely
        return
        
    print("\n" + "="*50)
    print(f"Time Window Passed. Processing Batch of {len(logs)} error logs...")
    
    # 3. Deduplicate
    deduped = deduplicate_logs(logs)
    print(f" -> After deduplication: {len(deduped)} unique signatures")
    
    # 4. Cluster
    clusters = cluster_logs(deduped)
    print(f" -> After clustering: {len(clusters)} distinct clusters")
    
    # 5. Summarize
    summary_dict = summarize_clusters(clusters)
    
    # 6. Trigger condition & Gemini Call
    check_and_trigger_gemini(summary_dict, total_threshold, unique_threshold)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the log processing pipeline.")
    parser.add_argument("--logfile", default="example.log", help="Path to the log file to tail")
    # For a hackathon demo, a 5-second window is great. In production, 30s-60s is better.
    parser.add_argument("--window", type=int, default=5, help="Time window in seconds")
    parser.add_argument("--total", type=int, default=15, help="Trigger Gemini if total errors exceed this")
    parser.add_argument("--unique", type=int, default=2, help="Trigger Gemini if unique errors exceed this")
    args = parser.parse_args()
    
    run_pipeline(args.logfile, args.window, args.total, args.unique)
