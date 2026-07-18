/**
 * 통화노트 — 구글시트 연동 로직 (자동 업데이트되는 본체)
 * ─────────────────────────────────────────────────────
 * 사용자의 Apps Script에는 이 파일을 불러오는 짧은 "연결 코드"만 들어가고,
 * 실제 동작은 이 파일이 담당한다. 이 파일을 수정해서 배포하면
 * 모든 사용자의 스크립트에 자동 반영된다 (재배포 불필요).
 *
 * ⚠️ 호환성 주의: 함수/헤더 이름을 바꾸면 기존 사용자 시트와 어긋난다.
 */

var FILE_NAME = "통화노트 매물 접수장"; // 드라이브에 자동 생성될 시트 파일 이름
var SHEET_NAME = "통화노트";
var HEADERS = ["id", "통화일시", "구분", "이름", "연락처", "고객유형", "물건종류", "거래유형",
  "주소/단지", "매매가", "보증금", "월세", "면적", "층", "방/욕실", "입주일", "희망조건",
  "특이사항", "할일", "요약", "통화내용", "수정일시"];

// 시트에서 만든 스크립트면 그 시트를, 독립 스크립트면 자동 생성한 시트를 사용
function getSpreadsheet_() {
  var props = PropertiesService.getScriptProperties();
  var savedId = props.getProperty("ssid");
  if (savedId) {
    try { return SpreadsheetApp.openById(savedId); } catch (err) {}
  }
  var active = SpreadsheetApp.getActiveSpreadsheet();
  if (active) { props.setProperty("ssid", active.getId()); return active; }
  var created = SpreadsheetApp.create(FILE_NAME);
  props.setProperty("ssid", created.getId());
  return created;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// 연결 테스트 + 수신함 읽기 — ?action=list 로 호출하면 최근 기록을 돌려준다
function handleGet(e) {
  var ss = getSpreadsheet_();
  if (e && e.parameter && e.parameter.action === "list") {
    var sh = ss.getSheetByName(SHEET_NAME);
    var rows = [];
    if (sh && sh.getLastRow() > 1) {
      var values = sh.getRange(1, 1, sh.getLastRow(), HEADERS.length).getValues();
      var start = Math.max(1, values.length - 500); // 최근 500건까지
      for (var i = start; i < values.length; i++) {
        var o = {};
        for (var j = 0; j < HEADERS.length; j++) o[HEADERS[j]] = values[i][j];
        rows.push(o);
      }
    }
    return json_({ ok: true, rows: rows });
  }
  return json_({ ok: true, sheet: ss.getUrl() });
}

// 기록 저장(upsert)/삭제 — 통화노트 앱과 동료의 [매물 공유]가 여기로 보낸다
function handlePost(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var data = JSON.parse(e.postData.contents);
    var ss = getSpreadsheet_();
    var sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
    if (sh.getLastRow() === 0) sh.appendRow(HEADERS);
    var ids = sh.getRange(1, 1, sh.getLastRow(), 1).getValues();
    var rowIdx = 0;
    for (var i = 0; i < ids.length; i++) {
      if (String(ids[i][0]) === String(data.record.id)) { rowIdx = i + 1; break; }
    }
    if (data.action === "delete") {
      if (rowIdx > 1) sh.deleteRow(rowIdx);
    } else {
      var row = [];
      for (var j = 0; j < HEADERS.length; j++) row.push(data.record[HEADERS[j]] || "");
      if (rowIdx > 1) sh.getRange(rowIdx, 1, 1, HEADERS.length).setValues([row]);
      else sh.appendRow(row);
    }
    return json_({ ok: true });
  } finally {
    lock.releaseLock();
  }
}

var __logic__ = { handleGet: handleGet, handlePost: handlePost };
