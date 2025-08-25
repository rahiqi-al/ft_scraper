import yaml
from dotenv import load_dotenv
import os




load_dotenv()

class config():


    with open('config/config.yml','r') as file :
        config_data = yaml.load(file,Loader = yaml.FullLoader)

    

    base_urls = config_data["SCRAPER"]["BASE_URLS"]
    search_terms = config_data["SEARCH_TERMS"]


    minio_endpoint = os.getenv("MINIO_ENDPOINT")
    minio_acces_key = os.getenv("MINIO_ACCESS_KEY")
    minio_secret_key = os.getenv("MINIO_SECRET_KEY")
    minio_bucket = os.getenv("MINIO_BUCKET")
    article_bucket = os.getenv("ARTICLE_BUCKET")
    link_bucket = os.getenv("LINK_BUCKET")








config = config()

# print(config.article_bucket,config.link_bucket,config.search_terms)