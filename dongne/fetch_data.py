#!/usr/bin/env python3
"""재건축 동네분석 — 공공데이터 자동 조회 스크립트 (2단계 자동화)

공공데이터포털(data.go.kr) 인증키 하나로 아래 항목을 자동 조회해서
앱(index.html)의 "가져오기"로 불러올 수 있는 JSON을 만들어 줍니다.

  1. 아파트 매매 실거래 최고가 (국토교통부)  → 신축/해당동/재건축 최고가
  2. 아파트 전세 실거래 최고가 (국토교통부)  → 전세가율 계산용
  3. 상권 점포 수 (소상공인시장진흥공단)      → 동네 상권 점포수

준비:
  1) https://www.data.go.kr 회원가입(무료) 후 아래 3개 API 활용신청
     - "국토교통부_아파트 매매 실거래가 상세 자료"
     - "국토교통부_아파트 전월세 실거래가 자료"
     - "소상공인시장진흥공단_상가(상권)정보"
     (신청 즉시~1시간 내 자동 승인, 인증키는 공용 1개)
  2) 환경변수 또는 .env 에 키 저장:  DATA_GO_KR_KEY=발급받은키

사용 예 (안산시 상록구 본오동):
  python dongne/fetch_data.py \
      --name 본오동 \
      --lawd 41271 \
      --umd 본오동 \
      --adong 4127160000 \
      --months 6

  --lawd  : 법정동코드 앞 5자리(시군구). https://www.code.go.kr 에서 검색
  --umd   : 법정동(읍면동) 이름 — 실거래 결과를 이 동으로 필터링
  --adong : 행정동코드 10자리(상가정보용). 행정동이 여럿이면 쉼표로 나열
            예: --adong 4127160000,4127161000,4127162000
  --months: 최근 몇 개월치 실거래를 볼지 (기본 6)

출력: dongne/output/<동이름>.json  → 앱의 [가이드 → 가져오기]로 불러오기
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

try:  # 레포에 이미 있는 python-dotenv 활용 (없어도 동작)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

KEY = os.getenv("DATA_GO_KR_KEY", "")

TRADE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
RENT_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"
STORE_URL = "http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInDong"


def get(url: str, params: dict) -> bytes:
    qs = urllib.parse.urlencode({**params, "serviceKey": KEY})
    with urllib.request.urlopen(f"{url}?{qs}", timeout=30) as r:
        return r.read()


def recent_months(n: int) -> list[str]:
    """오늘 기준 최근 n개월의 YYYYMM 목록."""
    y, m = date.today().year, date.today().month
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def parse_items(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    code = root.findtext(".//resultCode", "")
    if code not in ("00", "000"):
        msg = root.findtext(".//resultMsg", "unknown")
        raise RuntimeError(f"API 오류 [{code}] {msg}")
    return [
        {el.tag: (el.text or "").strip() for el in item}
        for item in root.iter("item")
    ]


def fetch_trades(lawd: str, umd: str, months: int) -> dict:
    """법정동 umd의 최근 실거래를 단지별 최고가로 집계 (단위: 만원)."""
    by_apt: dict[str, dict] = {}
    for ym in recent_months(months):
        items = parse_items(get(TRADE_URL, {
            "LAWD_CD": lawd, "DEAL_YMD": ym, "numOfRows": 1000, "pageNo": 1,
        }))
        for it in items:
            if umd and it.get("umdNm", "") != umd:
                continue
            apt = it.get("aptNm", "?")
            try:
                price = int(it["dealAmount"].replace(",", ""))
                area = float(it["excluUseAr"])
            except (KeyError, ValueError):
                continue
            py = round(price / (area / 3.3058))  # 평당가(만원) — 전용면적 기준
            cur = by_apt.setdefault(apt, {"max": 0, "py": 0, "n": 0})
            cur["n"] += 1
            if price > cur["max"]:
                cur["max"], cur["py"] = price, py
    return by_apt


def fetch_rents(lawd: str, umd: str, months: int) -> dict:
    """전세(보증금만, 월세 0) 실거래를 단지별 최고 보증금으로 집계 (만원)."""
    by_apt: dict[str, int] = {}
    for ym in recent_months(months):
        items = parse_items(get(RENT_URL, {
            "LAWD_CD": lawd, "DEAL_YMD": ym, "numOfRows": 1000, "pageNo": 1,
        }))
        for it in items:
            if umd and it.get("umdNm", "") != umd:
                continue
            if it.get("monthlyRent", "0").replace(",", "") not in ("", "0"):
                continue  # 월세 제외 → 순수 전세만
            apt = it.get("aptNm", "?")
            try:
                deposit = int(it["deposit"].replace(",", ""))
            except (KeyError, ValueError):
                continue
            by_apt[apt] = max(by_apt.get(apt, 0), deposit)
    return by_apt


def fetch_store_count(adong_codes: list[str]) -> int:
    """행정동코드(들)의 상가업소 총 개수 합계."""
    total = 0
    for code in adong_codes:
        raw = get(STORE_URL, {
            "divId": "adongCd", "key": code, "type": "json", "numOfRows": 1, "pageNo": 1,
        })
        body = json.loads(raw)["body"]
        total += int(body.get("totalCount", 0))
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help="동 이름 (앱에 표시될 이름, 예: 본오동)")
    ap.add_argument("--lawd", required=True, help="법정동코드 앞 5자리 (시군구)")
    ap.add_argument("--umd", default="", help="법정동(읍면동) 이름 필터, 예: 본오동")
    ap.add_argument("--adong", default="", help="행정동코드 10자리 (쉼표 구분 복수 가능)")
    ap.add_argument("--months", type=int, default=6, help="실거래 조회 개월 수 (기본 6)")
    args = ap.parse_args()

    if not KEY:
        sys.exit("환경변수 DATA_GO_KR_KEY 가 없습니다. .env 에 추가하세요.")

    rec: dict = {"name": args.name}

    print(f"▶ 매매 실거래 조회 중 ({args.months}개월)…")
    trades = fetch_trades(args.lawd, args.umd, args.months)
    print(f"▶ 전세 실거래 조회 중…")
    rents = fetch_rents(args.lawd, args.umd, args.months)

    if trades:
        ranked = sorted(trades.items(), key=lambda kv: kv[1]["max"], reverse=True)
        print(f"\n  {args.umd or args.lawd} 단지별 최고가 (최근 {args.months}개월, 만원):")
        for apt, v in ranked[:15]:
            jeonse = rents.get(apt)
            js = f"  전세 {jeonse:,}" if jeonse else ""
            print(f"   - {apt:<20s} 매매 {v['max']:>7,} (평당 {v['py']:,}, {v['n']}건){js}")
        top_apt, top = ranked[0]
        rec.update({
            "dongAptName": top_apt,
            "dongAptPrice": top["max"],
            "dongAptPy": top["py"],
        })
        if rents.get(top_apt):
            rec["jeonseDong"] = rents[top_apt]
        print(f"\n  → 해당 동 최고가로 '{top_apt}' 자동 선택 (신축/재건축 단지는 목록 보고 앱에서 지정)")
    else:
        print("  거래 내역 없음 — 기간(--months)을 늘려 보세요.")

    if args.adong:
        print("▶ 상권 점포 수 조회 중…")
        rec["stores"] = fetch_store_count(args.adong.split(","))
        print(f"  → 점포 수: {rec['stores']:,}")

    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{args.name}.json"
    out.write_text(json.dumps([rec], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 저장: {out}\n   앱 [가이드 → 가져오기]에서 이 파일을 불러오면 자동 반영됩니다.")


if __name__ == "__main__":
    main()
