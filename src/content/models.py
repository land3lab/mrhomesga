"""공유 데이터 모델."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GeneratedContent:
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    blog_title: str = ""
    blog_html: str = ""
    card_slides: list[dict] = field(default_factory=list)
    instagram_caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    source_articles: list = field(default_factory=list)
