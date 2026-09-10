# Mr. Homes GA — 부동산 뉴스 자동 콘텐츠 생성 & 승인 발행

인터넷 뉴스에서 **전국 부동산** 관련 기사를 자동 수집(서울시 관악구는 우선순위 태그)하고,
Claude AI로 **블로그 포스트 + 카드뉴스 + 인스타그램/쓰레드/페이스북 캡션**과 이미지를 생성합니다.

> ⚠️ **회사 정책: 대외 발행은 AI가 단독으로 확정하지 않습니다.**
> 매일 자동 실행되는 것은 **"초안 생성"** 까지입니다. 생성된 초안은 `output/pending/<날짜>/`에
> 저장되며, 담당자가 내용을 검토한 뒤 `python main.py --publish <날짜>` 명령을 직접 실행해야
> 비로소 Tistory / Instagram / Threads / Facebook에 실제로 게시됩니다.

> 이 저장소에는 별도 앱들이 함께 있습니다:
> - [`dongne/`](dongne/README.md) — 재건축 동네분석 PWA
> - [`callnote/`](callnote/README.md) — 📞 매통이: 통화 녹음/받아쓰기를 AI가 매물 접수·고객 상담 카드로 자동 정리하는 PWA
> - [`callnote-android/`](callnote-android/README.md) — 📱 매통이 안드로이드 앱: 통화 종료를 자동 감지해 녹음 정리 알림을 띄우는 네이티브 래퍼

## 아키텍처

```
뉴스 수집 (RSS 피드가 기본 — 키 불필요, 전국 부동산 + 관악구 우선순위)
  ※ Naver 검색 API 키를 넣으면 그쪽을 우선 사용 (선택 사항, 없어도 정상 동작)
    ↓
필터링 (부동산 키워드, 관악구는 combined 태그로 상위 노출)
    ↓
Claude AI 콘텐츠 생성
  ├── 블로그 포스트 (HTML) + 핵심 하이라이트 문장
  ├── 카드뉴스 텍스트 (슬라이드 5~7장)
  ├── 인스타그램 캡션 + 해시태그
  ├── 쓰레드(Threads) 캡션
  └── 페이스북 캡션
    ↓
이미지 생성 (Pillow)
  ├── 카드뉴스 1080×1080 (인스타/쓰레드용)
  └── 블로그 썸네일 1200×630 + 본문 삽입 이미지
    ↓
[초안 저장] output/pending/<날짜>/manifest.json  ← 여기서 자동화 중단, 담당자 검토
    ↓ (담당자 승인 후 --publish 실행)
실제 발행
  ├── Tistory 블로그 API (썸네일·본문 이미지 삽입)
  ├── Instagram Graph API (Carousel)
  ├── Threads API (텍스트/이미지/캐러셀)
  └── Facebook Page Graph API (다중 사진 게시글)
```

## 설치

```bash
pip install -r requirements.txt
cp .env.example .env
# .env 파일에 API 키 입력

# 한글이 포함된 이미지를 만들므로 한글 폰트가 반드시 필요합니다.
sudo apt install fonts-nanum   # 또는 fonts-noto-cjk
```

## API 키 발급 안내

| 서비스 | 발급 방법 |
|--------|-----------|
| **Anthropic (Claude)** | https://console.anthropic.com |
| **Naver 검색 API** (선택) | https://developers.naver.com/apps → 검색 권한 신청. ⚠️ 계정에 따라 애플리케이션 등록 화면의 "사용 API" 목록에 "검색"이 안 보이는 경우가 있음(정책 변경 추정, 미확인) — 이땐 네이버 문의하기로 확인 필요. **없어도 RSS 피드로 정상 동작하므로 필수 아님.** |
| **Tistory API** | https://www.tistory.com/guide/api → 앱 등록 후 Access Token 발급 |
| **Instagram Graph API** | Meta Developer → Instagram Graph API (비즈니스 계정 + Facebook 페이지 연결 필요) |
| **Threads API** | Meta Developer → Threads API (threads_basic, threads_content_publish 권한) |
| **Facebook Page Graph API** | Meta Developer → 페이지 액세스 토큰 (pages_manage_posts 권한) |
| **Imgbb (이미지 호스팅)** | https://imgbb.com/api (무료, Instagram/Threads/블로그 이미지 삽입에 필요) |

