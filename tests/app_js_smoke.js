/* Load app.js the way a browser does, and fail if it throws.
 *
 * `node --check` proves the file parses. It does not prove it runs, and the
 * difference is not academic: a call to a helper that does not exist —
 * `on(el, "click", …)` when this codebase has only addEventListener — is
 * perfectly valid syntax, passes every Python test (none of which execute
 * JavaScript), and leaves the entire dashboard stuck on "Loading…" with one
 * ReferenceError in a console nobody is reading.
 *
 * This stubs just enough DOM for the top-level module body to run. It is not a
 * behavioural test; it is a check that the file survives being loaded.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const APP = path.join(__dirname, "..", "src", "magi", "ui", "static", "app.js");

function fakeElement(tag = "div") {
  const el = {
    tagName: tag.toUpperCase(),
    style: { setProperty() {}, removeProperty() {}, getPropertyValue: () => "" },
    dataset: {},
    classList: {
      add() {}, remove() {}, toggle() {}, contains() { return false; },
    },
    children: [],
    value: "",
    textContent: "",
    innerHTML: "",
    checked: false,
    disabled: false,
    addEventListener() {},
    removeEventListener() {},
    appendChild(c) { this.children.push(c); return c; },
    removeChild() {},
    insertBefore(c) { this.children.push(c); return c; },
    setAttribute() {},
    getAttribute() { return null; },
    removeAttribute() {},
    querySelector() { return fakeElement(); },
    querySelectorAll() { return []; },
    closest() { return fakeElement(); },
    getBoundingClientRect() {
      return { top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0 };
    },
    focus() {},
    blur() {},
    click() {},
    scrollTo() {},
    scrollIntoView() {},
    getContext() { return null; },
    remove() {},
  };
  el.parentElement = null;
  el.firstChild = null;
  return el;
}

const storage = {
  getItem() { return null; },
  setItem() {},
  removeItem() {},
  clear() {},
};

const documentStub = {
  body: fakeElement("body"),
  documentElement: fakeElement("html"),
  fonts: { ready: Promise.resolve(), load: () => Promise.resolve() },
  head: fakeElement("head"),
  getElementById() { return fakeElement(); },
  querySelector() { return fakeElement(); },
  querySelectorAll() { return []; },
  createElement(tag) { return fakeElement(tag); },
  createElementNS(_ns, tag) { return fakeElement(tag); },
  createTextNode() { return fakeElement("text"); },
  addEventListener() {},
  removeEventListener() {},
  readyState: "complete",
  visibilityState: "visible",
  cookie: "",
  title: "",
};

const windowStub = {
  location: { href: "http://127.0.0.1:8737/", search: "", hash: "", pathname: "/" },
  localStorage: storage,
  sessionStorage: storage,
  navigator: { language: "en-US", userAgent: "node", clipboard: { writeText() {} } },
  addEventListener() {},
  removeEventListener() {},
  matchMedia() { return { matches: false, addEventListener() {}, addListener() {} }; },
  requestAnimationFrame(cb) { return 0; },
  cancelAnimationFrame() {},
  getComputedStyle() { return { getPropertyValue: () => "" }; },
  setTimeout() { return 0; },
  clearTimeout() {},
  setInterval() { return 0; },
  clearInterval() {},
  fetch() { return Promise.resolve({ ok: true, json: () => Promise.resolve({}) }); },
  devicePixelRatio: 1,
  innerWidth: 1280,
  innerHeight: 900,
  scrollTo() {},
  EventSource: function () { return { addEventListener() {}, close() {} }; },
  alert() {},
  confirm() { return true; },
};
windowStub.window = windowStub;
windowStub.document = documentStub;
windowStub.self = windowStub;
windowStub.globalThis = windowStub;

const sandbox = Object.assign(Object.create(null), windowStub, {
  console: { log() {}, warn() {}, error() {}, info() {}, debug() {} },
  // Vendored libraries the page loads before app.js.
  marked: { parse: (s) => s, setOptions() {} },
  katex: { render() {}, renderToString: () => "" },
  d3: new Proxy({}, { get: () => () => d3Chainable() }),
  mermaid: { initialize() {}, render: () => Promise.resolve({ svg: "" }) },
  Promise, JSON, Math, Date, Object, Array, String, Number, Boolean,
  Set, Map, WeakMap, WeakSet, RegExp, Error, TypeError, Symbol,
  encodeURIComponent, decodeURIComponent, parseInt, parseFloat, isNaN,
  URLSearchParams, AbortController, TextDecoder, TextEncoder, Intl,
});

function d3Chainable() {
  return new Proxy(function () {}, { get: () => () => d3Chainable(), apply: () => d3Chainable() });
}

const source = fs.readFileSync(APP, "utf8");
try {
  vm.runInNewContext(source, sandbox, { filename: "app.js", timeout: 15000 });
  console.log("app.js loaded without throwing");
  process.exit(0);
} catch (err) {
  console.error("app.js threw while loading:");
  console.error(`  ${err.name}: ${err.message}`);
  if (err.stack) {
    const line = err.stack.split("\n").find((l) => l.includes("app.js"));
    if (line) console.error(`  at ${line.trim()}`);
  }
  process.exit(1);
}
