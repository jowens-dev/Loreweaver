import requests
import gzip
import json

def fetch_scryfall_oracle_cards():
    url = "https://api.scryfall.com/bulk-data/oracle-cards"
    headers = {
        'User-Agent': 'your-agent-string'
    }
    
    # Replace the deprecated key with the new one.
    response = requests.get(url, headers=headers)
    jsonl_download_uri = response.json()['jsonl_download_uri']
    
    # Download and parse the JSONL archive
    import io
    import gzip
    
    with io.BytesIO() as f:
        f.write(gzip.GzipFile(fileobj=f).buffer())
        
        for line in f:
            yield json.loads(line.decode('utf-8'))