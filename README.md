# Mr. Homes GA — 관악구 부동산 뉴스 자동 포스팅

인터넷 뉴스에서 **부동산 / 서울시 관악구** 관련 기사를 자동 수집하고,
Claude AI로 **블로그 포스트 + 카드뉴스**를 생성한 뒤 **Tistory 블로그**와 **Instagram**에 자동 업로드합니다.

> 이 저장소에는 별도 앱 두 개가 함께 있습니다:
> - [`dongne/`](dongne/README.md) — 재건축 동네분석 PWA
> - [`callnote/`](callnote/README.md) — 📞 통화노트: 통화 녹음/받아쓰기를 AI가 매물 접수·고객 상담 카드로 자동 정리하는 PWA

## 아키텍처

```
뉴스 수집 (Naver API / RSS)
    ↓
필터링 (부동산 + 관악구 키워드)
    ↓
Claude AI 콘텐츠 생성
  ├── 블로그 포스트 (HTML)
  ├── 카드뉴스 텍스트 (슬라이드 5~7장)
  └── 인스타그램 캡션 + 해시태그
    ↓
카드뉴스 이미지 생성 (Pillow, 1080×1080)
    ↓
동시 발행
  ├── Tistory 블로그 API
  └── Instagram Graph API (Carousel)
```

## 설치

```bash
pip install -r requirements.txt
cp .env.example .env
# .env 파일에 API 키 입력
```

## API 키 발급 안내

| 서비스 | 발급 방법 |
|--------|-----------|
| **Anthropic (Claude)** | https://console.anthropic.com |
| **Naver 검색 API** | https://developers.naver.com/apps → 검색 권한 신청 |
| **Tistory API** | https://www.tistory.com/guide/api → 앱 등록 후 Access Token 발급 |
| **Instagram Graph API** | Meta Developer → Instagram Basic Display 또는 Graph API (비즈니스 계정 필요) |
| **Imgbb (이미지 호스팅)** | https://imgbb.com/api (무료, Instagram 이미지 업로드에 필요) |

## 환경 변수 (.env)

```env
ANTHROPIC_API_KEY=...
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
TISTORY_ACCESS_TOKEN=...
TISTORY_BLOG_NAME=myblog        # myblog.tistory.com
INSTAGRAM_ACCESS_TOKEN=...
INSTAGRAM_ACCOUNT_ID=...
IMGBB_API_KEY=...               # 선택 (Instagram 발행 시 필요)
SCHEDULE_HOURS=8,12,18,21       # 자동 실행 시각 (KST, 쉼표 구분)
KEYWORDS=부동산,관악구,아파트
```

## 실행

```bash
# 즉시 1회 실행 (테스트)
python main.py --now

# 설정만 확인
python main.py --test

# 스케줄러 시작 (데몬)
python main.py
```

## 백그라운드 실행 (Linux systemd)

```bash
sudo cp mrhomesga.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mrhomesga
sudo systemctl start mrhomesga
sudo journalctl -u mrhomesga -f   # 로그 확인
```

## 생성 파일 구조

```
output/
├── blog/
│   └── YYYY-MM-DD_blog.html      # Tistory 미설정 시 로컬 저장
├── card_news/
│   └── YYYY-MM-DD/
│       ├── slide_01.jpg           # 표지
│       ├── slide_02.jpg
│       └── ...
└── logs/
    ├── mrhomesga.log
    └── run_YYYYMMDD_HHMM.json    # 실행 결과 요약
```

## 주의사항

- Instagram Graph API는 **비즈니스/크리에이터 계정**과 **Facebook 페이지 연결** 필요
- 이미지 발행 시 공개 URL 필요 → `IMGBB_API_KEY` 설정 권장
- Tistory Access Token은 만료 기간(60일) 확인 후 재발급 필요
