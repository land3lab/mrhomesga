/**
 * RSAR Land3 매통이 — 라이선스 서버 로직 (자동 업데이트되는 본체)
 * ──────────────────────────────────────────────────────────────
 * 판매자(RSAR)의 Apps Script가 이 파일을 불러와 실행한다.
 * 구글 드라이브에 "매통이 라이선스" 스프레드시트를 자동 생성하며,
 * 그 시트가 곧 관리 화면이다:
 *
 *  - [코드] 탭: 판매자가 직접 행을 추가해 이용코드를 발급한다
 *      A: 코드 (예: MT-GWANAK-01)   B: 만료일 (예: 2027-07-18, 비우면 무기한)
 *      C: 메모 (예: 관악A사무실)     D~: 사용 기기/최초 사용일 (자동 기록)
 *  - [기기] 탭: 앱 설치 기기별 최초 실행일 자동 기록 (체험 30일 기준)
 *
 * ⚠️ 탭/열 구조를 바꾸면 호환이 깨진다.
 */

var LIC_FILE = "매통이 라이선스";
var TAB_CODES = "코드";
var TAB_DEVICES = "기기";
var CODE_HEADERS = ["코드", "만료일", "메모", "사용기기수", "최초사용일"];
var DEV_HEADERS = ["기기ID", "최초실행일", "마지막접속", "이용코드"];

function getSs_() {
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty("licssid");
  if (id) { try { return SpreadsheetApp.openById(id); } catch (err) {} }
  var active = SpreadsheetApp.getActiveSpreadsheet();
  var ss = active || SpreadsheetApp.create(LIC_FILE);
  props.setProperty("licssid", ss.getId());
  return ss;
}
function getTab_(ss, name, headers) {
  var sh = ss.getSheetByName(name) || ss.insertSheet(name);
  if (sh.getLastRow() === 0) sh.appendRow(headers);
  return sh;
}
function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
function fmtDate_(d) {
  return Utilities.formatDate(d, Session.getScriptTimeZone(), "yyyy-MM-dd");
}

function handleGet(e) {
  var p = (e && e.parameter) || {};
  var ss = getSs_();

  if (p.action === "check") {
    var lock = LockService.getScriptLock();
    lock.waitLock(10000);
    try {
      var out = { ok: true };
      var now = new Date();

      /* ── 기기 등록 / 최초 실행일 조회 (체험 기간 기준) ── */
      var device = String(p.device || "").slice(0, 64);
      if (device) {
        var dsh = getTab_(ss, TAB_DEVICES, DEV_HEADERS);
        var dvals = dsh.getDataRange().getValues();
        var drow = 0;
        for (var i = 1; i < dvals.length; i++) {
          if (String(dvals[i][0]) === device) { drow = i + 1; break; }
        }
        if (drow) {
          var first = dvals[drow - 1][1];
          out.trialStart = (first instanceof Date) ? first.getTime() : new Date(first).getTime();
          dsh.getRange(drow, 3).setValue(now);
          if (p.code) dsh.getRange(drow, 4).setValue(String(p.code));
        } else {
          dsh.appendRow([device, now, now, String(p.code || "")]);
          out.trialStart = now.getTime();
        }
      }

      /* ── 이용코드 검증 ── */
      if (p.code) {
        var code = String(p.code).trim().toUpperCase();
        var csh = getTab_(ss, TAB_CODES, CODE_HEADERS);
        var cvals = csh.getDataRange().getValues();
        var found = null, crow = 0;
        for (var j = 1; j < cvals.length; j++) {
          if (String(cvals[j][0]).trim().toUpperCase() === code) { found = cvals[j]; crow = j + 1; break; }
        }
        if (!found) {
          out.license = { valid: false, reason: "no_code" };
        } else {
          var until = found[1];
          var untilDate = (until instanceof Date) ? until : (until ? new Date(until) : null);
          if (untilDate && !isNaN(untilDate) && untilDate.getTime() < now.getTime() - 86400000) {
            out.license = { valid: false, reason: "expired", until: fmtDate_(untilDate) };
          } else {
            out.license = {
              valid: true,
              until: untilDate && !isNaN(untilDate) ? fmtDate_(untilDate) : "2099-12-31",
            };
            // 사용 현황 자동 기록 (판매자 참고용)
            var cnt = Number(found[3] || 0);
            if (!found[4]) csh.getRange(crow, 5).setValue(now);
            csh.getRange(crow, 4).setValue(cnt + 1);
          }
        }
      }
      return json_(out);
    } finally {
      lock.releaseLock();
    }
  }

  // 연결 테스트: 시트 주소 반환 (판매자 본인 확인용)
  // 이때 [코드]/[기기] 탭을 미리 만들어 둔다 — 판매자가 시트를 열면 바로 장부 구조가 보이도록
  getTab_(ss, TAB_CODES, CODE_HEADERS);
  getTab_(ss, TAB_DEVICES, DEV_HEADERS);
  return json_({ ok: true, sheet: ss.getUrl() });
}

function handlePost(e) { // 예비 (현재 미사용)
  return json_({ ok: true });
}

var __logic__ = { handleGet: handleGet, handlePost: handlePost };
