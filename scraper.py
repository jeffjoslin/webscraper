import logging
from bs4 import BeautifulSoup
import trafilatura
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
import re
import os

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1'
]

class ScrapingError(Exception):
    pass

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Comment out if you want to see the browser
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        logger.error(f"Failed to set up ChromeDriver: {str(e)}")
        raise ScrapingError(f"Failed to set up ChromeDriver: {str(e)}")

def fetch_html(url):
    driver = None
    try:
        driver = setup_driver()
        logger.info(f"Fetching HTML for {url}")
        driver.get(url)
        return driver.page_source
    except WebDriverException as e:
        logger.error(f"Failed to fetch HTML for {url}: {str(e)}")
        raise ScrapingError(f"Selenium request failed: {str(e)}")
    finally:
        if driver:
            driver.quit()

def scrape_website(url, max_retries=3):
    logger.info(f"Scraping website: {url}")

    for attempt in range(max_retries):
        try:
            html = fetch_html(url)
            soup = BeautifulSoup(html, 'html.parser')
            main_content = trafilatura.extract(html)

            scraped_data = {
                "url": url,
                "title": soup.title.string if soup.title else "No title found",
                "meta_description": soup.find("meta", attrs={"name": "description"})["content"] if soup.find("meta", attrs={"name": "description"}) else "No meta description found",
                "h1_tags": [h1.text for h1 in soup.find_all("h1")],
                "links": [{"text": a.text, "href": a.get("href")} for a in soup.find_all("a", href=True)],
                "main_content": main_content if main_content else "No main content extracted",
                "pages_count": count_pages(soup)
            }

            return scraped_data
        except Exception as e:
            logger.warning(f"Scraping attempt {attempt + 1} failed: {str(e)}. Retrying...")
            if attempt == max_retries - 1:
                logger.error(f"Failed to scrape website after {max_retries} attempts.")
                raise ScrapingError(f"Failed to scrape website after {max_retries} attempts: {str(e)}")

def count_pages(soup):
    internal_links = soup.find_all('a', href=lambda href: href and not href.startswith(('http', 'www')) and href != '#')
    valid_links = set(link['href'] for link in internal_links if 'href' in link.attrs and link['href'].strip() != '')
    return len(valid_links) + 1 if valid_links else 1

def test_scraper():
    test_url = "https://example.com"
    try:
        result = scrape_website(test_url)
        print(f"Successfully scraped {test_url}")
        print("Scraped data:")
        for key, value in result.items():
            if key == "links":
                print(f"{key}: {len(value)} links found")
            elif key == "main_content":
                print(f"{key}: {value[:100]}... (truncated)")
            else:
                print(f"{key}: {value}")
    except ScrapingError as e:
        print(f"Failed to scrape {test_url}: {str(e)}")

if __name__ == "__main__":
    test_scraper()