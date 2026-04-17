import time
import random
from datetime import datetime, timezone

# 10 log templates imitating real microservices traffic
LOG_TEMPLATES = [
    # --- INFO/DEBUG (These should get safely ignored by the filter) ---
    "[{timestamp}] [INFO] [health-check] Service is healthy. Uptime: {num} minutes.",
    "[{timestamp}] [INFO] [api] User {uuid} logged in successfully.",
    "[{timestamp}] [DEBUG] [worker] Processed payload sized {num} bytes.",
    
    # --- ERRORS (These should trigger rules and get clustered) ---
    "[{timestamp}] [ERROR] [auth] DB timeout while fetching user {uuid}",
    "[{timestamp}] [ERROR] [payment] Database timeout reading transaction {num}",
    "[{timestamp}] [WARNING] [data_layer] query timeout for session {uuid}",
    
    "[{timestamp}] [ERROR] [api] 500 Internal Server error on route /users/{num}",
    "[{timestamp}] [ERROR] [gateway] Bad gateway connection refused from IP 192.168.1.{num}",
    
    "[{timestamp}] [ERROR] [worker] Out of memory - limit exceeded",
    "[{timestamp}] [ERROR] [processing] OOM killer terminated process {num}"
]

def generate_logs(filepath, duration_sec=60, logs_per_sec=20):
    print(f"Generating synthetic logs to {filepath}...")
    print(f"Rate: {logs_per_sec} logs/sec | Duration: {duration_sec} seconds")
    
    # Truncate or create the file
    with open(filepath, 'w', encoding='utf-8') as f:
        pass 
        
    start_time = time.time()
    
    # Open for appending
    with open(filepath, 'a', encoding='utf-8') as f:
        while time.time() - start_time < duration_sec:
            # 70% INFO/DEBUG, 30% ERROR/WARNING
            is_error = random.random() > 0.70
            if is_error:
                template = random.choice(LOG_TEMPLATES[3:])
            else:
                template = random.choice(LOG_TEMPLATES[:3])
                
            timestamp = datetime.now(timezone.utc).isoformat()
            uuid_str = f"123e4567-e89b-12d3-a456-426614174{random.randint(100,999)}"
            num = random.randint(1, 9999)
            
            log_line = template.format(timestamp=timestamp, uuid=uuid_str, num=num)
            f.write(log_line + "\n")
            f.flush()
            
            # Sleep slightly to control the generation rate (add some burstiness)
            time.sleep(random.uniform(0.01, 1.0 / logs_per_sec))
            
    print("Synthetic log generation finished.")

if __name__ == "__main__":
    generate_logs("example.log", duration_sec=60, logs_per_sec=20)
