const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } = require('node:fs');
const { tmpdir } = require('node:os');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const inlineScript = /<script>([\s\S]*?)<\/script>/;
const archiveScript = readFileSync(path.join(root, 'posts/index.html'), 'utf8').match(inlineScript)[0];

// Author the fixture from the same element tree the script sees in the stand-in.
// The publisher changes list contents, which do not affect these elements' positions.
function element(tag, attributes, ...children) {
  const node = {
    parentElement: null,
    getAttribute(name) { return attributes[name] ?? null; },
    setAttribute(name, value) { attributes[name] = String(value); },
    get nextElementSibling() {
      const siblings = this.parentElement?.children ?? [];
      return siblings[siblings.indexOf(this) + 1] ?? null;
    },
    matches(selector) {
      const [selectorTag, className] = selector.split('.');
      return (!selectorTag || selectorTag === tag) && classes().includes(className);
    },
    classList: {
      toggle(name, active) {
        const updated = new Set(classes());
        if (active) updated.add(name);
        else updated.delete(name);
        attributes.class = [...updated].join(' ');
      },
    },
    children: children.filter(child => typeof child !== 'string'),
    html() {
      const attrs = Object.entries(attributes).map(([name, value]) => ` ${name}="${value}"`).join('');
      const content = children.map(child => typeof child === 'string' ? child : child.html()).join('\n');
      return `<${tag}${attrs}>${content}</${tag}>`;
    },
  };
  function classes() {
    return (attributes.class ?? '').split(/\s+/);
  }
  for (const child of node.children) child.parentElement = node;
  return node;
}

function archiveFixture() {
  const chronologicalSort = element('a', {
    href: '#chronological', class: 'archive-sort-link is-active',
    'data-sort': 'chronological', 'aria-current': 'page',
  }, 'Chronological');
  const categorySort = element('a', {
    href: '#by-category', class: 'archive-sort-link',
    'data-sort': 'category', 'aria-current': 'false',
  }, 'By category');
  const chronological = element('section', { id: 'chronological', class: 'archive-view-chrono' },
    element('ul', { class: 'archive-list' }));
  const category = element('section', { id: 'by-category', class: 'archive-view-category' },
    element('p', { class: 'category-links' },
      element('a', { href: '#field-notes' }, 'Field Notes'),
      element('a', { href: '#empty-notes' }, 'Empty Notes')),
    element('h3', { id: 'field-notes', class: 'archive-category-heading' }, 'Field Notes'),
    element('ul', { class: 'archive-list' }),
    element('h3', { id: 'empty-notes', class: 'archive-category-heading' }, 'Empty Notes'),
    element('ul', { class: 'archive-list' }),
    element('h3', { id: 'essay', class: 'archive-category-heading' }, 'Unpaired Heading'),
    element('ul', {}, element('li', {}, 'Unrelated list item')),
    element('div', {},
      element('h3', { id: 'nested-heading', class: 'archive-category-heading' }, 'Nested Heading'),
      element('ul', { class: 'archive-list' })));
  const layout = element('div', { id: 'archive-layout', 'data-view': 'chronological' }, chronological, category);
  const outside = element('aside', {},
    element('h3', { id: 'general', class: 'archive-category-heading' }, 'Outside Heading'),
    element('ul', { class: 'archive-list' }));
  const body = element('body', {}, chronologicalSort, categorySort, layout, outside, archiveScript);
  return { chronologicalSort, categorySort, layout, body };
}

function buildArchive(t, body) {
  const site = mkdtempSync(path.join(tmpdir(), 'posts-archive-test-'));
  t.after(() => rmSync(site, { recursive: true, force: true }));
  const publisher = path.join(site, 'tools/publish.py');
  const archive = path.join(site, 'posts/index.html');
  mkdirSync(path.dirname(publisher));
  mkdirSync(path.join(site, 'posts/observation-log'), { recursive: true });
  copyFileSync(path.join(root, 'tools/publish.py'), publisher);
  const authored = '<!doctype html><html><head><title>Posts</title></head>' + body.html() + '</html>';
  writeFileSync(archive, authored);
  writeFileSync(path.join(site, 'posts/observation-log/index.html'),
    '<!doctype html><html><head><title>Observation Log</title></head><body></body></html>');
  writeFileSync(path.join(site, 'posts.json'), JSON.stringify({
    categories: { 'field-notes': 'Field Notes', 'empty-notes': 'Empty Notes' },
    posts: [{
      slug: 'observation-log', title: 'Observation Log', date: 'May 1, 2026',
      categories: ['field-notes'], status: 'draft',
    }],
  }));
  for (const args of [['build'], ['publish', 'observation-log'], ['check']]) {
    execFileSync('python3', [publisher, ...args]);
  }
  const published = readFileSync(archive, 'utf8');
  const archiveLists = /(<ul class="archive-list">)[\s\S]*?(<\/ul>)/g;
  assert.equal(published.replace(archiveLists, '$1$2'), authored.replace(archiveLists, '$1$2'),
    'publishing preserves the authored markup used by the DOM stand-in');
  return published;
}

