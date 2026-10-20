const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const html = fs.readFileSync(__dirname + '/index.html', 'utf8');
const upload = html.slice(html.indexOf('async function uploadAudioToGemini('), html.indexOf('/* ══════════════ Gemini AI 정리'));
const flow = html.slice(html.indexOf('    let result;\n    if (pendingAudio)'), html.indexOf('    renderAiSteps(steps, steps.length - 1);'));
const response = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });
function setup({ state = 'ACTIVE', check = 'ACTIVE', deletion = 200, aiError, size = 15 * 1048576 } = {}) {
  const events = [], warnings = [], nodes = {};
  const ctx = vm.createContext({
    console: { warn: (...args) => warnings.push(args) },
    setTimeout: fn => fn(), encodeURIComponent, Blob,
    fetch: async (url, options = {}) => {
      if (options.method === 'DELETE') {
        events.push('delete');
        if (deletion === 'network') throw new Error('secret URL');
        return response({}, deletion);
      }
      if (url.includes('/upload/')) { events.push('upload'); return response({ file: { name: 'files/test', state, uri: 'test-uri', mimeType: 'audio/mp4' } }); }
      events.push('check');
      if (check === 'network') throw new Error('network');
      if (check === 'http') return response({}, 500);
      return response({ state: check, uri: 'test-uri' });
    },
    pendingAudio: size === null ? null : { size, name: 'test.m4a' },
    settings: { apiKey: 'fake-test-key' }, INLINE_MAX_BYTES: 12 * 1048576,
    guessMime: () => 'audio/mp4', PROMPT: '', PROMPT_AUDIO_EXTRA: '', callerContext: () => '',
    text: 'memo', steps: [], renderAiSteps: () => {},
    el: id => nodes[id] ||= {},
    fileToBase64: async () => { events.push('base64'); return 'fake'; },
    callGemini: async parts => {
      events.push(parts.some(p => p.fileData) ? 'ai-file' : parts.some(p => p.inlineData) ? 'ai-inline' : 'ai-text');
      if (aiError) throw aiError;
      return { summary: 'ok', transcript: 'test transcript' };
    },
  });
  vm.runInContext(upload, ctx);
  return { events, warnings, ctx, run: () => vm.runInContext('(async () => {\n' + flow + '\nreturn result; })()', ctx) };
}
test('all inline scripts parse', () => {
  for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
    if (!/src=|application\/ld\+json/.test(match[1])) new vm.Script(match[2]);
  }
});
test('AI success awaits one DELETE after generation', async () => {
  const s = setup(); assert.equal((await s.run()).summary, 'ok');
  assert.deepEqual(s.events, ['upload', 'ai-file', 'delete']);
});
for (const message of ['HTTP 429', 'HTTP 500', 'network error', 'invalid JSON', 'empty response']) {
  test('AI failure cleans up and preserves original error: ' + message, async () => {
    const error = new Error(message), s = setup({ aiError: error });
    await assert.rejects(s.run(), e => e === error);
    assert.equal(s.events.at(-1), 'delete'); assert.equal(s.events.filter(e => e === 'delete').length, 1);
  });
}
for (const deletion of [403, 500, 'network', 404]) {
  for (const fails of [false, true]) test(`DELETE ${deletion}, AI fails=${fails}`, async () => {
    const error = fails ? new Error('original AI error') : undefined;
    const s = setup({ deletion, aiError: error });
    if (fails) await assert.rejects(s.run(), e => e === error);
    else assert.equal((await s.run()).summary, 'ok');
    assert.equal(s.warnings.length, deletion === 404 ? 0 : 1);
    assert.ok(!JSON.stringify(s.warnings).includes('fake-test-key'));
    assert.ok(!JSON.stringify(s.warnings).includes('secret URL'));
  });
}
for (const check of ['FAILED', 'PROCESSING', 'network', 'http']) {
  test('processing failure cleans up: ' + check, async () => {
    const s = setup({ state: 'PROCESSING', check });
    await assert.rejects(s.run(), /녹음 파일 처리/);
    assert.equal(s.events.at(-1), 'delete'); assert.ok(!s.events.includes('ai-file'));
    assert.equal(s.events.filter(e => e === 'delete').length, 1);
  });
}
test('processing becomes ACTIVE before AI and DELETE', async () => {
  const s = setup({ state: 'PROCESSING' }); await s.run();
  assert.deepEqual(s.events, ['upload', 'check', 'ai-file', 'delete']);
});
for (const size of [1048576, 12 * 1048576, 12 * 1048576 + 1, null]) {
  test('routing boundary: ' + size, async () => {
    const s = setup({ size }); await s.run();
    assert.deepEqual(s.events, size === null ? ['ai-text'] : size <= 12 * 1048576 ? ['base64', 'ai-inline'] : ['upload', 'ai-file', 'delete']);
  });
}

test('only one upload implementation and no conflict markers', () => {
  assert.equal((html.match(/async function uploadAudioToGemini\(/g) || []).length, 1);
  assert.ok(!/^(<<<<<<<|=======|>>>>>>>)/m.test(html));
});

const diagnostic = html.slice(html.indexOf('// 개인정보가 없는 무음 WAV'), html.indexOf('/* ══════════════ 설정'));
for (const failure of [false, true]) {
  for (const status of [404, 200, 403]) test(`diagnostic AI failure=${failure}, verification=${status}`, async () => {
    const events = [], reports = [];
    const ctx = vm.createContext({ settings: { apiKey: 'fake-key' }, File, ArrayBuffer, DataView, URL,
      el: () => ({}),
      uploadAudioToGemini: async file => {
        assert.ok(file.size > 12 * 1048576);
        assert.equal(file.type, 'audio/wav');
        const view = new DataView(await file.arrayBuffer());
        assert.equal(view.getUint32(40, true), file.size - 44);
        events.push('upload');
        return { fileUri: 'https://generativelanguage.googleapis.com/v1beta/files/test', mimeType: 'audio/wav', cleanup: async () => events.push('delete') };
      },
      callGemini: async () => { events.push('ai'); if (failure) throw new Error('secret'); },
      fetch: async () => { events.push('verify'); return { status }; },
    });
    vm.runInContext(diagnostic, ctx);
    ctx.report = text => reports.push(text);
    await vm.runInContext('runGeminiDiagnostic(report)', ctx);
    assert.deepEqual(events, ['upload', 'ai', 'delete', 'verify']);
    assert.equal(reports.at(-1).includes('진단 통과'), !failure && status === 404);
    assert.ok(!reports.join('').includes('fake-key'));
    assert.ok(!reports.join('').includes('secret'));
  });
}
test('diagnostic without key never uploads', async () => {
  const ctx = vm.createContext({ settings: {}, el: () => ({}), report: () => {}, uploadAudioToGemini: () => { throw new Error('must not upload'); } });
  vm.runInContext(diagnostic, ctx);
  await vm.runInContext('runGeminiDiagnostic(report)', ctx);
});
