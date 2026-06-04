import os
import requests
import json
from typing import List, Dict, Any, Optional

class EventEmitter:
    def __init__(self, api_url: Optional[str] = None):
        """
        Initializes the event emitter.
        Detects if running inside Docker network or on localhost.
        """
        # Resolve target API URL
        self.api_url = api_url or os.getenv("API_URL", "http://web:8000")
        self.ingest_endpoint = f"{self.api_url}/events/ingest"
        
        print(f"[EventEmitter] Target ingestion endpoint set to: {self.ingest_endpoint}")

    def emit_batch(self, events: List[Dict[str, Any]]) -> bool:
        """
        Ingests a batch of generated CCTV events into the FastAPI backend service.
        """
        if not events:
            return True
            
        try:
            # Set headers
            headers = {"Content-Type": "application/json"}
            
            # Send batch POST request
            response = requests.post(
                self.ingest_endpoint,
                data=json.dumps(events),
                headers=headers,
                timeout=5.0
            )
            
            if response.status_code in [200, 207]:
                result = response.json()
                print(f"[EventEmitter] Ingested {result.get('success_count', 0)} / {len(events)} events successfully.")
                
                # Write to the JSONL evaluation log file
                try:
                    # Resolve to project root (works inside Docker or locally)
                    log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "events.jsonl")
                    with open(log_path, "a") as f:
                        for ev in events:
                            f.write(json.dumps(ev) + "\n")
                except Exception as log_err:
                    print(f"[EventEmitter] Could not write to events.jsonl: {log_err}")
                    
                return True
            else:
                print(f"[EventEmitter] API Ingestion failed with status {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"[EventEmitter] Ingestion failed (connection error): {e}. Events dropped/logged.")
            # In production, you would write these events to a local SQLite buffer file or queue.
            # For hackathon simplicity, we log them and let the pipeline continue running.
            return False
