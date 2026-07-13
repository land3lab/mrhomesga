#!/usr/bin/env python3
"""재건축 동네분석 — 공공데이터 자동 조회 스크립트 (2단계 자동화)

공공데이터포털(data.go.kr) 인증키 하나로 아래 항목을 자동 조회해서
앱(index.html)이 읽는 dongne/output/auto.json 을 만들어 줍니다.

  1. 아파트 매매 실거래 최고가·평당가 (국토교통부) → 신축/해당동/재건축 최고가
  2. 아파트 전세 실거래 최고 보증금 (국토교통부)   → 전세가율 계산
  3. 상권 점포 수 (소상공인시장진흥공단)           → 동네 상권 점포수
     (시군구 전체를 받아 행정동 이름으로 집계 — 행정동코드 몰라도 됨)

준비 (한 번만):
  1) https://www.data.go.kr 회원가입(무료) 후 아래 3개 API 활용신청
     - "국토교통부_아파트 매매 실거래가 상세 자료"
     - "국토교통부_아파트 전월세 실거래가 자료"
     - "소상공인시장진흥공단_상가(상권)정보"
     (신청 즉시~1시간 내 자동 승인, 인증키는 공용 1개)
  2) 환경변수 또는 .env 에 키 저장:  DATA_GO_KR_KEY=발급받은키

사용:
  # 권장 — targets.json에 등록된 동네 전부 일괄 조회 (GitHub Actions가 매월 실행)
  python dongne/fetch_data.py --config dongne/targets.json

  # 단발 조회
  python dongne/fetch_data.py --name 본오동 --lawd 41271 --umd 본오동 --adong-prefix 본오

출력: dongne/output/auto.json — 앱이 시작할 때 자동으로 불러오고,
      [가이드 → 가져오기]로 수동 임포트도 가능합니다.
"""
import argparse
import json
import math
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

try:  # 레포에 이미 있는 python-dotenv 활용 (없어도 동작)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

KEY = os.getenv("DATA_GO_KR_KEY", "").strip()

TRADE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
RENT_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"
STORE_URL = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInDong"
PAGE = 1000  # 한 페이지 최대 행 수


def get(url: str, params: dict) -> bytes:
    qs = urllib.parse.urlencode(params)
    # Encoding 키(% 포함)는 이미 인코딩된 상태이므로 그대로 붙여 이중 인코딩을 피한다
    key = KEY if "%" in KEY else urllib.parse.quote(KEY, safe="")
    req = urllib.request.Request(
        f"{url}?{qs}&serviceKey={key}",
        headers={"User-Agent": "Mozilla/5.0 (dongne-analysis)"},  # 기본 UA는 WAF에 차단됨
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code} ({url.rsplit('/', 1)[-1]}): {body}") from None


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


def fetch_rtms(url: str, lawd: str, months: int) -> list[dict]:
    """국토부 실거래 API를 최근 months개월 × 전체 페이지 순회해 items 반환."""
    items: list[dict] = []
    for ym in recent_months(months):
        page = 1
        while True:
            chunk = parse_items(get(url, {
                "LAWD_CD": lawd, "DEAL_YMD": ym,
                "numOfRows": PAGE, "pageNo": page,
            }))
            items.extend(chunk)
            if len(chunk) < PAGE:
                break
            page += 1
    return items


def agg_trades(items: list[dict], umd: str = "") -> dict[str, dict]:
    """단지별 매매 최고가/평당가 집계 (단위: 만원). umd가 있으면 해당 법정동만."""
    by_apt: dict[str, dict] = {}
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
        cur = by_apt.setdefault(apt, {"max": 0, "py": 0, "n": 0, "umd": it.get("umdNm", "")})
        cur["n"] += 1
        if price > cur["max"]:
            cur["max"], cur["py"] = price, py
    return by_apt


def agg_rents(items: list[dict], umd: str = "") -> dict[str, int]:
    """단지별 순수 전세(월세 0) 최고 보증금 집계 (만원)."""
    by_apt: dict[str, int] = {}
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


def pick(agg: dict[str, dict], keyword: str) -> tuple[str, dict] | None:
    """단지명 부분 일치로 선택. 여러 개면 거래 건수가 가장 많은 단지."""
    hits = [(apt, v) for apt, v in agg.items() if keyword in apt]
    if not hits:
        return None
    return max(hits, key=lambda kv: kv[1]["n"])


def fetch_store_count(signgu: str, adong_prefix: str) -> int:
    """시군구 상가업소 전체를 페이지 순회하며 행정동 이름 접두어로 점포수 집계."""
    first = json.loads(get(STORE_URL, {
        "divId": "signguCd", "key": signgu, "type": "json",
        "numOfRows": PAGE, "pageNo": 1,
    }))["body"]
    total = int(first.get("totalCount", 0))
    count = sum(1 for it in first.get("items") or []
                if it.get("adongNm", "").startswith(adong_prefix))
    for page in range(2, math.ceil(total / PAGE) + 1):
        body = json.loads(get(STORE_URL, {
            "divId": "signguCd", "key": signgu, "type": "json",
            "numOfRows": PAGE, "pageNo": page,
        }))["body"]
        count += sum(1 for it in body.get("items") or []
                     if it.get("adongNm", "").startswith(adong_prefix))
    return count


