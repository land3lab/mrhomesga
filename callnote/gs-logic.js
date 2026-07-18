/**
 * 통화노트 — 구글시트 연동 로직 (자동 업데이트되는 본체)
 * ─────────────────────────────────────────────────────
 * 사용자의 Apps Script에는 이 파일을 불러오는 짧은 "연결 코드"만 들어가고,
 * 실제 동작은 이 파일이 담당한다. 이 파일을 수정해서 배포하면
 * 모든 사용자의 스크립트에 자동 반영된다 (재배포 불필요).
 *
 * 권한 체계 (사무실 공용 매물장):
 * - 관리자(사장) 앱이 최초 연결 시 admin_init 으로 관리자 키를 등록한다.
 * - 관리자 키가 등록되면, 이후 모든 기록 읽기/쓰기는 유효한 키(관리자 또는
 *   직원 초대코드)가 있어야 한다. 직원 추가/삭제는 관리자 키로만 가능.
 * - 관리자 키가 없는 상태(개인 사용)에서는 예전처럼 키 없이 동작한다.
 *
 * ⚠️ 호환성 주의: 함수/헤더 이름을 바꾸면 기존 사용자 시트와 어긋난다.
 */

var FILE_NAME = "매통이 매물 접수장"; // 드라이브에 자동 생성될 시트 파일 이름
var SHEET_NAME = "통화노트"; // ⚠️ 기존 사용자 시트의 탭 이름 — 바꾸면 호환이 깨진다
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

/* ── 키/직원 명단 저장 ── */
function adminKey_() {
  return PropertiesService.getScriptProperties().getProperty("adminKey") || "";
}
function staff_() {
  try {
    return JSON.parse(PropertiesService.getScriptProperties().getProperty("staff")) || {};
  } catch (err) { return {}; }
}
function saveStaff_(map) {
  PropertiesService.getScriptProperties().setProperty("staff", JSON.stringify(map));
}
// 접근 등급: "admin" | "staff" | "open"(관리자 미설정) | ""(거부)
function authLevel_(key) {
  var admin = adminKey_();
  if (!admin) return "open"; // 개인 사용 모드 — 키 검사 안 함
  if (key && key === admin) return "admin";
  if (key && staff_()[key]) return "staff";
  return "";
}
function newCode_() {
  var chars = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"; // 헷갈리는 문자(I,L,O,0,1) 제외
  var code = "";
  for (var i = 0; i < 8; i++) code += chars.charAt(Math.floor(Math.random() * chars.length));
  return code;
}

function handleGet(e) {
  var p = (e && e.parameter) || {};
  var key = p.key || "";
  var level = authLevel_(key);
  var props = PropertiesService.getScriptProperties();

  /* ── 관리자 기능 ── */
  if (p.action === "admin_init") {
    // 최초 연결한 관리자 앱의 키를 등록 (이미 있으면 같은 키만 통과)
    if (!key) return json_({ ok: false, error: "no_key" });
    if (!adminKey_()) { props.setProperty("adminKey", key); return json_({ ok: true, admin: true, created: true }); }
    return adminKey_() === key
      ? json_({ ok: true, admin: true })
      : json_({ ok: false, error: "admin_exists" });
  }
  if (p.action === "staff_list") {
    if (level !== "admin") return json_({ ok: false, error: "unauthorized" });
    var map = staff_();
    var list = [];
    for (var code in map) list.push({ code: code, name: map[code] });
    return json_({ ok: true, staff: list });
  }
  if (p.action === "staff_add") {
    if (level !== "admin") return json_({ ok: false, error: "unauthorized" });
    if (!p.name) return json_({ ok: false, error: "no_name" });
    var map2 = staff_();
    var code2 = newCode_();
    map2[code2] = p.name;
    saveStaff_(map2);
    return json_({ ok: true, code: code2, name: p.name });
  }
  if (p.action === "staff_remove") {
    if (level !== "admin") return json_({ ok: false, error: "unauthorized" });
    var map3 = staff_();
    delete map3[p.code];
    saveStaff_(map3);
    return json_({ ok: true });
  }

  /* ── 수신함 읽기 (공용 매물장 동기화) ── */
  if (p.action === "list") {
    if (!level) return json_({ ok: false, error: "unauthorized" });
    var ss = getSpreadsheet_();
    var sh = ss.getSheetByName(SHEET_NAME);
    var rows = [];
    if (sh && sh.getLastRow() > 1) {
      var values = sh.getRange(1, 1, sh.getLastRow(), HEADERS.length).getValues();
      var start = Math.max(1, values.length - 1000); // 최근 1000건까지
      for (var i = start; i < values.length; i++) {
        var o = {};
        for (var j = 0; j < HEADERS.length; j++) o[HEADERS[j]] = values[i][j];
        rows.push(o);
      }
    }
    return json_({ ok: true, rows: rows });
  }

  /* ── 연결 테스트/상태 ── */
  if (!level) return json_({ ok: false, error: "unauthorized" });
  var out = { ok: true, role: level };
  if (level === "admin" || level === "open") out.sheet = getSpreadsheet_().getUrl(); // 시트 파일 위치는 관리자에게만
  if (level === "staff") out.name = staff_()[key] || "";
  return json_(out);
}

// 기록 저장(upsert)/삭제 — 통화노트 앱과 동료의 [매물 공유]가 여기로 보낸다
function handlePost(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var data = JSON.parse(e.postData.contents);
    if (!authLevel_(data.key || "")) return json_({ ok: false, error: "unauthorized" });
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
