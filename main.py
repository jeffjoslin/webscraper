import os
from flask import Flask, request, jsonify, send_from_directory
from scraper import scrape_website, ScrapingError
from validator import validate_input
import logging
from functools import wraps
from time import time
from google.cloud import secretmanager

app = Flask(__name__, static_folder='assets')
logging.basicConfig(level=logging.DEBUG)

def get_secret(secret_id):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/scraper-436405/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# Get the webhook key from system variable or Secret Manager
WEBHOOK_KEY = os.environ.get('WEBHOOK_KEY')
if WEBHOOK_KEY and WEBHOOK_KEY.startswith('sm://'):
    secret_id = WEBHOOK_KEY.split('/')[-3]
    WEBHOOK_KEY = get_secret(secret_id)

print(f"WEBHOOK_KEY read: {'[SET]' if WEBHOOK_KEY else '[NOT SET]'}")
print(f"WEBHOOK_KEY value: {WEBHOOK_KEY}")

if not WEBHOOK_KEY:
    print("WEBHOOK_KEY is not set.")
    raise ValueError("WEBHOOK_KEY is not set. Please set it using: set WEBHOOK_KEY=Your_Key")

# Simple in-memory cache
cache = {}
CACHE_TIMEOUT = 3600  # 1 hour

# Rate limiting
RATE_LIMIT = 10  # requests
RATE_LIMIT_PERIOD = 60  # seconds
request_history = {}

def rate_limit(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        now = time()
        ip = request.remote_addr
        if ip not in request_history:
            request_history[ip] = []
        request_history[ip] = [t for t in request_history[ip] if now - t < RATE_LIMIT_PERIOD]
        if len(request_history[ip]) >= RATE_LIMIT:
            return jsonify({"error": "Rate limit exceeded"}), 429
        request_history[ip].append(now)
        return func(*args, **kwargs)
    return wrapper

@app.route('/webhook', methods=['GET', 'POST'])
@rate_limit
def webhook():
    print(f"Received {request.method} webhook request")

    received_key = request.headers.get('X-Webhook-Key')
    print(f"Received key: {received_key}")
    print(f"Stored WEBHOOK_KEY: {WEBHOOK_KEY}")
    print(f"Keys match: {received_key == WEBHOOK_KEY}")

    if request.method == 'GET':
        return jsonify({"message": "Webhook endpoint is active. Please use POST method to submit data."}), 200

    if received_key != WEBHOOK_KEY:
        print("Invalid webhook key received")
        return jsonify({"error": "Invalid webhook key"}), 401

    data = request.json
    print(f"Received data: {data}")

    validation_result = validate_input(data)
    if validation_result:
        print(f"Validation error: {validation_result}")
        return jsonify({"error": validation_result}), 400

    website_url = data['website_url']
    
    try:
        # Check cache first
        if website_url in cache and time() - cache[website_url]['timestamp'] < CACHE_TIMEOUT:
            print(f"Returning cached data for: {website_url}")
            return jsonify(cache[website_url]['data']), 200

        print(f"Scraping website: {website_url}")
        scraped_data = scrape_website(website_url)

        response = {
            "status": "success",
            "scraped_data": scraped_data,
            "message": "Website successfully scraped."
        }
        
        # Update cache
        cache[website_url] = {
            'data': response,
            'timestamp': time()
        }

        print("Scraping successful")
        return jsonify(response), 200

    except ScrapingError as e:
        print(f"Scraping failed: {str(e)}")
        return jsonify({"error": str(e), "status": "failed"}), 500

@app.route('/')
def home():
    return "Welcome to The Bot Experts Webservices!"

@app.route('/assets/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/test')
def test():
    return jsonify({"message": "Test route is working!"}), 200

@app.route('/test_scraper')
@rate_limit
def test_scraper():
    try:
        scraped_data = scrape_website("https://www.example.com")
        response = {
            "status": "success",
            "scraped_data": scraped_data
        }
        print(f"Test scraper response: {response}")
        return jsonify(response), 200
    except ScrapingError as e:
        error_response = {"error": str(e), "status": "failed"}
        print(f"Test scraper error: {error_response}")
        return jsonify(error_response), 500

@app.route('/test_validator')
def test_validator():
    test_cases = [
        {"input": {"website_url": "https://www.example.com"}, "expected": None},
        {"input": {}, "expected": "Missing 'website_url' in the request data."},
        {"input": {"website_url": ""}, "expected": "'website_url' must be a non-empty string."},
        {"input": {"website_url": 123}, "expected": "'website_url' must be a non-empty string."},
    ]

    results = []
    for case in test_cases:
        result = validate_input(case["input"])
        passed = result == case["expected"]
        results.append({
            "input": case["input"],
            "expected": case["expected"],
            "result": result,
            "passed": passed
        })

    return jsonify({"test_results": results})

@app.route('/debug_env')
def debug_env():
    return jsonify({
        "WEBHOOK_KEY": "[SET]" if WEBHOOK_KEY else "[NOT SET]",
        "WEBHOOK_KEY_VALUE": WEBHOOK_KEY[:5] + "..." if WEBHOOK_KEY else None
    })

if __name__ == "__main__":
    print("Starting Flask application")
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