def build_record(t: dict, months: int) -> dict:
    """대상 동 하나를 조회해 앱 임포트 형식 레코드로 반환."""
    name, lawd, umd = t["name"], t["lawd"], t.get("umd", "")
    apts = t.get("apts", {})
    rec: dict = {"name": name}

    print(f"\n━━ {name} (시군구 {lawd}) ━━")
    print(f"▶ 매매 실거래 조회 중 ({months}개월)…")
    try:
        trades_all = agg_trades(fetch_rtms(TRADE_URL, lawd, months))
    except Exception as e:  # 개별 API 실패는 경고만 하고 나머지 항목은 계속 수집
        print(f"  ⚠ 매매 조회 실패 (아파트 매매 실거래가 API 활용신청/승인 확인): {e}")
        trades_all = {}
    trades_umd = {a: v for a, v in trades_all.items() if not umd or v["umd"] == umd}
    print(f"▶ 전세 실거래 조회 중…")
    try:
        rents_all = agg_rents(fetch_rtms(RENT_URL, lawd, months))
    except Exception as e:
        print(f"  ⚠ 전세 조회 실패 (아파트 전월세 실거래가 API 활용신청/승인 확인): {e}")
        rents_all = {}

    ranked = sorted(trades_umd.items(), key=lambda kv: kv[1]["max"], reverse=True)
    if ranked:
        print(f"  {umd or lawd} 단지별 최고가 (최근 {months}개월, 만원):")
        for apt, v in ranked[:15]:
            jeonse = rents_all.get(apt)
            js = f"  전세 {jeonse:,}" if jeonse else ""
            print(f"   - {apt:<22s} 매매 {v['max']:>7,} (평당 {v['py']:,}, {v['n']}건){js}")
    else:
        print("  ⚠ 거래 내역 없음 — months를 늘리거나 umd 이름을 확인하세요.")

    # 신축(new)은 시군구 전체에서, 해당동(dong)/재건축(rebuild)은 법정동 안에서 검색
    for role, scope, price_key, py_key, name_key in [
        ("new", trades_all, "newAptPrice", "newAptPy", "newAptName"),
        ("dong", trades_umd, "dongAptPrice", "dongAptPy", "dongAptName"),
        ("rebuild", trades_umd, "rebuildAptPrice", "rebuildAptPy", "rebuildAptName"),
    ]:
        kw = apts.get(role)
        if not kw:
            continue
        hit = pick(scope, kw)
        if not hit:
            print(f"  ⚠ '{kw}'({role}) 단지의 최근 거래를 찾지 못함")
            continue
        apt, v = hit
        rec[name_key], rec[price_key], rec[py_key] = apt, v["max"], v["py"]
        jeonse = rents_all.get(apt)
        if role == "new" and jeonse:
            rec["jeonseNew"] = jeonse
        if role == "dong" and jeonse:
            rec["jeonseDong"] = jeonse
        print(f"  ✓ {role:7s} {apt}: 매매 {v['max']:,} / 평당 {v['py']:,}"
              + (f" / 전세 {jeonse:,}" if jeonse and role in ("new", "dong") else ""))

    prefix = t.get("adongPrefix")
    if prefix:
        print(f"▶ 상가 점포 수 집계 중 ('{prefix}*' 행정동)…")
        try:
            rec["stores"] = fetch_store_count(lawd, prefix)
            print(f"  ✓ 점포 수: {rec['stores']:,}")
        except Exception as e:
            print(f"  ⚠ 상가 조회 실패 (상가(상권)정보 API 활용신청/승인 확인): {e}")

    rec["autoUpdatedAt"] = datetime.now().strftime("%Y-%m-%d")
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="targets.json 경로 (일괄 조회 모드)")
    ap.add_argument("--name", help="동 이름 (단발 조회)")
    ap.add_argument("--lawd", help="법정동코드 앞 5자리 (시군구)")
    ap.add_argument("--umd", default="", help="법정동(읍면동) 이름 필터")
    ap.add_argument("--adong-prefix", default="", help="상가 집계용 행정동 이름 접두어 (예: 본오)")
    ap.add_argument("--months", type=int, default=0, help="실거래 조회 개월 수 (기본 6)")
    args = ap.parse_args()

    if not KEY:
        sys.exit("환경변수 DATA_GO_KR_KEY 가 없습니다. .env 또는 GitHub Secrets에 추가하세요.")

    if args.config:
        cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
        months = args.months or cfg.get("months", 6)
        targets = cfg["targets"]
    elif args.name and args.lawd:
        months = args.months or 6
        targets = [{"name": args.name, "lawd": args.lawd, "umd": args.umd,
                    "adongPrefix": args.adong_prefix}]
    else:
        ap.error("--config 또는 --name/--lawd 를 지정하세요")

    records = []
    for t in targets:
        try:
            records.append(build_record(t, months))
        except Exception as e:  # 한 동네가 실패해도 나머지는 계속
            print(f"  ✗ {t.get('name')} 조회 실패: {e}", file=sys.stderr)

    if not records:
        sys.exit("조회된 데이터가 없습니다.")

    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "auto.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 저장: {out}")
    print("   웹으로 배포된 앱은 다음 접속 때 자동 반영, 파일로 쓰는 앱은 [가져오기]로 불러오세요.")


if __name__ == "__main__":
    main()
