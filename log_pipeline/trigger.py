import os

def check_and_trigger_gemini(summary_dict, total_threshold=100, unique_threshold=3):
    """
    Conditional trigger: Evaluates conditions (e.g., total > threshold OR unique > threshold). 
    If met, it invokes a function to 'send' the summary to the Gemini API.
    """
    total = summary_dict.get("total_errors", 0)
    unique = summary_dict.get("unique_clusters", 0)
    text_summary = summary_dict.get("text", "")
    
    if total == 0:
        return
        
    print("\n--- Pipeline Summary ---")
    print(text_summary)
    print(f"------------------------")
    print(f"[Trigger Check] Total Errors: {total} | Unique Clusters: {unique}")
    
    if total > total_threshold or unique > unique_threshold:
        print(f"[Trigger] Threshold exceeded! (Total > {total_threshold} or Unique > {unique_threshold})")
        print("[Trigger] Invoking Gemini API for Root Cause Analysis...")
        _call_gemini(text_summary)
    else:
        print(f"[Trigger] Limits not exceeded. Skipping Gemini API call to save tokens/costs.")

def _call_gemini(summary_text):
    """
    Function representing the Gemini API call.
    Only sends the summarized output (never raw logs).
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    prompt = f"""
You are an expert SRE AI. Analyze this condensed log summary and provide a 
brief root cause hypothesis and a single recommended mitigation step.

Condended Logs:
{summary_text}
"""
    
    if not api_key:
        print("\n[Gemini API - MOCK]")
        print("No API key provided in GEMINI_API_KEY environment variable. Mocking response.")
        print(f"-> Sent to Gemini:\n{prompt}")
        print("<- Received from Gemini:")
        print("   Based on the summary, the most frequent issue is DB_TIMEOUT affecting multiple services.")
        print("   Hypothesis: The database connection pool is likely exhausted or the DB is locked.")
        print("   Mitigation: Temporarily increase the max connection pool limit and investigate long-running queries.")
        print("=======================\n")
        return
        
    # Actual implementation for Gemini (if API Key was present)
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        response = model.generate_content(prompt)
        print("\n[Gemini API - REAL]")
        print("<- Received from Gemini:")
        print(response.text)
        print("=======================\n")
    except Exception as e:
        print(f"\n[Gemini API - ERROR] Failed to call Gemini API: {e}\n")
