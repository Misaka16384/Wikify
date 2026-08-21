/* MAGI browser button.
 *
 * Deliberately tiny. It sends the current tab's URL and a chosen library name
 * to a local MAGI, and does nothing else — no scraping, no downloading, no
 * parsing, no deciding what a page is. All of that is the server's job, where
 * it is deterministic and testable; here it would be a second implementation
 * that drifts from the first.
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
const STORE = { port: "magi-port", library: "magi-library" };

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

  const tab = await currentTab();
  const url = tab?.url || "";
  $("target").textContent = url || "no page";

  if (!/^https?:/i.test(url)) {
    status("This only works on a web page.", "err");
    return;
  }

  let kbs;
  try {
    kbs = await findMagi();
  } catch (err) {
    status(`Could not reach MAGI. Is it running? Start it with: magi ui`, "err");
    return;
  }

  if (!kbs.length) {
    status("MAGI is running but has no libraries registered yet.", "err");
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
  $("send").disabled = true;
  status("queueing…");

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
    // worked".
    const kind = { arxiv: "arXiv paper", doi: "DOI", url: "page" }[body.source_type]
      || body.source_type;
    status(`Queued as ${kind}: ${body.value}\n${body.pending} waiting in ${library}.`, "ok");
  } catch (err) {
    status(String(err.message || err), "err");
    $("send").disabled = false;
  }
});

$("port").addEventListener("change", () => {
  $("send").disabled = true;
  init();
});

init();
