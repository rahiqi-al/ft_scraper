# FT.com Scraper Documentation

---

## 1. Overview

The FT.com Scraper is a sophisticated web scraping tool, designed to extract timely data from the Financial Times website. This solution targets search results for specified terms (e.g., "tech", "finance", "markets", "companies"), leveraging `flaresolverr` to address Cloudflare protections. It gathers metadata such as links, categories, titles, and snippets, while checking articles for paywalls and logging accessible content. The project emphasizes automation and scalability, utilizing JavaScript-based scraping, multiprocessing, daily scheduling, and secure MinIO storage.

### Key Features
- Dynamic content rendering with undetected_chromedriver.
- Partial Cloudflare bypass using flaresolverr.
- Efficient multiprocessing for concurrent term processing.
- Automated daily scheduling with the `schedule` library.
- Persistent data storage via MinIO.

### Achievements
- Successfully deploys undetected_chromedriver for dynamic FT.com page rendering.
- Achieves intermittent Cloudflare bypass, passing verification in some instances despite spinner challenges.
- Implements multiprocessing to handle multiple search terms simultaneously.
- Establishes a reliable daily scheduling framework.
- Ensures data security and accessibility with MinIO storage and error management.

### Limitations
- **Paywall Restriction**: Detects paywalls but cannot bypass them .
- **Cloudflare Issue**: Partial success with flaresolverr; verification spinner persists in some cases.

---

## 2. Project Structure

```
ft_scraper/
├── command.sh           
├── config/              # Configuration directory
│   ├── config.py        # Python configuration loader
│   ├── config.yml       # YAML file for search term definitions
│   └── __init__.py      
├── logs/                # Logging directory
│   └── app.log          # Application log file
├── README.md            # documentation
├── requirements.txt     # List of Python dependencies
└── scraper.py           # Main scraping script
```

---

## 3. Installation & Setup

### 3.1 Create Virtual Environment
Initialize a virtual environment named `venv` to isolate dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3.2 Install Dependencies
Install the required packages from `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 3.3 Configure Environment Variables
Create a `.env` file in the root directory with the following settings:
```
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=ali
MINIO_SECRET_KEY=aliali123
MINIO_BUCKET=ft-articles
LINK_BUCKET=ft-links
ARTICLE_BUCKET=ft-articles
```

### 3.4 Configure Search Terms
Edit `config/config.yml` to define `search_terms` (e.g., `["tech", "finance", "markets", "companies"]`). Ensure MinIO and flaresolverr are running locally (setup assumed to be handled separately).

---

## 4. Cloning the Repository
Clone the repository to your local machine using the following command:
```bash
git clone https://github.com/rahiqi-al/ft_scraper.git
cd ft_scraper
```

---

## 5. Usage
Run the scraper script:
```bash
python3 scraper.py
```
- Executes automatically at midnight daily (configurable; e.g., 20:52 for testing).
- Processes search terms concurrently using multiprocessing for enhanced performance.
- Checks articles for paywalls and logs accessible links.
- Stores data in MinIO:
  - Links: `ft-links_links_YYYYMMDD.csv`
  - Accessible articles: `ft-articles_accessible_YYYYMMDD.csv`
- Monitor execution logs in `logs/app.log`. Terminate with `Ctrl+C`.

---

## 6. Technical Approach

### 6.1 Scraping Methodology
- **JavaScript Rendering**: Uses undetected_chromedriver with Selenium to manage dynamic FT.com content.
- **Cloudflare Management**: Integrates flaresolverr for cookie retrieval and challenge resolution, with partial success (passes occasionally).
- **Swarm Processing**: Employs a multiprocessing Pool for parallel term scraping, optimizing efficiency.
- **Paywall Detection**: Identifies paywalls via XPath, skips restricted content.
- **Scheduling**: Leverages the `schedule` library for daily midnight runs.
- **Data Storage**: Secures data in MinIO using CSV format.
- **Error Handling**: Implements retries for spinner issues, comprehensive logging, and skips invalid cookies.

### 6.2 24-Hour Filter
The search is configured with `dateRange=now-24h` to restrict results to the latest 24 hours of news. This aligns with the daily midnight schedule, ensuring only fresh content is captured and avoiding redundant data.

---

## 7. Future Considerations
- Enhance Cloudflare bypass with advanced proxy or CAPTCHA-solving techniques.
- Explore legal avenues for paywall access (e.g., API integration with proper licensing).