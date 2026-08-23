/* MAGI browser button.
 *
 * Deliberately tiny. It sends the current tab's URL and a chosen library name
 * to a local MAGI, and does nothing else — no scraping, no downloading, no
 * parsing, no deciding what a page is. All of that is the server's job, where
 * it is deterministic and testable; here it would be a second implementation
 * that drifts from the first. The tab's title goes over untouched for the same
 * reason: stripping arXiv's "[2410.11942] " prefix is a rule about titles, and
 * rules about titles live in `magi.ingest.enqueue.clean_title`.
 *
 * The server endpoint it calls can only append one line to a queue. That is
 * what makes it safe to talk to an unauthenticated loopback server: the worst
 * this button can do is put something in a list a human still has to approve.
 *
 * Requests go from the popup with host_permissions for 127.0.0.1, not from a
 * content script. MAGI deliberately ships no CORS middleware — the absence of
 * it is one of the three things stopping a hostile web page from driving the
 * local API — and this must not be the reason that gets weakened.
 */

const PORTS = [8737, 8738, 8739, 8740, 8741];
const STORE = { port: "magi-port", library: "magi-library", lang: "magi-lang" };

/* Same shape as the WebUI's I18N table and the same storage key, so the two
 * surfaces agree about which language you read in. `chrome.i18n` handles the
 * manifest strings instead — the extension's name and tooltip can only be
 * localised that way — but it follows Chrome's UI language and cannot be
 * toggled, which is why the popup does not use it. */
const I18N = {
  en: {
    addTo: "Add to",
    port: "MAGI port",
    send: "Queue it",
    loading: "…",
    noPage: "This only works on a web page.",
    noPageTarget: "no page",
    noMagi: "Could not reach MAGI. Is it running? Start it with: magi ui",
    noLibs: "MAGI is running but has no libraries registered yet.",
    noLibChosen: "No library to queue into — check the port above, or register one with 'magi kb register'.",
    queueing: "queueing…",
    queued: (kind, value) => `Queued as ${kind}: ${value}`,
    already: (kind, value) => `Already waiting as ${kind}: ${value}`,
    waiting: (n, lib) => `${n} waiting in ${lib}.`,
    hint: "Queuing only adds it to a list. Run <code>magi ingest batch-run</code>, then approve what came out — nothing enters your library until you do.",
    kind: { arxiv: "arXiv paper", doi: "DOI", url: "page", file: "file" },
  },
  zh: {
    addTo: "收进哪个库",
    port: "MAGI 端口",
    send: "加入队列",
    loading: "…",
    noPage: "这个只对网页有效。",
    noPageTarget: "没有页面",
    noMagi: "连不上 MAGI。它在跑吗？用 magi ui 启动。",
    noLibs: "MAGI 在跑，但还没有注册任何知识库。",
    noLibChosen: "没有可入队的知识库——检查上面的端口，或者用 'magi kb register' 注册一个。",
    queueing: "正在入队…",
    queued: (kind, value) => `已入队，识别为${kind}：${value}`,
    already: (kind, value) => `已经在队列里了，识别为${kind}：${value}`,
    waiting: (n, lib) => `${lib} 里现在有 ${n} 项待处理。`,
    hint: "入队只是加进一个清单。跑 <code>magi ingest batch-run</code>，然后审批转换结果——在你批准之前，什么都不会进库。",
    kind: { arxiv: "arXiv 论文", doi: "DOI", url: "网页", file: "文件" },
  },
};

let lang = "en";
const t = () => I18N[lang];

const $ = (id) => document.getElementById(id);
const status = (text, kind = "") => {
  const el = $("status");
  el.textContent = text;
  el.className = kind;
};

const base = () => `http://127.0.0.1:${$("port").value}`;

async function currentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

/** Saved choice first, then what the browser is set to, then English. Same
 *  order the WebUI uses, so opening both does not give two answers. */
async function resolveLang() {
  const saved = (await chrome.storage.local.get(STORE.lang))[STORE.lang];
  if (saved && I18N[saved]) return saved;
  const nav = String(navigator.language || "").toLowerCase();
  return nav.startsWith("zh") ? "zh" : "en";
}