각 플랫폼 토큰은 회사 승인을 받은 **업무용 계정**으로만 발급받아 사용하세요.

## 환경 변수 (.env)

전체 목록은 [`.env.example`](.env.example) 참고. 핵심 항목:

```env
ANTHROPIC_API_KEY=...
NAVER_CLIENT_ID=... / NAVER_CLIENT_SECRET=...   # 선택 — 비워두면 RSS 피드로 자동 대체
TISTORY_ACCESS_TOKEN=... / TISTORY_BLOG_NAME=myblog
INSTAGRAM_ACCESS_TOKEN=... / INSTAGRAM_ACCOUNT_ID=...
THREADS_ACCESS_TOKEN=... / THREADS_USER_ID=...
FACEBOOK_PAGE_ACCESS_TOKEN=... / FACEBOOK_PAGE_ID=...
IMGBB_API_KEY=...               # 이미지 공개 호스팅 (선택이지만 강력 권장)
SCHEDULE_HOURS=8,12,18,21       # 초안 자동 생성 시각 (KST)
```

플랫폼 토큰이 없는 상태로도 동작합니다 — 해당 플랫폼은 발행 시 `skipped` 처리되거나
(블로그는) 로컬 HTML 파일로 저장됩니다.

## 실행

```bash
# 1) 초안 생성 (뉴스 수집 → 콘텐츠 → 이미지). 발행은 하지 않음.
python main.py --now

# 2) 승인 대기 중인 초안 목록 확인
python main.py --list-pending

# 3) 담당자 검토 후 실제 발행 (기본: 전체 플랫폼)
python main.py --publish latest
python main.py --publish 2025-01-01
python main.py --publish latest --platforms blog,instagram   # 일부 플랫폼만

# 설정만 확인
python main.py --test

# 스케줄러 시작 — 매일 설정된 시각에 "초안"만 자동 생성 (데몬)
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

systemd로 상시 구동하는 것은 **초안 생성 스케줄러**입니다. 실제 발행은 담당자가
서버에 접속해 `--publish` 명령을 실행하거나, 별도의 승인 절차를 거쳐야 합니다.

## 생성 파일 구조

```
output/
├── pending/<날짜>/manifest.json     # 승인 대기 중인 초안 (콘텐츠 전문 + 이미지 경로)
├── published/<날짜>/
│   ├── manifest.json                # 발행된 콘텐츠 스냅샷
│   └── publish_result.json          # 플랫폼별 발행 결과
├── blog/<날짜>_blog.html            # Tistory 미설정 시 로컬 저장(썸네일·본문 이미지 삽입됨)
├── blog_images/<날짜>/
│   ├── thumbnail.jpg                # 1200×630 대표 썸네일
│   └── body_0X.jpg                  # 본문 삽입용 하이라이트 이미지
├── card_news/<날짜>/
│   ├── slide_01.jpg                 # 표지
│   └── ...
└── logs/
    ├── mrhomesga.log
    └── run_YYYYMMDD_HHMM.json       # 초안 생성 실행 결과 요약
```

## 주의사항

- **한글 폰트 필수**: `fonts-nanum` 또는 `fonts-noto-cjk` 미설치 시 이미지의 한글이 깨져 보입니다(실행 시 경고 로그로 안내).
- Instagram/Threads Graph API는 **비즈니스/크리에이터 계정**과 **Facebook 페이지 연결** 필요
- 카드뉴스·블로그 이미지는 공개 URL이 필요 → `IMGBB_API_KEY` 설정 권장 (미설정 시 Instagram/Threads는 스킵, 블로그는 로컬 이미지 참조로 저장)
- Facebook은 로컬 이미지를 직접 업로드하므로 Imgbb 없이도 동작
- Tistory Access Token은 만료 기간(60일) 확인 후 재발급 필요
- 뉴스 수집 범위는 `src/news/fetcher.py`의 `NATIONAL_QUERIES`(전국)/`GWANAK_QUERIES`(관악구 우선순위)로 조정
- **뉴스 수집은 Naver API 키 없이 RSS 피드만으로 기본 동작합니다.** Naver 검색 API는 정확도를 높이고 싶을 때 추가하는 선택 사항이며, 발급이 막혀 있어도 시스템 운영에 지장이 없습니다.
- 실제 SNS/블로그 계정 연결과 자동 게시는 **담당자·조직장 승인** 후 진행하세요
