import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Naver Search API
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

# Tistory
TISTORY_ACCESS_TOKEN = os.getenv("TISTORY_ACCESS_TOKEN", "")
TISTORY_BLOG_NAME = os.getenv("TISTORY_BLOG_NAME", "")

# Instagram
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")

# Threads
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")

# Facebook Page
FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")

# Schedule (KST)
SCHEDULE_HOURS = [
    int(h.strip())
    for h in os.getenv("SCHEDULE_HOURS", "8,18").split(",")
    if h.strip().isdigit()
]

# Keywords
KEYWORDS = [k.strip() for k in os.getenv("KEYWORDS", "부동산,관악구,아파트").split(",")]

# Fixed target keywords always included
REAL_ESTATE_KEYWORDS = ["부동산", "아파트", "전세", "월세", "분양", "재개발", "재건축", "주택", "임대"]
GWANAK_KEYWORDS = ["관악구", "관악", "신림", "봉천", "낙성대", "서울대입구"]

# Card news dimensions
CARD_WIDTH = 1080
CARD_HEIGHT = 1080

# Blog thumbnail / body image dimensions
BLOG_THUMB_WIDTH = 1200
BLOG_THUMB_HEIGHT = 630     # OpenGraph 표준 비율 (1.91:1)
BLOG_BODY_WIDTH = 1200
BLOG_BODY_HEIGHT = 675      # 16:9