function browserHost(body, script, hash) {
  function descendants(node) {
    return [node, ...node.children.flatMap(descendants)];
  }
  const nodes = descendants(body);
  const frames = [];
  const scrolls = [];
  for (const node of nodes) {
    node.scrollIntoView = () => scrolls.push(node.getAttribute('id'));
  }
  const document = {
    getElementById: id => nodes.find(node => node.getAttribute('id') === id) ?? null,
    querySelectorAll: selector => nodes.filter(node => node.matches(selector)),
  };
  const listeners = new Map();
  const location = { hash };
  const window = { addEventListener: (event, callback) => listeners.set(event, callback) };
  vm.runInNewContext(script, { document, location, window, requestAnimationFrame: callback => frames.push(callback) });
  return {
    frames,
    scrolls,
    changeHash(hash) {
      location.hash = hash;
      listeners.get('hashchange')();
    },
    runFrames() {
      for (const callback of frames.splice(0)) callback();
    },
  };
}

function assertView(fixture, expected) {
  assert.equal(fixture.layout.getAttribute('data-view'), expected);
  for (const link of [fixture.chronologicalSort, fixture.categorySort]) {
    const active = link.getAttribute('data-sort') === expected;
    assert.equal(link.matches('.is-active'), active);
    assert.equal(link.getAttribute('aria-current'), active ? 'page' : 'false');
  }
}

test('a newly published category fragment selects the category view and scrolls to its heading', t => {
  const fixture = archiveFixture();
  const archive = buildArchive(t, fixture.body);
  assert.match(archive, /<h3 id="field-notes"[^>]*>Field Notes<\/h3>\s*<ul class="archive-list">\s*<li>\s*<a href="\/posts\/observation-log\/"/);
  assert.match(archive, /<h3 id="empty-notes"[^>]*>Empty Notes<\/h3>\s*<ul class="archive-list">\s*<\/ul>/);
  const browser = browserHost(fixture.body, archive.match(inlineScript)[1], '#field-notes');
  assertView(fixture, 'category');
  assert.equal(browser.frames.length, 1);
  assert.deepEqual(browser.scrolls, []);
  browser.runFrames();
  assert.deepEqual(browser.scrolls, ['field-notes']);

  browser.changeHash('#empty-notes');
  assertView(fixture, 'category');
  assert.equal(browser.frames.length, 1);
  browser.runFrames();
  assert.deepEqual(browser.scrolls, ['field-notes', 'empty-notes']);
});

for (const [fragment, view] of [
  ['', 'chronological'],
  ['#chronological', 'chronological'],
  ['#by-category', 'category'],
  ['#general', 'chronological'],
  ['#essay', 'chronological'],
  ['#nested-heading', 'chronological'],
  ['#constructor', 'chronological'],
]) {
  test(`${fragment || 'an empty fragment'} selects ${view} without scheduling a scroll`, () => {
    const fixture = archiveFixture();
    const browser = browserHost(fixture.body, archiveScript.match(inlineScript)[1], fragment);
    assertView(fixture, view);
    assert.equal(browser.frames.length, 0);
  });
}

test('hash changes switch the active sort link and scroll to the current category only', () => {
  const fixture = archiveFixture();
  const browser = browserHost(fixture.body, archiveScript.match(inlineScript)[1], '');

  browser.changeHash('#field-notes');
  assertView(fixture, 'category');
  browser.changeHash('#chronological');
  assertView(fixture, 'chronological');
  browser.runFrames();
  assert.deepEqual(browser.scrolls, []);

  browser.changeHash('#field-notes');
  assertView(fixture, 'category');
  browser.runFrames();
  assert.deepEqual(browser.scrolls, ['field-notes']);

  browser.changeHash('#by-category');
  assertView(fixture, 'category');
  assert.equal(browser.frames.length, 0);
  browser.changeHash('#unrelated');
  assertView(fixture, 'chronological');
  assert.equal(browser.frames.length, 0);
});
