import os
from flask import Flask, request, jsonify, send_from_directory
from scraper import scrape_website, ScrapingError
from validator import validate_input
import logging
from functools import wraps
from time import time
from selenium.common.exceptions import WebDriverException

app = Flask(__name__, static_folder='assets')
logging.basicConfig(level=logging.DEBUG)

# Get the webhook key from system variable
WEBHOOK_KEY = os.environ.get('WEBHOOK_KEY')

app.logger.debug(f"WEBHOOK_KEY read from system variable: {'[SET]' if WEBHOOK_KEY else '[NOT SET]'}")

if not WEBHOOK_KEY:
    raise ValueError("WEBHOOK_KEY system variable is not set. Please set it using: set WEBHOOK_KEY=Your_Key")

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
    app.logger.debug(f"Received {request.method} webhook request")

    received_key = request.headers.get('X-Webhook-Key')
    app.logger.debug(f"Received key: {received_key}")
    app.logger.debug(f"Keys match: {received_key == WEBHOOK_KEY}")

    if request.method == 'GET':
        return jsonify({"message": "Webhook endpoint is active. Please use POST method to submit data."}), 200

    if received_key != WEBHOOK_KEY:
        app.logger.warning("Invalid webhook key received")
        return jsonify({"error": "Invalid webhook key"}), 401

    data = request.json
    app.logger.debug(f"Received data: {data}")

    validation_result = validate_input(data)
    if validation_result:
        app.logger.warning(f"Validation error: {validation_result}")
        return jsonify({"error": validation_result}), 400

    website_url = data['website_url']
    
    try:
        # Check cache first
        if website_url in cache and time() - cache[website_url]['timestamp'] < CACHE_TIMEOUT:
            app.logger.info(f"Returning cached data for: {website_url}")
            return jsonify(cache[website_url]['data']), 200

        app.logger.info(f"Scraping website: {website_url}")
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

        app.logger.info("Scraping successful")
        return jsonify(response), 200

    except ScrapingError as e:
        app.logger.error(f"Scraping failed: {str(e)}")
        return jsonify({"error": str(e), "status": "failed"}), 500
    except WebDriverException as e:
        app.logger.error(f"Selenium WebDriver error: {str(e)}")
        return jsonify({"error": f"Selenium WebDriver error: {str(e)}", "status": "failed"}), 500

@app.route('/')
def home():
    return "WebSiteScarpeService is running!"

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
        app.logger.info(f"Test scraper response: {response}")  # Log the response
        return jsonify(response), 200
    except ScrapingError as e:
        error_response = {"error": str(e), "status": "failed"}
        app.logger.error(f"Test scraper error: {error_response}")  # Log the error
        return jsonify(error_response), 500
    except WebDriverException as e:
        error_response = {"error": f"Selenium WebDriver error: {str(e)}", "status": "failed"}
        app.logger.error(f"Test scraper error: {error_response}")  # Log the error
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
        "WEBHOOK_KEY": "[SET]" if WEBHOOK_KEY else "[NOT SET]"
    })

if __name__ == "__main__":
    app.logger.info("Starting Flask application")
    app.run(host='0.0.0.0', port=5000, debug=True)
