const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = readFileSync(path.join(__dirname, '../styles/theme.js'), 'utf8');

// Browser facilities are the boundary; execute the production script unchanged.
function browserHost({ stored = null, dark = false, storage = 'working', ready = true,
  metadata = true, media = 'modern', storageGetterBlocked = false,
  readyState = 'complete' } = {}) {
  function element() {
    const attributes = new Map();
    const listeners = new Map();
    const classes = new Set();
    return {
      style: {},
      classList: { add: name => classes.add(name), contains: name => classes.has(name) },
      setAttribute: (name, value) => attributes.set(name, String(value)),
      getAttribute: name => attributes.get(name) ?? null,
      removeAttribute: name => attributes.delete(name),
      addEventListener: (name, fn) => listeners.set(name, fn),
      click() { listeners.get('click')?.(); },
    };
  }

  const root = element();
  const buttons = [];
  const frames = [];
  const documentEvents = new Map();
  const windowEvents = new Map();
  const mediaListeners = [];
  const values = new Map(stored === null ? [] : [['theme', stored]]);
  const writes = [];
  let meta = ready && metadata ? element() : null;
  const body = { appendChild: button => buttons.push(button) };
  const query = {
    matches: dark,
    ...(media === 'legacy'
      ? { addListener: fn => mediaListeners.push(fn) }
      : { addEventListener: (name, fn) => { if (name === 'change') mediaListeners.push(fn); } }),
  };
  const document = {
    documentElement: root,
    body: ready ? body : null,
    readyState: ready ? readyState : 'loading',
    createElement(name) { assert.equal(name, 'button'); return element(); },
    querySelector(selector) {
      if (selector === 'meta[name="theme-color"]') return meta;
      if (selector === '.theme-toggle') return buttons[0] ?? null;
      throw new Error('Unexpected selector: ' + selector);
    },
    querySelectorAll(selector) { assert.equal(selector, '.theme-toggle'); return buttons; },
    addEventListener: (name, fn) => documentEvents.set(name, fn),
  };
  const localStorage = {
    getItem(key) {
      if (storage === 'blocked' || storage === 'read-blocked') throw new Error('Storage read blocked');
      return values.get(key) ?? null;
    },
    setItem(key, value) {
      writes.push([key, value]);
      if (storage === 'blocked' || storage === 'write-blocked') throw new Error('Storage write blocked');
      if (storage !== 'discarded') values.set(key, value);
    },
  };
  const window = { addEventListener: (name, fn) => windowEvents.set(name, fn) };
  if (media !== 'unavailable') window.matchMedia = () => query;
  const context = { window, document, requestAnimationFrame: fn => frames.push(fn) };
  Object.defineProperty(context, 'localStorage', {
    get() {
      if (storageGetterBlocked) throw new Error('Storage access blocked');
      return localStorage;
    },
  });
  vm.runInNewContext(script, context, { filename: 'styles/theme.js' });

  return {
    root, buttons, writes, values,
    get meta() { return meta; },
    ready() {
      document.body = body;
      document.readyState = 'interactive';
      meta = metadata ? element() : null;
      documentEvents.get('DOMContentLoaded')?.();
    },
    paint() { frames.splice(0).forEach(fn => fn()); },
    system(dark) {
      query.matches = dark;
      mediaListeners.forEach(fn => fn({ matches: dark }));
    },
    storage(key, newValue) { windowEvents.get('storage')?.({ key, newValue }); },
  };
}

function assertPresentation(host, { pin, color, label, meta }) {
  assert.equal(host.root.getAttribute('data-theme'), pin);
  assert.equal(host.root.style.colorScheme, color);
  assert.equal(host.meta?.getAttribute('content'), meta);
  assert.equal(host.buttons.length, 1);
  assert.equal(host.buttons[0].type, 'button');
  assert.equal(host.buttons[0].className, 'theme-toggle theme-toggle--fixed');
  assert.equal(host.buttons[0].getAttribute('aria-label'), label);
  assert.equal(host.buttons[0].getAttribute('title'), label);
}

const light = { pin: 'light', color: 'light', meta: '#fef9ee', label: 'Switch to dark mode' };
const dark = { pin: 'dark', color: 'dark', meta: '#0f1a1c', label: 'Switch to light mode' };

test('blocked storage keeps two consecutive clicks consistent', () => {
  const host = browserHost({ storage: 'blocked' });
  host.buttons[0].click();
  assertPresentation(host, dark);
  host.buttons[0].click();
  assertPresentation(host, light);
});

test('early head execution sets the root before readiness and refreshes late metadata', () => {
  const host = browserHost({ stored: 'dark', ready: false });
  assert.equal(host.root.getAttribute('data-theme'), 'dark');
  assert.equal(host.root.style.colorScheme, 'dark');
  assert.equal(host.meta, null);
  assert.equal(host.buttons.length, 0);
  assert.equal(host.root.classList.contains('theme-ready'), false);
  host.ready();
  assertPresentation(host, dark);
  assert.equal(host.root.classList.contains('theme-ready'), false);
  host.paint();
  assert.equal(host.root.classList.contains('theme-ready'), true);
});

test('storage event values own cross-tab preference even when storage cannot be read', () => {
  const host = browserHost({ storage: 'blocked' });
  host.storage('theme', 'dark');
  assertPresentation(host, dark);
  host.system(true);
  host.storage('theme', 'light');
  assertPresentation(host, light);
  host.storage('unrelated', 'dark');
  assertPresentation(host, light);
  host.storage('theme', null);
  assertPresentation(host, { ...dark, pin: null, color: '' });
  host.system(false);
  assertPresentation(host, { ...light, pin: null, color: '' });
  host.storage('theme', 'dark');
  host.storage('theme', 'invalid');
  assertPresentation(host, { ...light, pin: null, color: '' });
  assert.deepEqual(host.writes, []);
});

