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
from multiprocessing import Pool
import schedule

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', filename="logs/app.log", filemode='a')
logger = logging.getLogger(__name__)

# flaresolverr setup
def get_cloudflare_cookies(url):
    payload = {"cmd": "request.get", "url": url, "maxTimeout": 180000}
    response = requests.post("http://localhost:8191/v1", json=payload)
    if response.status_code == 200:
        return response.json().get("solution", {}).get("cookies", [])
    else:
        logger.error(f"flaresolverr failed: {response.text}")
        return []

# Driver setup with undetected_chromedriver
def setup_driver():
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
    return uc.Chrome(options=options)

def scrape_search_links(term):
    base_url = f"https://www.ft.com/search?q={term}&dateRange=now-24h&sort=relevance&isFirstView=false"
    url = base_url
    driver = setup_driver()
    data = {"link": [], "category": [], "title": [], "snippet": []}
    try:
        cookies = get_cloudflare_cookies(url)
        for cookie in cookies:
            try:
                driver.add_cookie({"name": cookie["name"], "value": cookie["value"], "domain": ".ft.com", "path": cookie.get("path", "/")})
            except InvalidCookieDomainException:
                logger.warning(f"Skipped invalid cookie domain for {cookie['name']}")
        driver.get(url)
        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(random.uniform(30, 45))
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                WebDriverWait(driver, 90).until_not(EC.presence_of_element_located((By.ID, "spinnerText")))
                logger.info(f"Spinner resolved for {url}")
                break
            except TimeoutException:
                retry_count += 1
                logger.warning(f"Spinner still present after 90 seconds on {url}, retry {retry_count}/{max_retries}")
                if retry_count == max_retries:
                    logger.error(f"Failed to resolve spinner after {max_retries} retries on {url}, proceeding anyway")
                time.sleep(15)
        page_source = driver.page_source.lower()
        if "access denied" in page_source or "please verify you are a human" in page_source:
            logger.error("Cloudflare block detected, stopping scrape for {}".format(term))
            return pd.DataFrame(data)
        if "no results found" in page_source:
            logger.info(f"No results found on {url}")
            return pd.DataFrame(data)
        links = driver.find_elements(By.XPATH, "//a[@class='js-teaser-heading-link']")
        if not links:
            logger.info(f"No links found on {url}, checking for verification")
            time.sleep(15)
            links = driver.find_elements(By.XPATH, "//a[@class='js-teaser-heading-link']")
            if not links:
                logger.warning(f"Verification still active or no content on {url}")
                return pd.DataFrame(data)
        for link in links:
            href = link.get_attribute('href')
            if '/content/' in href and href not in data["link"]:
                title = link.text.strip() if link.text else None
                category_elem = driver.find_element(By.XPATH, "//a[@class='o-teaser__tag']") if driver.find_elements(By.XPATH, "//a[@class='o-teaser__tag']") else None
                category = category_elem.text.strip() if category_elem else None
                snippet_elem = driver.find_element(By.XPATH, "//a[@class='js-teaser-standfirst-link']") if driver.find_elements(By.XPATH, "//a[@class='js-teaser-standfirst-link']") else None
                snippet = snippet_elem.text.strip() if snippet_elem else None
                data["link"].append(href)
                data["category"].append(category)
                data["title"].append(title)
                data["snippet"].append(snippet)
        logger.info(f"Collected {len(links)} unique items from {url} for term {term}")
    except (TimeoutException, Exception) as e:
        logger.error(f"Error accessing {url} for term {term}: {e}")
    finally:
        driver.quit()
    return pd.DataFrame(data)

def scrape_article_data(articles, data):
    driver = setup_driver()
    try:
        for article in articles:
            try:
                cookies = get_cloudflare_cookies(article)
                for cookie in cookies:
                    try:
                        driver.add_cookie({"name": cookie["name"], "value": cookie["value"], "domain": ".ft.com", "path": cookie.get("path", "/")})
                    except InvalidCookieDomainException:
                        logger.warning(f"Skipped invalid cookie domain for {cookie['name']}")
                driver.get(article)
                WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
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
    finally:
        driver.quit()

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

    with Pool(processes=min(len(config.search_terms), 4)) as pool:
        results = pool.map(scrape_search_links, config.search_terms)
    for result in results:
        all_links_data = pd.concat([all_links_data, result], ignore_index=True)
    logger.info(f"Total unique items collected: {len(all_links_data)}")
    if not all_links_data.empty:
        save_to_minio(minio_client, link_bucket, all_links_data, filename=f"{link_bucket}_links_{datetime.now().strftime('%Y%m%d')}.csv")

    article_data = {'title': [], 'author': [], 'content': [], 'link': []}
    scrape_article_data(all_links_data["link"].dropna().unique(), article_data)
    article_df = pd.DataFrame(article_data)
    if not article_df.empty:
        save_to_minio(minio_client, article_bucket, article_df)

def run_scraper():
    logger.info("Starting daily scrape at scheduled time")
    main()

if __name__ == '__main__':
    schedule.every().day.at("20:52").do(run_scraper)

    while True:
        schedule.run_pending()
        time.sleep(60)  