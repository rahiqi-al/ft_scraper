import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, InvalidCookieDomainException, TimeoutException
import time
import pandas as pd
import logging
from minio import Minio
from minio.error import S3Error
from config.config import config
import io
import random
from datetime import datetime
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', filename="logs/app.log", filemode='a')
logger = logging.getLogger(__name__)

# flaresolverr setup
def get_cloudflare_cookies(url):
    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 120000  # Increased to 120 seconds
    }
    response = requests.post("http://localhost:8191/v1", json=payload)
    if response.status_code == 200:
        return response.json().get("solution", {}).get("cookies", [])
    else:
        logger.error(f"flaresolverr failed: {response.text}")
        return []

# Driver setup with undetected_chromedriver
options = uc.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--disable-extensions")
options.add_argument("--disable-images")
options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
prefs = {"profile.managed_default_content_settings.images": 2}
options.add_experimental_option("prefs", prefs)
driver = uc.Chrome(options=options)
driver.implicitly_wait(15)

def scrape_search_links(search_term):
    base_url = f"https://www.ft.com/search?q={search_term}&dateRange=now-24h&sort=relevance&isFirstView=false"
    all_data = {"link": [], "category": [], "title": [], "snippet": []}
    page = 1
    while True:
        url = f"{base_url}&page={page}"
        try:
            # Get cookies from flaresolverr
            cookies = get_cloudflare_cookies(url)
            for cookie in cookies:
                try:
                    driver.add_cookie({
                        "name": cookie["name"],
                        "value": cookie["value"],
                        "domain": ".ft.com",
                        "path": cookie.get("path", "/")
                    })
                except InvalidCookieDomainException:
                    logger.warning(f"Skipped invalid cookie domain for {cookie['name']}")
            driver.get(url)

            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(random.uniform(30, 45))  

            try:
                WebDriverWait(driver, 90).until_not(
                    EC.presence_of_element_located((By.ID, "spinnerText"))
                )
                logger.info(f"Spinner resolved for {url}")
            except TimeoutException:
                logger.warning(f"Spinner still present after 90 seconds on {url}, proceeding anyway")
            page_source = driver.page_source.lower()
            if "access denied" in page_source or "please verify you are a human" in page_source:
                logger.error("Cloudflare block detected, stopping scrape")
                break
            if "no results found" in page_source:
                logger.info(f"No results found on {url}")
                break
            links = driver.find_elements(By.XPATH, "//a[@class='js-teaser-heading-link']")
            if not links:
                logger.info(f"No links found on {url}, checking for verification")
                time.sleep(15)  
                links = driver.find_elements(By.XPATH, "//a[@class='js-teaser-heading-link']")
                if not links:
                    logger.warning(f"Verification still active or no content on {url}")
                    break
            for link in links:
                href = link.get_attribute('href')
                if '/content/' in href and href not in all_data["link"]:
                    title = link.text.strip() if link.text else None
                    category_elem = driver.find_element(By.XPATH, "//a[@class='o-teaser__tag']") if driver.find_elements(By.XPATH, "//a[@class='o-teaser__tag']") else None
                    category = category_elem.text.strip() if category_elem else None
                    snippet_elem = driver.find_element(By.XPATH, "//a[@class='js-teaser-standfirst-link']") if driver.find_elements(By.XPATH, "//a[@class='js-teaser-standfirst-link']") else None
                    snippet = snippet_elem.text.strip() if snippet_elem else None
                    all_data["link"].append(href)
                    all_data["category"].append(category)
                    all_data["title"].append(title)
                    all_data["snippet"].append(snippet)
            if not links:
                break
            logger.info(f"Collected {len(links)} unique items from {url}")
            page += 1
        except (TimeoutException, Exception) as e:
            logger.error(f"Error accessing {url}: {e}")
            break
    return pd.DataFrame(all_data)

def scrape_article_data(articles, data):
    for article in articles:
        try:
            cookies = get_cloudflare_cookies(article)
            for cookie in cookies:
                try:
                    driver.add_cookie({
                        "name": cookie["name"],
                        "value": cookie["value"],
                        "domain": ".ft.com",
                        "path": cookie.get("path", "/")
                    })
                except InvalidCookieDomainException:
                    logger.warning(f"Skipped invalid cookie domain for {cookie['name']}")
            driver.get(article)
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(random.uniform(30, 45))
            li = []
            try:
                paywall = driver.find_element(By.XPATH, "//div[contains(@class, 'paywall')]")
                logger.info(f"Paywall detected for {article}, skipping")
                li.extend([None, None, None, article])
                for key, value in zip(data.keys(), li):
                    data[key].append(value)
                continue
            except NoSuchElementException:
                pass
            try:
                title = driver.find_element(By.XPATH, "//h1[contains(@class, 'n-content-layout__title')]").text.strip()
                li.append(title)
            except NoSuchElementException:
                li.append(None)
            try:
                author = driver.find_element(By.XPATH, "//span[@itemprop='author']").text.strip()
                li.append(author)
            except NoSuchElementException:
                li.append(None)
            try:
                content_elements = driver.find_elements(By.XPATH, "//div[@itemprop='articleBody']//p")
                content = ' '.join([p.text.strip() for p in content_elements if p.text])[:1000]
                li.append(content)
            except NoSuchElementException:
                li.append(None)
            li.append(article)
            for key, value in zip(data.keys(), li):
                data[key].append(value)
                logger.debug(f"Scraped {key}: {value} for {article}")
        except Exception as e:
            logger.error(f"Error scraping {article}: {e}")
            continue

def setup_minio():
    client = Minio(config.minio_endpoint, access_key=config.minio_acces_key, secret_key=config.minio_secret_key, secure=False)
    link_bucket = config.link_bucket
    article_bucket = config.article_bucket
    try:
        if not client.bucket_exists(link_bucket):
            client.make_bucket(link_bucket)
            logger.info(f"Created bucket {link_bucket}")
        if not client.bucket_exists(article_bucket):
            client.make_bucket(article_bucket)
            logger.info(f"Created bucket {article_bucket}")
    except S3Error as e:
        logger.error(f"MinIO error: {e}")
    return client, link_bucket, article_bucket

def save_to_minio(client, bucket_name, df, filename):
    try:
        csv_data = df.to_csv(index=False).encode("utf-8")
        client.put_object(bucket_name=bucket_name, object_name=filename, data=io.BytesIO(csv_data))
        logger.info(f"Saved {filename} to MinIO")
    except S3Error as e:
        logger.error(f"MinIO save error: {e}")

def main():
    minio_client, link_bucket, article_bucket = setup_minio()
    all_links_data = pd.DataFrame()

    for term in config.search_terms:
        links_data = scrape_search_links(term)
        all_links_data = pd.concat([all_links_data, links_data], ignore_index=True)
    logger.info(f"Total unique items collected: {len(all_links_data)}")
    if not all_links_data.empty:
        save_to_minio(minio_client, link_bucket, all_links_data, filename=f"{link_bucket}_links_{datetime.now().strftime('%Y%m%d')}.csv")

    article_data = {'title': [], 'author': [], 'content': [], 'link': []}
    scrape_article_data(all_links_data["link"].dropna().unique(), article_data)
    article_df = pd.DataFrame(article_data)
    if not article_df.empty:
        save_to_minio(minio_client, article_bucket, article_df)

    driver.quit()

if __name__ == '__main__':
    main()