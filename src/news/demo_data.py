"""
API 키 없이 카드뉴스 생성을 테스트할 수 있는 샘플 뉴스 데이터.
"""

from datetime import datetime
from src.news.fetcher import NewsItem

SAMPLE_NEWS: list[NewsItem] = [
    NewsItem(
        title="관악구 신림동 재개발 조합 설립 인가… 2000세대 규모",
        description=(
            "서울시 관악구 신림동 1234번지 일대 재개발 정비사업 조합이 공식 설립 인가를 받았다. "
            "총 2000세대 규모의 아파트 단지로 조성될 예정이며, 2027년 착공을 목표로 하고 있다. "
            "조합 측은 일반분양 물량의 60% 이상을 전용 59㎡ 이하 중소형으로 구성할 계획이라고 밝혔다."
        ),
        link="https://example.com/news/1",
        published=datetime.now(),
        source="sample",
    ),
    NewsItem(
        title="서울 전세가격 3주 연속 하락… 관악·동작구 낙폭 커",
        description=(
            "한국부동산원이 발표한 주간 아파트 가격 동향에 따르면 서울 전세가격이 3주 연속 하락세를 보이고 있다. "
            "특히 관악구(-0.18%)와 동작구(-0.15%)의 낙폭이 서울 평균을 웃돌았다. "
            "전문가들은 입주 물량 증가와 금리 부담이 겹치면서 전세 수요가 줄어들고 있다고 분석했다."
        ),
        link="https://example.com/news/2",
        published=datetime.now(),
        source="sample",
    ),
    NewsItem(
        title="서울대입구역 인근 오피스텔 월세 강세… 1인 가구 수요 급증",
        description=(
            "서울대입구역(관악구 봉천동) 인근 오피스텔의 월세가 전년 대비 평균 8% 상승한 것으로 나타났다. "
            "1인 가구와 청년층 수요가 꾸준히 증가하면서 소형 주거 공간에 대한 수요가 높아지고 있다. "
            "전용 20㎡ 이하 소형 오피스텔의 평균 월세는 60~75만 원 수준을 형성하고 있다."
        ),
        link="https://example.com/news/3",
        published=datetime.now(),
        source="sample",
    ),
    NewsItem(
        title="정부, 신림선 연장 추진… 관악구 교통 편의 향상 기대",
        description=(
            "국토교통부가 경전철 신림선의 여의도 방면 연장을 본격 추진한다고 밝혔다. "
            "연장 구간이 완공되면 관악구에서 여의도까지 약 15분 이내에 접근이 가능해져 "
            "인근 부동산 시장에도 긍정적인 영향을 줄 것으로 전망된다. "
            "사업 완료는 2030년을 목표로 한다."
        ),
        link="https://example.com/news/4",
        published=datetime.now(),
        source="sample",
    ),
    NewsItem(
        title="관악구 봉천동 아파트 매매가 회복세… 3개월 만에 반등",
        description=(
            "관악구 봉천동 일대 아파트 매매가격이 3개월 만에 반등세로 돌아섰다. "
            "봉천 푸르지오 전용 84㎡가 이달 7억 4000만 원에 손바뀜되며 "
            "지난 분기 저점 대비 2000만 원 상승했다. "
            "실수요자 중심의 거래가 이어지면서 관악구 전반적인 매매 심리도 회복 중이다."
        ),
        link="https://example.com/news/5",
        published=datetime.now(),
        source="sample",
    ),
]
