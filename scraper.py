from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium_stealth import stealth
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
import time
import pandas as pd
import logging
from minio import Minio
from minio.error import S3Error
from config.config import config
import io
import random
from datetime import datetime

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', filename="logs/app.log", filemode='a')
logger = logging.getLogger(__name__)

# Driver setup with selenium-stealth
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--disable-extensions")
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
prefs = {"profile.managed_default_content_settings.images": 2}
options.add_experimental_option("prefs", prefs)
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
service = Service(executable_path="/home/ali/.local/bin/chromedriver")
driver = webdriver.Chrome(options=options, service=service)
stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True)

driver.implicitly_wait(10)

def scrapping(articles, data):
    for article in articles:
        try:
            driver.get(article)
            time.sleep(random.uniform(1, 3))
            li = []
            # Check for paywall
            try:
                paywall = driver.find_element(By.XPATH, "//div[contains(@class, 'paywall')]")
                logger.info(f"Paywall detected for {article}, skipping")
                li.extend([None, None, None, None, article])
                for key, value in zip(data.keys(), li):
                    data[key].append(value)
                continue
            except NoSuchElementException:
                pass
            # Scrape article data
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
                date = driver.find_element(By.XPATH, "//time[@itemprop='datePublished']").get_attribute('datetime')
                li.append(date)
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
    client = Minio(config.minio_endpoint,access_key=config.minio_acces_key,secret_key=config.minio_secret_key,secure=False)
    bucket_name = config.minio_bucket
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            logger.info(f"Created bucket {bucket_name}")
    except S3Error as e:
        logger.error(f"MinIO error: {e}")
    return client, bucket_name

def save_to_minio(client, bucket_name, df, filename=f"ft_articles_{datetime.now().strftime('%Y%m%d')}.csv"):
    try:
        csv_data = df.to_csv(index=False).encode("utf-8")
        client.put_object(bucket_name=bucket_name,object_name=filename,data=io.BytesIO(csv_data))
        logger.info(f"Saved {filename} to MinIO")
    except S3Error as e:
        logger.error(f"MinIO save error: {e}")

def main():
    data = {'title': [],'author': [],'date': [],'content': [],'link': []}
    minio_client, bucket_name = setup_minio()
    seen_articles = set()
    for url in config.base_urls:
        try:
            driver.get(url)
            time.sleep(2)
            articles = [a.get_attribute('href') for a in driver.find_elements(By.XPATH, "//a[@class='js-teaser-heading-link']") if 'content' in a.get_attribute('href') and a.get_attribute('href') not in seen_articles]
            seen_articles.update(articles)
            logger.info(f"Collected {len(articles)} unique links from {url}")
            scrapping(articles, data)
        except Exception as e:
            logger.error(f"Error accessing {url}: {e}")
            continue
    df = pd.DataFrame(data)
    if not df.empty:
        save_to_minio(minio_client, bucket_name, df)
    else:
        logger.warning("No data scraped")
    driver.quit()

if __name__ == '__main__':
    main()