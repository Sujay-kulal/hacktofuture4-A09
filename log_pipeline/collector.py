import time
import os

def tail_logs(filepath):
    """
    Simulates a real-time log stream by tailing a log file.
    Yields new lines as they are written to the file.
    """
    # Wait until file exists
    print(f"[Collector] Waiting for log file: {filepath}")
    while not os.path.exists(filepath):
        time.sleep(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        # Move to the end of file if we only want new logs,
        # but for testing/simulation we might want to read from start
        # f.seek(0, 2) 
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1) # Sleep briefly to wait for more lines
                continue
            yield line.strip()