function paint() {
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  $("lbl-library").textContent = t().addTo;
  $("lbl-port").textContent = t().port;
  $("send").textContent = t().send;
  $("hint").innerHTML = t().hint;
}

async function loadLibraries() {
  const res = await fetch(`${base()}/api/kb`, { method: "GET" });
  if (!res.ok) throw new Error(`MAGI answered ${res.status}`);
  const data = await res.json();
  return (data.kbs || []).filter((kb) => kb.exists);
}

/** Try each candidate port until one answers, so a second dashboard on 8738
 *  is found without the user being asked to know that. */
async function findMagi() {
  const saved = (await chrome.storage.local.get(STORE.port))[STORE.port];
  const order = saved ? [saved, ...PORTS.filter((p) => p !== saved)] : PORTS;

  for (const port of order) {
    $("port").value = String(port);
    try {
      const kbs = await loadLibraries();
      await chrome.storage.local.set({ [STORE.port]: port });
      return kbs;
    } catch {
      /* try the next one */
    }
  }
  throw new Error("no MAGI found on 127.0.0.1");
}

async function init() {
  $("port").innerHTML = PORTS.map((p) => `<option value="${p}">${p}</option>`).join("");
  paint();

  const tab = await currentTab();
  const url = tab?.url || "";
  $("target").textContent = url || t().noPageTarget;

  if (!/^https?:/i.test(url)) {
    status(t().noPage, "err");
    return;
  }

  let kbs;
  try {
    kbs = await findMagi();
  } catch (err) {
    status(t().noMagi, "err");
    return;
  }

  if (!kbs.length) {
    status(t().noLibs, "err");
    return;
  }

  const savedLib = (await chrome.storage.local.get(STORE.library))[STORE.library];
  $("library").innerHTML = kbs
    .map((kb) => {
      const selected = kb.name === savedLib || (!savedLib && kb.current) ? " selected" : "";
      return `<option value="${kb.name}"${selected}>${kb.name}</option>`;
    })
    .join("");

  $("send").disabled = false;
  status("");
}

$("send").addEventListener("click", async () => {
  const tab = await currentTab();
  const library = $("library").value;
  // An empty picker means the library list never loaded — wrong port, server
  // down, nothing registered. Sending anyway used to queue into whichever
  // directory `magi ui` was started in; the server refuses that now, and
  // saying so here saves a round trip and names the real problem.
  if (!library) {
    status(t().noLibChosen, "err");
    return;
  }
  $("send").disabled = true;
  status(t().queueing);

  try {
    const res = await fetch(`${base()}/api/ingest/enqueue`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value: tab.url, library, title: tab.title || null }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `MAGI answered ${res.status}`);
    }
    const body = await res.json();
    await chrome.storage.local.set({ [STORE.library]: library });

    // Say what MAGI understood the page to be. A journal URL queued as a DOI
    // and one queued as a bare URL take different routes, and knowing which
    // happened is the difference between "it worked" and "it looked like it
    // worked". The newline is load-bearing: #status sets white-space:pre-line
    // so these stay two sentences.
    const kind = t().kind[body.source_type] || body.source_type;
    // Say which of the two happened. Clicking the same paper twice used to
    // queue it twice; it now collapses into the request already waiting, and
    // reporting that as a fresh queueing would be a comfortable lie — the
    // duplicate it replaced was at least visible.
    const line = body.status === "already-queued"
      ? t().already(kind, body.value)
      : t().queued(kind, body.value);
    status(`${line}\n${t().waiting(body.pending, library)}`, "ok");
  } catch (err) {
    status(String(err.message || err), "err");
    $("send").disabled = false;
  }
});

$("port").addEventListener("change", () => {
  $("send").disabled = true;
  init();
});

$("lang").addEventListener("click", async () => {
  lang = lang === "zh" ? "en" : "zh";
  await chrome.storage.local.set({ [STORE.lang]: lang });
  $("send").disabled = true;
  init();
});

(async () => {
  lang = await resolveLang();
  init();
})();
