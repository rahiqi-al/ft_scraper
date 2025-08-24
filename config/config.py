import yaml
from dotenv import load_dotenv
import os




load_dotenv()

class config():


    with open('config/config.yml','r') as file :
        config_data = yaml.load(file,Loader = yaml.FullLoader)

    

    base_urls = config_data["SCRAPER"]["BASE_URLS"]

    minio_endpoint = os.getenv("MINIO_ENDPOINT")
    minio_acces_key = os.getenv("MINIO_ACCESS_KEY")
    minio_secret_key = os.getenv("MINIO_SECRET_KEY")
    minio_bucket = os.getenv("MINIO_BUCKET")







config = config()

# print(config.base_urls)