for (const [stored, systemDark, expected] of [
  ['light', true, light],
  ['light', false, light],
  ['dark', false, dark],
  ['dark', true, dark],
  [null, false, { ...light, pin: null, color: '' }],
  [null, true, { ...dark, pin: null, color: '' }],
  ['invalid', true, { ...dark, pin: null, color: '' }],
  ['', false, { ...light, pin: null, color: '' }],
  ['DARK', false, { ...light, pin: null, color: '' }],
]) {
  test(`initial stored ${JSON.stringify(stored)}, system ${systemDark ? 'dark' : 'light'}`, () => {
    const host = browserHost({ stored, dark: systemDark });
    assertPresentation(host, expected);
    assert.deepEqual(host.writes, []);
    assert.equal(host.root.classList.contains('theme-ready'), false);
    host.paint();
    assert.equal(host.root.classList.contains('theme-ready'), true);
  });
}

for (const storage of ['working', 'blocked', 'read-blocked', 'write-blocked', 'discarded']) {
  for (const systemDark of [false, true]) {
    test(`${storage} persistence alternates both directions from a ${systemDark ? 'dark' : 'light'} system`, () => {
      const host = browserHost({ storage, dark: systemDark });
      assertPresentation(host, { ...(systemDark ? dark : light), pin: null, color: '' });
      host.buttons[0].click();
      assertPresentation(host, systemDark ? light : dark);
      host.system(!systemDark);
      assertPresentation(host, systemDark ? light : dark);
      host.buttons[0].click();
      assertPresentation(host, systemDark ? dark : light);
      assert.deepEqual(host.writes, systemDark
        ? [['theme', 'light'], ['theme', 'dark']]
        : [['theme', 'dark'], ['theme', 'light']]);
      if (storage === 'working' || storage === 'read-blocked') {
        assert.equal(host.values.get('theme'), systemDark ? 'dark' : 'light');
      } else {
        assert.equal(host.values.has('theme'), false);
      }
    });
  }
}

for (const storage of ['working', 'write-blocked', 'discarded']) {
  for (const [stored, expected, next] of [['light', light, dark], ['dark', dark, light]]) {
    test(`${storage} persistence cannot restore a stale ${stored} pin after a click`, () => {
      const host = browserHost({ storage, stored, dark: stored === 'light' });
      assertPresentation(host, expected);
      host.buttons[0].click();
      assertPresentation(host, next);
      host.system(stored === 'dark');
      assertPresentation(host, next);
      host.buttons[0].click();
      assertPresentation(host, expected);
    });
  }
}

test('blocked storage property starts in system mode and still allows clicks', () => {
  const host = browserHost({ storageGetterBlocked: true, stored: 'light', dark: true });
  assertPresentation(host, { ...dark, pin: null, color: '' });
  host.buttons[0].click();
  assertPresentation(host, light);
  host.buttons[0].click();
  assertPresentation(host, dark);
});

for (const media of ['modern', 'legacy']) {
  test(`${media} media-query events follow system mode and respect stored and clicked pins`, () => {
    const host = browserHost({ media, stored: 'invalid' });
    assertPresentation(host, { ...light, pin: null, color: '' });
    host.system(true);
    assertPresentation(host, { ...dark, pin: null, color: '' });
    host.system(false);
    assertPresentation(host, { ...light, pin: null, color: '' });
    host.storage('theme', 'dark');
    host.system(true);
    host.system(false);
    assertPresentation(host, dark);
    host.buttons[0].click();
    host.system(true);
    assertPresentation(host, light);
    host.storage('theme', null);
    assertPresentation(host, { ...dark, pin: null, color: '' });
  });
}

test('missing media queries fall back to light and retain explicit choices', () => {
  const host = browserHost({ media: 'unavailable' });
  assertPresentation(host, { ...light, pin: null, color: '' });
  host.buttons[0].click();
  assertPresentation(host, dark);
  host.buttons[0].click();
  assertPresentation(host, light);
});

test('an interactive document mounts immediately without waiting for readiness again', () => {
  assertPresentation(browserHost({ stored: 'dark', readyState: 'interactive' }), dark);
});

test('early system and storage events are reflected when the body and metadata arrive', () => {
  const host = browserHost({ ready: false });
  host.system(true);
  host.storage('theme', 'light');
  assert.equal(host.root.getAttribute('data-theme'), 'light');
  assert.equal(host.root.style.colorScheme, 'light');
  assert.equal(host.buttons.length, 0);
  host.storage('theme', 'invalid');
  assert.equal(host.root.getAttribute('data-theme'), null);
  assert.equal(host.root.style.colorScheme, '');
  host.ready();
  assertPresentation(host, { ...dark, pin: null, color: '' });
});

for (const ready of [false, true]) {
  test(`optional metadata can stay absent with an ${ready ? 'already-ready' : 'early'} load`, () => {
    const host = browserHost({ metadata: false, ready });
    if (!ready) host.ready();
    assertPresentation(host, { ...light, pin: null, color: '', meta: undefined });
    host.buttons[0].click();
    assertPresentation(host, { ...dark, meta: undefined });
    host.buttons[0].click();
    assertPresentation(host, { ...light, meta: undefined });
  });
}
