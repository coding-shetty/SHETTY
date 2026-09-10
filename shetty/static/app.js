import { icon, hydrateIcons, orb } from "./icons.js";

const $ = (selector, root = document) => root.querySelector(selector);
const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const pageNames = {
  assistant: ["Assistant", "Your personal space", "spark"],
  memory: ["Memory", "The things worth keeping", "memory"],
  tasks: ["Tasks & reminders", "A little peace of mind", "checklist"],
  activity: ["Activity", "You stay in control", "activity"],
  settings: ["Settings", "Make yourself at home", "settings"],
};
const toolTitles = {
  save_memory: "Save a memory",
  create_task: "Create a task",
  read_file: "Read a file",
  open_app: "Open an application",
  open_website: "Open a website",
};
const toolIcons = {
  save_memory: "memory",
  create_task: "checklist",
  read_file: "folder",
  open_app: "window",
  open_website: "globe",
};
const state = {
  boot: null,
  status: {
    connected: false,
    ready: false,
    capabilities: [],
    models: [],
    message: "Checking your local engine…",
  },
  page: "assistant",
  conversation: null,
  messages: [],
  conversationProposals: [],
  draft: "",
  sendingText: "",
  busy: false,
  memoryFilter: "all",
  memoryQuery: "",
  taskFilter: "open",
  activityFilter: "all",
  desiredModel: "",
  confirm: null,
  refreshPromise: null,
  checking: false,
  pendingDecisions: new Set(),
};

async function api(path, options = {}) {
  const headers = { ...options.headers };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.method && !["GET", "HEAD"].includes(options.method))
    headers["X-Shetty-Token"] = state.boot?.token || "";
  let response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers,
      body:
        options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: "same-origin",
    });
  } catch {
    throw new Error(
      "Cannot reach SHETTY. Check that the local server is still running, then refresh.",
    );
  }
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error(
      "The server returned an unexpected response. Try refreshing SHETTY.",
    );
  }
  if (!response.ok) {
    const detail = Array.isArray(result.detail)
      ? result.detail.map((item) => item.msg).join(" · ")
      : result.detail;
    throw new Error(detail || "This request could not be completed.");
  }
  return result;
}

function toast(message, error = false) {
  const element = document.createElement("div");
  element.className = `toast${error ? " error" : ""}`;
  element.innerHTML = `${icon(error ? "alert" : "check")}<span>${escapeHtml(message)}</span>`;
  $("#toast-region").append(element);
  setTimeout(() => element.remove(), error ? 8000 : 4200);
}

function shortDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "No date"
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
function timeLabel(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "2-digit",
      });
}
function dueLabel(value) {
  if (!value) return "Whenever you’re ready";
  const date = new Date(value);
  if (date.getTime() <= Date.now())
    return `Due · ${shortDate(value)}, ${timeLabel(value)}`;
  const today = new Date();
  const tomorrow = new Date();
  tomorrow.setDate(today.getDate() + 1);
  const day =
    date.toDateString() === today.toDateString()
      ? "Today"
      : date.toDateString() === tomorrow.toDateString()
        ? "Tomorrow"
        : shortDate(value);
  return `${day}, ${timeLabel(value)}`;
}
function pendingCount() {
  return (state.boot?.proposals || []).filter((p) => p.status === "pending")
    .length;
}
function openTasks() {
  return (state.boot?.tasks || []).filter((task) => !task.completed);
}
function formatMessage(text) {
  // Escape first. No raw HTML, remote images, link auto-fetching, or user-supplied attributes.
  return String(text)
    .split(/(```[\s\S]*?```)/g)
    .map((part) => {
      if (part.startsWith("```")) {
        const code = part.replace(/^```[^\n]*\n?/, "").replace(/```$/, "");
        return `<pre><code>${escapeHtml(code)}</code></pre>`;
      }
      return escapeHtml(part)
        .replace(/`([^`\n]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    })
    .join("");
}

function updateChrome() {
  const [title, subtitle, pageIcon] = pageNames[state.page];
  $("#page-title").textContent = title;
  $("#page-subtitle").textContent = subtitle;
  $("#page-icon").innerHTML = icon(pageIcon);
  document.title = `${title} — SHETTY`;
  document.querySelectorAll("[data-page]").forEach((link) => {
    const current = link.dataset.page === state.page;
    link.classList.toggle("active", current);
    if (current) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  if (!state.boot) return;
  $("#memory-count").textContent = state.boot.memories.length;
  $("#task-count").textContent = openTasks().length;
  $("#approval-count").textContent = pendingCount();
  $("#approval-count").hidden = !pendingCount();
  $("#environment-badge").classList.toggle("preview", state.boot.preview);
  $("#environment-badge").innerHTML =
    `<span class="tiny-dot"></span> ${state.boot.preview ? "SANDBOX PREVIEW" : "LOCAL WORKSPACE"}`;
  $("#recent-chats").innerHTML = state.boot.conversations.length
    ? state.boot.conversations
        .slice(0, 6)
        .map(
          (chat) =>
            `<button class="recent-chat ${state.conversation?.id === chat.id ? "selected" : ""}" data-action="open-chat" data-id="${escapeHtml(chat.id)}" title="${escapeHtml(chat.title)}">${escapeHtml(chat.title)}</button>`,
        )
        .join("")
    : '<p class="sidebar-empty">A fresh start. Make it yours.</p>';
}

function renderPage() {
  if (!state.boot) return;
  updateChrome();
  const renderers = {
    assistant: renderAssistant,
    memory: renderMemory,
    tasks: renderTasks,
    activity: renderActivity,
    settings: renderSettings,
  };
  $("#page").innerHTML = renderers[state.page]();
  if (state.page === "assistant" && (state.messages.length || state.busy))
    scrollChat();
}
function navigate(page) {
  if (!pageNames[page]) page = "assistant";
  $("#sidebar").classList.remove("open");
  $("#sidebar-scrim").hidden = true;
  if (location.hash !== `#${page}`) location.hash = page;
  else {
    state.page = page;
    renderPage();
  }
}
window.addEventListener("hashchange", () => {
  state.page = pageNames[location.hash.slice(1)]
    ? location.hash.slice(1)
    : "assistant";
  $("#sidebar").classList.remove("open");
  $("#sidebar-scrim").hidden = true;
  renderPage();
});

function renderAssistant() {
  const today = new Date().toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
  return `<div class="assistant-grid"><section class="assistant-workspace" aria-label="Conversation">
    <div class="session-meta"><span class="session-title">${escapeHtml(state.conversation?.title || "A LITTLE SPACE TO THINK")}</span>${state.conversation ? `<button class="icon-button" data-action="delete-chat" aria-label="Delete this conversation" title="Delete conversation">${icon("trash")}</button>` : `<span class="session-date">${escapeHtml(today)}</span>`}</div>
    <div class="conversation-body" id="conversation-body" role="log" aria-label="Conversation messages" aria-live="polite">${chatBody()}</div>
    <div class="composer-area"><div id="connection-hint">${connectionHint()}</div>
      <form class="composer" id="chat-form"><textarea id="composer-input" name="message" placeholder="Ask SHETTY anything, or start with a thought…" aria-label="Message SHETTY" maxlength="4000" rows="2" ${state.busy ? "disabled" : ""}>${escapeHtml(state.draft)}</textarea>
        <div class="composer-actions"><button type="button" class="composer-plus" data-action="tools" aria-label="Open tool workbench" title="Tool workbench">${icon("plus")}</button><span class="composer-divider"></span>
          <button type="button" class="memory-chip ${state.boot.preferences.include_memory ? "" : "off"}" data-action="toggle-memory" title="Toggle saved memories and tasks in local model context">${icon("memory")} Memory ${state.boot.preferences.include_memory ? "on" : "off"}</button>
          <button type="button" class="composer-model" data-action="settings" title="Choose an installed local model">${escapeHtml(state.boot.model)} ${icon("chevron-down")}</button>
          <button type="button" class="icon-button" data-action="stop-speech" ${state.boot.macos_available ? "" : "disabled"} aria-label="Stop macOS speech" title="Stop macOS speech (available on your Mac)">${icon("volume")}</button>
          <button type="submit" class="send-button" id="send-button" aria-label="Send message" ${state.busy || !state.draft.trim() ? "disabled" : ""}>${state.busy ? '<span class="loading-spinner"></span>' : icon("arrow-up")}</button>
        </div>
      </form><div class="composer-caption"><span>${icon("shield")} Actions ask first. Always.</span><span>SHETTY can make mistakes. You stay in control.</span></div>
    </div></section><aside class="context-panel" id="context-panel" aria-label="Your local setup">${contextPanel()}</aside></div>`;
}
function connectionHint() {
  if (state.status.ready) return "";
  const label = state.status.connected
    ? "Your local model needs a quick check."
    : "Ollama isn’t connected yet.";
  return `<div class="connection-hint"><span class="tiny-dot"></span><span>${label}</span><button type="button" class="text-link" data-action="settings">Connection guide ${icon("arrow")}</button></div>`;
}
function chatBody() {
  if (!state.messages.length && !state.busy)
    return `<div class="welcome">${orb}<div class="hero-eyebrow">YOUR EVERYDAY, WITH A LITTLE MORE POSSIBILITY</div><h1>A mind for your<br><em>everyday.</em></h1><p class="welcome-description">A place to think, remember, and get things done.<br>Powered on your Mac. Guided by you.</p>
    <div class="quick-start"><div class="section-kicker">START WITH SOMETHING SMALL</div><div class="quick-grid">
      <button class="quick-card" data-action="prompt"><span class="quick-card-top">${icon("bulb")}${icon("arrow-up-right")}</span><strong>Think it through</strong><p>A fresh perspective on an idea</p></button>
      <button class="quick-card" data-action="new-memory"><span class="quick-card-top">${icon("memory")}${icon("arrow-up-right")}</span><strong>Keep a thought</strong><p>Give your mind a little room</p></button>
      <button class="quick-card" data-action="new-task"><span class="quick-card-top">${icon("clock")}${icon("arrow-up-right")}</span><strong>Plan a little ahead</strong><p>One less thing to remember</p></button>
    </div></div></div>`;
  let content = state.messages
    .map((message) => {
      const user = message.role === "user";
      const controls =
        !user && message.kind !== "error"
          ? `<div class="message-controls"><button class="icon-button" data-action="copy-message" data-id="${escapeHtml(message.id)}" aria-label="Copy reply" title="Copy reply">${icon("copy")}</button><button class="icon-button" data-action="speak-message" data-id="${escapeHtml(message.id)}" ${state.boot.macos_available ? "" : "disabled"} aria-label="Read reply aloud on your Mac" title="Read aloud using macOS speech">${icon("volume")}</button></div>`
          : "";
      const approvals = state.conversationProposals
        .filter((p) => p.message_id === message.id)
        .map(approvalCard)
        .join("");
      return `<article class="message ${user ? "user-message" : "assistant-message"}"><div class="message-label">${user ? "" : '<img src="/static/mark.svg" alt="">'}${user ? "You" : "SHETTY"}<span class="message-time">${escapeHtml(timeLabel(message.created_at))}</span></div><div class="${message.kind === "error" ? "message-error" : "message-text"}">${user ? escapeHtml(message.content) : formatMessage(message.content)}</div>${controls}${approvals}</article>`;
    })
    .join("");
  if (state.busy)
    content += `<article class="message user-message draft-message"><div class="message-label">You</div><div class="message-text">${escapeHtml(state.sendingText)}</div></article><div class="thinking"><span class="loading-spinner"></span>Thinking on the local engine…<small>First replies can take a little longer</small></div>`;
  return `<div class="messages">${content}</div>`;
}
function contextPanel() {
  const tasks = openTasks().slice(0, 3);
  const ready = state.status.ready;
  return `<section class="setup-card"><div class="setup-heading"><h2>Your local setup</h2><button class="icon-button" data-action="refresh-status" aria-label="Refresh Ollama connection" title="Refresh connection">${icon("refresh")}</button></div>
    <div class="model-display"><div class="model-icon">${icon("chip")}</div><div><div class="section-kicker">LOCAL INTELLIGENCE</div><strong>${escapeHtml(state.boot.model)}</strong></div></div>
    <div class="status-line ${ready ? "ready" : ""}"><span class="tiny-dot"></span>${ready ? "Connected to Ollama" : state.status.connected ? "Model needs attention" : "Waiting for Ollama"}</div>
    <div class="model-specs"><div><strong>4K</strong><span>Context limit</span></div><div><strong>16 GB</strong><span>Memory profile</span></div><div><strong>M4</strong><span>Target chip</span></div></div><hr class="setup-separator">
    <div class="permission-label"><span class="section-kicker">PERMISSION MODE</span><span class="permission-pill">${icon("shield")} Ask every time</span></div>
    <div class="permission-list"><div>${icon("folder")} Only the files you approve</div><div>${icon("lock")} No terminal access</div><div>${icon("monitor")} No background screen capture</div></div>
    <div class="setup-footer"><button class="text-link" data-action="settings">Manage your setup ${icon("arrow")}</button><small>LOCAL-FIRST</small></div>
    </section>
    <section class="radar-panel"><div class="panel-heading"><h2>${icon("clock")} On your radar</h2><button class="icon-button" data-action="new-task" aria-label="Add a task" title="Add a task">${icon("plus")}</button></div>
      ${tasks.length ? tasks.map((task) => `<div class="radar-task"><button class="task-check" data-action="complete-task" data-id="${escapeHtml(task.id)}" data-completed="true" aria-label="Complete ${escapeHtml(task.title)}"></button><div><div class="radar-task-title">${escapeHtml(task.title)}</div><div class="radar-task-time">${escapeHtml(dueLabel(task.due_at))}</div></div></div>`).join("") + '<button class="text-link" data-action="tasks">See all tasks →</button>' : `<div class="radar-empty"><div class="empty-mini-icon">${icon("checklist")}</div><strong>A little breathing room.</strong><p>Your upcoming tasks will appear here.</p><button class="text-link" data-action="new-task">Add your first task ${icon("plus")}</button></div>`}
    </section>
    <section class="memory-promo"><div class="memory-promo-top">${icon("memory")}<span>${state.boot.memories.length} ${state.boot.memories.length === 1 ? "memory" : "memories"} saved</span></div><h3>Made to remember.</h3><p>The small details. The big ideas.<br>A place for the things that matter.</p><button class="text-link" data-action="new-memory">Leave a thought here ${icon("arrow")}</button></section>
    <p class="local-footnote">${icon("lock")}<span>${state.boot.preview ? "This preview is a separate sandbox, not your Mac. Use disposable data here." : "Your conversations and memories live on this Mac, in your local SQLite store."}</span></p>`;
}
function scrollChat() {
  requestAnimationFrame(() => {
    const element = $("#conversation-body");
    if (element) element.scrollTop = element.scrollHeight;
  });
}

function heading(eyebrow, title, description, action = "", buttonLabel = "") {
  return `<div class="page-eyebrow">${eyebrow}</div><div class="workspace-heading"><div><h1>${title}</h1><p>${description}</p></div>${action ? `<button class="button" data-action="${action}">${icon("plus")} ${buttonLabel}</button>` : ""}</div>`;
}
function emptyState(
  iconName,
  title,
  description,
  action = "",
  buttonLabel = "",
) {
  return `<div class="empty-state"><div class="empty-illustration">${icon(iconName)}</div><h2>${title}</h2><p>${description}</p>${action ? `<button class="button secondary" data-action="${action}">${icon("plus")} ${buttonLabel}</button>` : ""}</div>`;
}
function segments(items, active, action) {
  return `<div class="segments" role="group" aria-label="Filter">${items.map(([value, label]) => `<button class="segment ${value === active ? "active" : ""}" data-action="${action}" data-value="${value}" aria-pressed="${value === active}">${label}</button>`).join("")}</div>`;
}
function renderMemory() {
  return `<section class="workspace-page">${heading("YOUR SECOND MEMORY", "A little less to remember.", "Preferences, passing thoughts, and things worth holding onto.<br>Saved by you. Remembered when they’re relevant.", "new-memory", "Add a memory")}
    <div class="workspace-toolbar">${segments(
      [
        ["all", "Everything"],
        ["note", "Notes"],
        ["preference", "Preferences"],
      ],
      state.memoryFilter,
      "memory-filter",
    )}<label class="search-field">${icon("search")}<input id="memory-search" type="search" maxlength="200" placeholder="Find a thought…" aria-label="Search memories" value="${escapeHtml(state.memoryQuery)}"></label></div>
    <div class="memory-grid" id="memory-grid">${memoryCards()}</div><p class="page-footnote">${icon("lock")}<span>Stored locally. ${state.boot.preferences.include_memory ? "Relevant notes, preferences, and active tasks may be shared with your local model. Nothing is saved silently." : "Saved context is currently off. Your notes are kept, but not included in model requests."}</span></p></section>`;
}
function memoryCards() {
  const query = state.memoryQuery.toLocaleLowerCase();
  const memories = state.boot.memories.filter(
    (memory) =>
      (state.memoryFilter === "all" || memory.kind === state.memoryFilter) &&
      `${memory.title} ${memory.content}`.toLocaleLowerCase().includes(query),
  );
  if (!memories.length)
    return state.boot.memories.length
      ? emptyState(
          "search",
          "That thought hasn’t landed here.",
          "Try another search or switch the filter to Everything.",
        )
      : emptyState(
          "memory",
          "Good things deserve a place.",
          "A coffee preference. A project idea. A note to your future self. Start with something small.",
          "new-memory",
          "Save your first memory",
        );
  return memories
    .map(
      (memory) =>
        `<article class="memory-card"><div class="memory-card-top"><span class="tag ${memory.kind}">${icon(memory.kind === "preference" ? "sliders" : "note")}${memory.kind === "preference" ? "Preference" : "Note"}</span><button class="icon-button" data-action="edit-memory" data-id="${escapeHtml(memory.id)}" aria-label="Edit ${escapeHtml(memory.title)}" title="View or edit memory">${icon("edit")}</button></div><h3>${escapeHtml(memory.title)}</h3><p>${escapeHtml(memory.content)}</p><div class="memory-card-footer"><span>Updated ${escapeHtml(shortDate(memory.updated_at))}</span><button class="icon-button" data-action="delete-memory" data-id="${escapeHtml(memory.id)}" aria-label="Delete ${escapeHtml(memory.title)}" title="Delete memory">${icon("trash")}</button></div></article>`,
    )
    .join("");
}
function renderTasks() {
  return `<section class="workspace-page">${heading("MAKE ROOM FOR WHAT MATTERS", "One less thing on your mind.", "A gentle nudge at the right time. Keep a task for later,<br>or set a one-off reminder for something you don’t want to miss.", "new-task", "Add a task")}
    <div class="reminder-info">${icon("moon")}<span>Reminders run while SHETTY is open and your Mac is awake. If you’re away, a missed reminder appears once when SHETTY resumes. ${state.boot.preview ? "Preview reminders stay in this sandbox." : "Desktop notifications are opt-in in Settings."}</span></div>
    <div class="workspace-toolbar">${segments(
      [
        ["open", "On your list"],
        ["completed", "Completed"],
        ["all", "All tasks"],
      ],
      state.taskFilter,
      "task-filter",
    )}<div class="task-stats"><span><strong>${openTasks().length}</strong> open</span><span><strong>${state.boot.tasks.filter((t) => t.completed).length}</strong> complete</span></div></div><div id="task-list-container">${taskList()}</div>
    <p class="page-footnote">${icon("shield")}One-off reminders only. No recurring loops, unattended app actions, or continuous monitoring.</p></section>`;
}
function taskList() {
  const tasks = state.boot.tasks.filter(
    (task) =>
      state.taskFilter === "all" ||
      (state.taskFilter === "completed" ? task.completed : !task.completed),
  );
  if (!tasks.length)
    return state.taskFilter === "completed"
      ? emptyState(
          "checklist",
          "Progress will find its way here.",
          "Complete a task and it will move to this list.",
        )
      : emptyState(
          "clock",
          "Nothing pressing. That feels good.",
          "Let SHETTY hold the small things so you can focus on the bigger ones.",
          "new-task",
          "Add your first task",
        );
  return `<div class="task-list">${tasks.map((task) => `<article class="task-row ${task.completed ? "completed" : ""}"><button class="task-check ${task.completed ? "checked" : ""}" data-action="complete-task" data-id="${escapeHtml(task.id)}" data-completed="${!task.completed}" aria-label="${task.completed ? "Reopen" : "Complete"} ${escapeHtml(task.title)}">${task.completed ? icon("check") : ""}</button><div class="task-row-text"><div class="task-row-title">${escapeHtml(task.title)}</div><div class="task-row-meta">${icon(task.due_at ? "bell" : "note")} ${escapeHtml(dueLabel(task.due_at))}${task.notified_at ? " · Reminder delivered in app" : ""}</div></div>${task.due_at && !task.completed ? `<span class="due-tag ${new Date(task.due_at).getTime() <= Date.now() ? "overdue" : ""}">${new Date(task.due_at).getTime() <= Date.now() ? "Due" : "Scheduled"}</span>` : ""}<button class="icon-button" data-action="delete-task" data-id="${escapeHtml(task.id)}" aria-label="Delete ${escapeHtml(task.title)}" title="Delete task">${icon("trash")}</button></article>`).join("")}</div>`;
}

function approvalCard(proposal) {
  const pending = proposal.status === "pending";
  const labels = {
    title: "Title",
    content: "Content",
    kind: "Type",
    app: "Application",
    url: "Destination",
    due_at: "Reminder time (UTC)",
    root_id: "Approved folder",
    path: "Relative path",
  };
  const args = Object.entries(proposal.arguments)
    .filter(([, value]) => value !== null)
    .map(([key, value]) => {
      if (key === "root_id") {
        const root = state.boot.roots.find((r) => r.id === value);
        value = root
          ? `${root.label} — ${root.path}`
          : "Folder no longer approved";
      }
      return `<div class="argument-row"><strong>${escapeHtml(labels[key] || key)}</strong><span>${escapeHtml(typeof value === "object" ? JSON.stringify(value, null, 2) : value)}</span></div>`;
    })
    .join("");
  const notes = {
    save_memory:
      "Saves this exact content to your local memory. It may be included in future replies when saved context is on.",
    create_task:
      "Creates this task in SHETTY. A scheduled time adds a one-off reminder, not an autonomous action.",
    read_file:
      "Reads up to 64 KiB of text. The result is saved locally with this approval and, if linked to a chat, a bounded excerpt can be used on your next message.",
    open_app:
      "Opens this application on your Mac. It does not grant control over the app or its contents.",
    open_website:
      "Opens this exact URL in your default browser. The destination may use your existing browser session and make network requests.",
  };
  return `<article class="approval-card ${escapeHtml(proposal.status)}" data-proposal="${escapeHtml(proposal.id)}"><div class="approval-top">${icon(toolIcons[proposal.tool] || "shield")}<h3>${escapeHtml(toolTitles[proposal.tool] || proposal.tool)}</h3><span class="approval-status">${pending ? "Your permission" : escapeHtml(proposal.status)}</span></div><div class="approval-arguments">${args}</div>
    ${pending ? `<p class="approval-note">${icon("shield")}<span>${notes[proposal.tool] || "Review the exact request before approving."}</span></p><div class="approval-actions"><small>One use · expires ${escapeHtml(timeLabel(proposal.expires_at))}</small><button class="button ghost small" data-action="decide" data-id="${escapeHtml(proposal.id)}" data-approve="false" ${state.pendingDecisions.has(proposal.id) ? "disabled" : ""}>Decline</button><button class="button small" data-action="decide" data-id="${escapeHtml(proposal.id)}" data-approve="true" ${state.pendingDecisions.has(proposal.id) ? "disabled" : ""}>${icon("check")} Approve once</button></div>` : ""}
    ${proposal.result ? `<details class="approval-result"><summary>${proposal.status === "failed" ? "What went wrong" : "View recorded result"}</summary><pre>${escapeHtml(JSON.stringify(proposal.result, null, 2))}</pre></details>` : ""}
    ${proposal.status === "executed" && proposal.conversation_id ? `<div class="approval-actions"><button class="text-link" data-action="continue-chat" data-id="${escapeHtml(proposal.conversation_id)}">Continue with this result ${icon("arrow")}</button></div>` : ""}</article>`;
}
function renderActivity() {
  return `<section class="workspace-page">${heading("NOTHING BEHIND YOUR BACK", "Your assistant. Your say.", "Every proposed action has a visible trail. Review a request,<br>see what happened, and keep the final say with you.")}
    <div class="workspace-toolbar">${segments(
      [
        ["all", "Everything"],
        [
          "pending",
          `Needs approval${pendingCount() ? " · " + pendingCount() : ""}`,
        ],
        ["actions", "Action history"],
      ],
      state.activityFilter,
      "activity-filter",
    )}<button class="button ghost small" data-action="refresh-data">${icon("refresh")} Refresh</button></div>
    <div id="activity-content">${activityContent()}</div><p class="page-footnote">${icon("lock")}The local journal keeps the latest 1,000 events; this view shows the latest 100. It is not a tamper-proof security log.</p></section>`;
}
function activityContent() {
  if (state.activityFilter === "pending") {
    const pending = state.boot.proposals.filter((p) => p.status === "pending");
    return pending.length
      ? `<div class="pending-stack">${pending.map(approvalCard).join("")}</div>`
      : emptyState(
          "shield",
          "All clear. You’re in control.",
          "No actions are waiting for approval. SHETTY cannot silently open apps, save memories, or read files.",
        );
  }
  if (state.activityFilter === "actions")
    return state.boot.proposals.length
      ? `<div class="pending-stack">${state.boot.proposals.map(approvalCard).join("")}</div>`
      : emptyState(
          "activity",
          "A clean slate.",
          "Model suggestions and manual tool requests will be recorded here. Nothing runs without a deliberate approval.",
        );
  const pending = state.boot.proposals.filter((p) => p.status === "pending");
  const eventIcons = {
    memory: "memory",
    task: "checklist",
    reminder: "bell",
    chat: "spark",
    settings: "settings",
    permission: "folder",
    approval: "shield",
    executed: "check",
    denied: "close",
    deleted: "trash",
    error: "alert",
    model: "chip",
  };
  const journal = state.boot.events.length
    ? `<div class="journal"><div class="journal-heading">THE LOCAL JOURNAL</div>${state.boot.events.map((event) => `<article class="journal-event"><div class="event-icon ${event.category === "error" ? "error" : ["reminder", "approval"].includes(event.category) ? "amber" : ""}">${icon(eventIcons[event.category] || "activity")}</div><div class="event-copy"><h3>${escapeHtml(event.title)}</h3>${event.detail ? `<p>${escapeHtml(event.detail)}</p>` : ""}</div><div class="event-time">${escapeHtml(shortDate(event.created_at))}<br>${escapeHtml(timeLabel(event.created_at))}</div></article>`).join("")}</div>`
    : emptyState(
        "activity",
        "The beginning of a good working relationship.",
        "Saved memories, reminders, and approved actions will leave a record here. No pretend activity. Just what actually happened.",
      );
  return `${pending.length ? `<div class="pending-stack">${pending.map(approvalCard).join("")}</div>` : '<div class="activity-intro">' + icon("check") + "No actions waiting for your approval.</div>"}${journal}`;
}

function commandBox(command) {
  return `<div class="command-box">${icon("terminal")}<code>${escapeHtml(command)}</code><button type="button" class="icon-button" data-action="copy-command" data-value="${escapeHtml(command)}" aria-label="Copy command" title="Copy command">${icon("copy")}</button></div>`;
}
function settingToggle(key, title, description, disabled = false) {
  return `<div class="setting-row"><div><h3>${title}</h3><p>${description}</p></div><button type="button" class="switch" role="switch" aria-label="${title}" aria-checked="${state.boot.preferences[key]}" data-action="toggle-setting" data-key="${key}" ${disabled ? "disabled" : ""}></button></div>`;
}
function engineContent() {
  const connected = state.status.ready;
  const caps = state.status.capabilities || [];
  const options = state.status.models?.length
    ? state.status.models
        .map(
          (model) =>
            `<option value="${escapeHtml(model.name)}" ${(state.desiredModel || state.boot.model) === model.name ? "selected" : ""} ${model.blocked ? "disabled" : ""}>${escapeHtml(model.name)} · ${(model.size / 1e9).toFixed(1)} GB${model.blocked ? " · blocked" : ""}</option>`,
        )
        .join("")
    : `<option value="${escapeHtml(state.boot.model)}">${escapeHtml(state.boot.model)} · not connected</option>`;
  const capLabel = (name) =>
    !state.status.capabilities_verified
      ? "Not verified yet"
      : caps.includes(name)
        ? "Reported by Ollama"
        : "Not reported";
  return `<div class="status-line ${connected ? "ready" : ""}"><span class="tiny-dot"></span>${connected ? "Local engine connected" : state.status.connected ? "Ollama found · model needs attention" : "Waiting for your local engine"}</div>
    <p>${escapeHtml(state.status.message)}</p>
    ${!connected ? commandBox("ollama serve") : ""}
    ${state.boot.preview ? '<div class="preview-notice">This sandbox is not your Mac and cannot reach your Mac’s Ollama. Run SHETTY on your Mac for local chat, file access, and speech. Memory and task controls here use separate sandbox storage.</div>' : ""}
    <label class="input-label" for="model-select">YOUR INSTALLED MODEL</label><form id="model-form" class="model-select-row"><select id="model-select" name="model" aria-label="Select installed model" ${state.status.models?.length ? "" : "disabled"}>${options}</select><button type="submit" class="button secondary" ${state.status.models?.length && !state.busy ? "" : "disabled"}>Use model</button></form>
    <p class="inline-note">${icon("info")}Start with qwen3.5:4b. A 9B model is an experiment, not a measured recommendation. Disk size is not runtime memory.</p>
    <div class="capability-grid"><div class="capability"><span>Tool suggestions</span><strong class="${caps.includes("tools") ? "" : "muted"}">${capLabel("tools")}</strong></div><div class="capability"><span>Vision metadata</span><strong class="${caps.includes("vision") ? "" : "muted"}">${capLabel("vision")}</strong></div></div>
    <p>Capabilities come from <code>/api/show</code>, not the model’s name. Screen understanding is not implemented, even if vision is reported.</p>
    ${state.status.loaded_models?.length > 1 ? `<div class="preview-notice">Multiple models are loaded in Ollama: ${escapeHtml(state.status.loaded_models.join(", "))}. Use <code>ollama ps</code> and stop ones you don’t need. SHETTY does not control other apps’ inference.</div>` : ""}
    <div class="speech-actions"><button class="button secondary small" data-action="refresh-status">${icon("refresh")} Check connection</button><button class="button ghost small" data-action="unload-model" ${connected && !state.busy ? "" : "disabled"}>Unload model</button></div>`;
}
function renderSettings() {
  const folders = state.boot.roots
    .map(
      (root) =>
        `<div class="folder-entry">${icon("folder")}<div><strong>${escapeHtml(root.label)}</strong><code>${escapeHtml(root.path)}</code></div><button class="icon-button" data-action="revoke-folder" data-id="${escapeHtml(root.id)}" aria-label="Revoke access to ${escapeHtml(root.label)}" title="Revoke folder access">${icon("close")}</button></div>`,
    )
    .join("");
  return `<section class="workspace-page">${heading("BUILT LOCAL, ON PURPOSE", "Make yourself at home.", "A modest model. Clear boundaries. A workspace that belongs to you.<br>No subscriptions, new model downloads, or cloud credentials required.")}
    <div class="settings-grid"><div class="settings-column">
      <section class="settings-card"><div class="settings-card-heading">${icon("chip")}<h2>The local engine</h2></div><div id="engine-content">${engineContent()}</div></section>
      <section class="settings-card"><div class="settings-card-heading">${icon("folder")}<h2>A small, approved corner of your Mac</h2></div><p>No folders are shared by default. Approve a dedicated folder, then approve each text-file read separately. Files are read-only, capped at 64 KiB. Hidden files, symlinks, and likely credential filenames are blocked.</p><div class="folder-list">${folders || '<div class="folder-empty">No folders approved. Everything starts private.</div>'}</div><button class="button secondary small" data-action="new-folder" ${state.boot.preview ? "disabled" : ""}>${icon("plus")} Approve a folder</button><p class="inline-note">${icon("shield")}Don’t put passwords or secrets in approved folders. Filename checks cannot recognize every sensitive file.</p></section>
      <section class="settings-card"><div class="settings-card-heading">${icon("lock")}<h2>Your data, close to home</h2></div><p>Chats, notes, tasks, and approval results are in a local SQLite database, not encrypted by this app. Use macOS FileVault and your account permissions.</p><div class="command-box"><code>${escapeHtml(state.boot.data_dir)}/shetty.sqlite3</code></div><p>Delete memories and conversations from their own pages. Revoking a folder stops future reads; it does not erase past excerpts from conversation history.</p></section>
    </div><div class="settings-column">
      <section class="settings-card"><div class="settings-card-heading">${icon("monitor")}<h2>A realistic starting point</h2></div><div class="profile-spec">${icon("monitor")}<div><strong>MacBook Pro · Apple M4</strong><p>16 GB unified memory · configured target</p></div></div><div class="spec-list"><div class="spec-row"><span>Context limit</span><strong>4,096 tokens</strong></div><div class="spec-row"><span>Reply budget</span><strong>768 tokens</strong></div><div class="spec-row"><span>Idle model release</span><strong>2 minutes</strong></div><div class="spec-row"><span>Concurrent generations</span><strong>One at a time</strong></div><div class="spec-row"><span>Cloud models</span><strong>Blocked</strong></div><div class="spec-row"><span>Models over 10 GiB on disk</span><strong>Blocked for this profile</strong></div></div><p class="inline-note">${icon("info")}This is your chosen hardware profile, not a live reading of this server. No performance benchmarks are claimed.</p></section>
      <section class="settings-card"><div class="settings-card-heading">${icon("sliders")}<h2>The way you like things</h2></div>${settingToggle("include_memory", "Use saved context", "Include relevant memories, preferences, and active tasks in local model requests.")}${settingToggle("offer_tools", "Allow tool suggestions", "Only for models that report tool support. Every action still needs your approval.")}${settingToggle("desktop_notifications", "macOS reminder notifications", "Optional system notifications. In-app reminders are always kept.", !state.boot.macos_available)}</section>
      <section class="settings-card"><div class="settings-card-heading">${icon("volume")}<h2>A familiar voice</h2></div><p>Use the speaker beside a reply to hear it through your Mac’s built-in speech. No cloud speech service. Microphone input and whisper.cpp integration come later.</p><div class="speech-actions"><button class="button secondary small" data-action="test-speech" ${state.boot.macos_available ? "" : "disabled"}>${icon("volume")} Try the Mac voice</button><button class="button ghost small" data-action="stop-speech" ${state.boot.macos_available ? "" : "disabled"}>${icon("stop")} Stop</button></div></section>
      <section class="settings-card"><div class="settings-card-heading">${icon("moon")}<h2>There when you need it</h2></div><p>Install an optional per-user login service on your Mac. SHETTY will start at login and check reminders while your Mac is awake. It won’t wake your Mac or keep it from sleeping.</p><div class="speech-actions"><button class="button secondary small" data-action="service-guide">Login service guide ${icon("arrow")}</button></div></section>
    </div></div><div class="settings-footer"><span>SHETTY / VERSION ${escapeHtml(state.boot.version)}</span><span>LESS NOISE. MORE POSSIBILITY.</span></div></section>`;
}

function openModal(title, description, content) {
  const modal = $("#modal");
  $("#modal-content").innerHTML =
    `<div class="modal-inner"><div class="modal-header"><h2 id="modal-title">${escapeHtml(title)}</h2><button type="button" class="icon-button" data-action="close-modal" aria-label="Close dialog">${icon("close")}</button></div><p class="modal-description">${description}</p>${content}</div>`;
  modal.setAttribute("aria-labelledby", "modal-title");
  if (!modal.open) modal.showModal();
  requestAnimationFrame(() => {
    const input = $("input:not([type=checkbox]), textarea, select", modal);
    if (input && !input.disabled) input.focus();
  });
}
function closeModal() {
  $("#modal").close();
  state.confirm = null;
}
function formFooter(label, iconName = "check") {
  return `<div class="form-error" hidden></div><div class="modal-footer"><button type="button" class="button ghost" data-action="close-modal">Cancel</button><button type="submit" class="button">${icon(iconName)} ${label}</button></div>`;
}
function memoryModal(id = null) {
  const memory = id ? state.boot.memories.find((item) => item.id === id) : null;
  if (id && !memory)
    throw new Error("That memory is no longer here. Try refreshing.");
  openModal(
    memory ? "A thought worth keeping." : "Leave a thought here.",
    "Something useful now. Something you’ll be glad to remember later.",
    `<form id="memory-form" data-id="${escapeHtml(id || "")}"><label class="input-label">TYPE<select name="kind"><option value="note" ${memory?.kind !== "preference" ? "selected" : ""}>A note or an idea</option><option value="preference" ${memory?.kind === "preference" ? "selected" : ""}>A personal preference</option></select></label><label class="input-label">GIVE IT A NAME<input name="title" type="text" required maxlength="100" placeholder="e.g. How I like to work" value="${escapeHtml(memory?.title || "")}"></label><label class="input-label">THE THOUGHT<textarea name="content" class="form-textarea" required maxlength="8000" rows="6" placeholder="A small detail. A bright idea. Write it down…">${escapeHtml(memory?.content || "")}</textarea></label><div class="modal-note">${icon("lock")}<span>Saved only when you choose. Local storage is not app-encrypted. Please leave passwords, tokens, and secrets out of your notes.</span></div>${formFooter(memory ? "Save changes" : "Save memory")}</form>`,
  );
}
function taskModal() {
  const tomorrow = new Date(Date.now() + 60 * 60 * 1000);
  const local = new Date(
    tomorrow.getTime() - tomorrow.getTimezoneOffset() * 60000,
  )
    .toISOString()
    .slice(0, 16);
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  openModal(
    "One less thing to hold onto.",
    "Add a task, with an optional nudge when the time is right.",
    `<form id="task-form"><label class="input-label">WHAT’S ON YOUR MIND?<input name="title" type="text" required maxlength="160" placeholder="e.g. Make time for the side project"></label><label class="checkbox-label"><input type="checkbox" name="remind" id="remind-checkbox">Remind me at a specific time</label><label class="input-label" id="due-field" hidden>WHEN<input type="datetime-local" name="due_at" value="${local}"><small>Your browser timezone: ${escapeHtml(zone)}. Stored as UTC.</small></label><div class="modal-note">${icon("moon")}<span>This is a one-off reminder. SHETTY must be running and your Mac awake. Missed reminders appear once when it resumes.</span></div>${formFooter("Add task")}</form>`,
  );
}
function folderModal() {
  if (state.boot.preview)
    throw new Error(
      "Approve folders after running SHETTY on your Mac. File access is disabled in preview.",
    );
  openModal(
    "Share a small corner.",
    "Choose a dedicated folder. You still approve each file read individually.",
    `<form id="folder-form"><label class="input-label">FOLDER NAME<input type="text" name="label" required maxlength="60" placeholder="e.g. Project notes"></label><label class="input-label">ABSOLUTE FOLDER PATH<input type="text" name="path" required maxlength="1024" placeholder="~/Documents/SHETTY Notes"><small>The folder must already exist on this Mac.</small></label><div class="modal-note warning">${icon("shield")}<span>Only share data you intend the assistant to read. Do not approve your whole home directory or a folder containing secrets. Revoking access does not erase past reads.</span></div>${formFooter("Approve folder", "folder")}</form>`,
  );
}
function toolChooser() {
  const mac = state.boot.macos_available;
  const files = !state.boot.preview && state.boot.roots.length;
  openModal(
    "A little help, with your say.",
    "Direct, bounded tools. Choose an action, review the exact request, then approve it once.",
    `<div class="tool-options"><button class="tool-option" data-action="tool-form" data-tool="open_app" ${mac ? "" : "disabled"}>${icon("window")}<strong>Open an app</strong><small>${mac ? "Only allowlisted macOS apps" : "Available on your Mac"}</small></button><button class="tool-option" data-action="tool-form" data-tool="open_website" ${mac ? "" : "disabled"}>${icon("globe")}<strong>Open a website</strong><small>${mac ? "Your default browser" : "Available on your Mac"}</small></button><button class="tool-option" data-action="tool-form" data-tool="read_file" ${files ? "" : "disabled"}>${icon("folder")}<strong>Read a text file</strong><small>${files ? "Approved folders only" : state.boot.preview ? "Disabled in sandbox preview" : "Approve a folder in Settings"}</small></button><button class="tool-option" data-action="new-task">${icon("checklist")}<strong>Set a reminder</strong><small>A nudge, not an autonomous task</small></button></div><div class="modal-note">${icon("shield")}<span>No shell access. No installations. No screen capture. Model-proposed tools use the same approval queue as manual requests.</span></div><button class="text-link" data-action="settings-close">Manage permissions in Settings ${icon("arrow")}</button>`,
  );
}
function toolForm(tool) {
  let fields = "";
  if (tool === "open_app")
    fields = `<label class="input-label">APPLICATION<select name="app">${state.boot.apps.map((name) => `<option>${escapeHtml(name)}</option>`).join("")}</select></label>`;
  else if (tool === "open_website")
    fields =
      '<label class="input-label">EXACT DESTINATION<input name="url" type="url" placeholder="https://example.com" required maxlength="2000"><small>Only HTTP or HTTPS. No credentials in the URL.</small></label>';
  else if (tool === "read_file")
    fields = `<label class="input-label">APPROVED FOLDER<select name="root_id">${state.boot.roots.map((root) => `<option value="${escapeHtml(root.id)}">${escapeHtml(root.label)} — ${escapeHtml(root.path)}</option>`).join("")}</select></label><label class="input-label">RELATIVE FILE PATH<input name="path" type="text" required maxlength="512" placeholder="project/notes.md"><small>UTF-8 text only, up to 64 KiB. No hidden files or symlinks.</small></label>`;
  else throw new Error("That tool is not available.");
  openModal(
    toolTitles[tool],
    "This creates a request, not an action. You’ll review it in Activity before anything happens.",
    `<form id="tool-form" data-tool="${tool}">${fields}<div class="modal-note">${icon("shield")}<span>Approval is one-use and expires in 10 minutes. Folder permissions and arguments are checked again when you approve.</span></div>${formFooter("Review request", "arrow")}</form>`,
  );
}
function confirmAction(title, copy, label, callback) {
  state.confirm = callback;
  openModal(
    title,
    "A deliberate choice. No surprises.",
    `<p class="confirm-copy">${escapeHtml(copy)}</p><div class="modal-footer"><button class="button ghost" data-action="close-modal">Keep it</button><button class="button danger" data-action="confirm">${icon("trash")} ${escapeHtml(label)}</button></div>`,
  );
}
function serviceGuide() {
  openModal(
    "Ready when your Mac is.",
    "An optional per-user macOS login service. No sudo, no sleep prevention, and no unattended application actions.",
    `<ol class="guide-list"><li>Install and test SHETTY in your Python virtual environment on your Mac first.</li><li>Stop the foreground server with Control-C so port 8765 is free.</li><li>With the same virtual environment active, install the login service.</li></ol>${commandBox("python -m shetty service install")}<h3>Check the service</h3>${commandBox("python -m shetty service status")}<h3>Remove it without deleting your data</h3>${commandBox("python -m shetty service uninstall")}<div class="modal-note">${icon("info")}<span>Keep this checkout and its virtual environment at their installed paths. The service starts SHETTY, not Ollama. Open the installed Ollama app on your Mac for chat. Desktop notifications may need macOS permission.</span></div>`,
  );
}

async function refreshData({ passive = false } = {}) {
  while (state.refreshPromise) {
    if (passive) return;
    await state.refreshPromise.catch(() => {});
  }
  const operation = (async () => {
    const previous = state.boot;
    const fresh = await api("/bootstrap");
    state.boot = fresh;
    updateChrome();
    if (!passive) renderPage();
    else if (previous) {
      if (state.page === "assistant") {
        if ($("#context-panel")) $("#context-panel").innerHTML = contextPanel();
        const updated = fresh.proposals.filter(
          (p) => p.conversation_id === state.conversation?.id,
        );
        if (
          !state.busy &&
          state.conversation &&
          JSON.stringify(updated) !==
            JSON.stringify(
              previous.proposals.filter(
                (p) => p.conversation_id === state.conversation.id,
              ),
            )
        ) {
          await loadConversation(state.conversation.id, { navigateTo: false });
        }
      } else if (
        state.page === "memory" &&
        JSON.stringify(previous.memories) !== JSON.stringify(fresh.memories)
      ) {
        if ($("#memory-grid")) $("#memory-grid").innerHTML = memoryCards();
      } else if (
        state.page === "tasks" &&
        JSON.stringify(previous.tasks) !== JSON.stringify(fresh.tasks)
      )
        renderPage();
      else if (
        state.page === "activity" &&
        JSON.stringify([previous.events, previous.proposals]) !==
          JSON.stringify([fresh.events, fresh.proposals]) &&
        !$("#activity-content details[open]")
      ) {
        if ($("#activity-content"))
          $("#activity-content").innerHTML = activityContent();
      }
      const oldIds = new Set(
        previous.events
          .filter((e) => e.category === "reminder")
          .map((e) => e.id),
      );
      const newReminders = fresh.events.filter(
        (e) => e.category === "reminder" && !oldIds.has(e.id),
      );
      newReminders
        .slice(0, 3)
        .forEach((e) => toast(`A little nudge: ${e.title}`));
    }
  })();
  state.refreshPromise = operation;
  try {
    await operation;
  } finally {
    if (state.refreshPromise === operation) state.refreshPromise = null;
  }
}
async function refreshStatus(notify = false) {
  if (state.checking) return;
  state.checking = true;
  try {
    state.status = await api("/status");
    if (state.page === "assistant") {
      if ($("#context-panel")) $("#context-panel").innerHTML = contextPanel();
      if ($("#connection-hint"))
        $("#connection-hint").innerHTML = connectionHint();
    }
    if (
      state.page === "settings" &&
      $("#engine-content") &&
      !$("#model-form")?.contains(document.activeElement)
    )
      $("#engine-content").innerHTML = engineContent();
    if (notify)
      toast(
        state.status.ready
          ? "Connected to your local engine."
          : state.status.message,
        !state.status.ready,
      );
  } finally {
    state.checking = false;
  }
}
async function loadConversation(id, { navigateTo = true } = {}) {
  if (state.busy)
    throw new Error("Wait for the local reply before changing conversations.");
  const result = await api(`/conversations/${id}`);
  state.conversation = result.conversation;
  state.messages = result.messages;
  state.conversationProposals = result.proposals;
  state.sendingText = "";
  if (navigateTo) navigate("assistant");
  else if (state.page === "assistant") renderPage();
  updateChrome();
}
async function newChat() {
  if (state.busy)
    throw new Error(
      "Wait for the current reply before starting a fresh conversation.",
    );
  state.conversation = null;
  state.messages = [];
  state.conversationProposals = [];
  state.draft = "";
  navigate("assistant");
  requestAnimationFrame(() => $("#composer-input")?.focus());
}
async function sendMessage(text = state.draft.trim()) {
  if (!text || state.busy) return;
  if (!state.status.ready) {
    toast(
      state.boot.preview
        ? "This preview cannot reach your Mac’s Ollama. See Settings for the local connection guide."
        : state.status.message,
      true,
    );
    return;
  }
  state.busy = true;
  state.sendingText = text;
  state.draft = "";
  renderPage();
  let success = false;
  try {
    if (!state.conversation)
      state.conversation = await api("/conversations", { method: "POST" });
    const result = await api(`/conversations/${state.conversation.id}/chat`, {
      method: "POST",
      body: { message: text },
    });
    state.conversation = result.conversation;
    state.messages = result.messages;
    state.conversationProposals = result.proposals;
    success = true;
  } catch (error) {
    toast(error.message, true);
    state.draft = text;
    if (state.conversation) {
      try {
        const data = await api(`/conversations/${state.conversation.id}`);
        state.messages = data.messages;
        state.conversationProposals = data.proposals;
        state.conversation = data.conversation;
      } catch {
        /* Keep existing local UI until the server is reachable again. */
      }
    }
  } finally {
    state.busy = false;
    state.sendingText = "";
    renderPage();
    try {
      await refreshData({ passive: true });
    } catch {
      /* Main request already surfaced its failure. */
    }
    if (success) requestAnimationFrame(() => $("#composer-input")?.focus());
    refreshStatus().catch(() => {});
  }
}
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied. Ready when you are.");
  } catch {
    throw new Error(
      "Clipboard permission is unavailable. Select and copy the visible text manually.",
    );
  }
}
async function toggleSetting(key, button = null) {
  const value = !state.boot.preferences[key];
  if (button) button.disabled = true;
  try {
    state.boot.preferences = await api("/settings", {
      method: "PATCH",
      body: { [key]: value },
    });
    renderPage();
    toast(
      key === "include_memory"
        ? `Saved context is now ${value ? "on" : "off"}.`
        : "Preference updated.",
    );
  } finally {
    if (button?.isConnected) button.disabled = false;
  }
}
async function decideProposal(id, approve) {
  if (state.pendingDecisions.has(id)) return;
  state.pendingDecisions.add(id);
  document
    .querySelectorAll(`[data-proposal="${CSS.escape(id)}"] button`)
    .forEach((button) => {
      button.disabled = true;
    });
  try {
    const result = await api(`/proposals/${id}/decision`, {
      method: "POST",
      body: { approve },
    });
    if (result.status === "failed")
      toast(result.result?.error || "The action could not complete.", true);
    else
      toast(
        approve
          ? "Approved action completed. The result is recorded."
          : "Request declined. Nothing was executed.",
      );
    if (state.conversation && !state.busy)
      await loadConversation(state.conversation.id, { navigateTo: false });
    await refreshData();
  } catch (error) {
    await refreshData().catch(() => {});
    throw error;
  } finally {
    state.pendingDecisions.delete(id);
    renderPage();
  }
}

async function handleAction(button) {
  const { action, id, value, tool, key } = button.dataset;
  if (action === "menu") {
    $("#sidebar").classList.toggle("open");
    $("#sidebar-scrim").hidden = !$("#sidebar").classList.contains("open");
  } else if (action === "settings" || action === "tasks") navigate(action);
  else if (action === "settings-close") {
    closeModal();
    navigate("settings");
  } else if (action === "search") {
    navigate("memory");
    setTimeout(() => $("#memory-search")?.focus(), 30);
  } else if (action === "new-chat") await newChat();
  else if (action === "open-chat") await loadConversation(id);
  else if (action === "delete-chat") {
    if (!state.conversation) return;
    const conversationId = state.conversation.id;
    confirmAction(
      "Let this conversation go?",
      "This removes the conversation and its linked approval records and file excerpts. Memories and tasks saved separately are kept. This is not secure erasure of disk backups.",
      "Delete conversation",
      async () => {
        await api(`/conversations/${conversationId}`, { method: "DELETE" });
        closeModal();
        await newChat();
        await refreshData();
        toast("Conversation deleted.");
      },
    );
  } else if (action === "prompt") {
    state.draft =
      "Help me think through an idea. Ask me a few useful questions to get started.";
    renderPage();
    $("#composer-input")?.focus();
  } else if (action === "new-memory") memoryModal();
  else if (action === "edit-memory") memoryModal(id);
  else if (action === "delete-memory") {
    const memory = state.boot.memories.find((item) => item.id === id);
    if (!memory) return;
    confirmAction(
      "Make a little room?",
      `Delete “${memory.title}” from saved memory? Existing conversations may still contain references to it.`,
      "Delete memory",
      async () => {
        await api(`/memories/${id}`, { method: "DELETE" });
        closeModal();
        await refreshData();
        toast("Memory deleted.");
      },
    );
  } else if (action === "new-task") taskModal();
  else if (action === "complete-task") {
    button.disabled = true;
    try {
      await api(`/tasks/${id}`, {
        method: "PATCH",
        body: { completed: button.dataset.completed === "true" },
      });
      await refreshData();
      toast(
        button.dataset.completed === "true"
          ? "One less thing. Nicely done."
          : "Task is back on your list.",
      );
    } finally {
      if (button.isConnected) button.disabled = false;
    }
  } else if (action === "delete-task") {
    const task = state.boot.tasks.find((item) => item.id === id);
    if (!task) return;
    confirmAction(
      "Take this off your list?",
      `Delete “${task.title}” and cancel any undelivered reminder?`,
      "Delete task",
      async () => {
        await api(`/tasks/${id}`, { method: "DELETE" });
        closeModal();
        await refreshData();
        toast("Task deleted.");
      },
    );
  } else if (action === "memory-filter") {
    state.memoryFilter = value;
    renderPage();
  } else if (action === "task-filter") {
    state.taskFilter = value;
    renderPage();
  } else if (action === "activity-filter") {
    state.activityFilter = value;
    renderPage();
  } else if (action === "refresh-status") {
    button.disabled = true;
    try {
      await refreshStatus(true);
    } finally {
      if (button.isConnected) button.disabled = false;
    }
  } else if (action === "refresh-data") {
    await refreshData();
    toast("Workspace refreshed.");
  } else if (action === "toggle-setting") await toggleSetting(key, button);
  else if (action === "toggle-memory")
    await toggleSetting("include_memory", button);
  else if (action === "tools") toolChooser();
  else if (action === "tool-form") toolForm(tool);
  else if (action === "new-folder") folderModal();
  else if (action === "revoke-folder") {
    const root = state.boot.roots.find((item) => item.id === id);
    if (!root) return;
    confirmAction(
      "Close this door?",
      `Revoke access to “${root.label}”? Pending file reads will fail. Past file excerpts are not erased; delete their conversation to remove those records.`,
      "Revoke access",
      async () => {
        await api(`/folders/${id}`, { method: "DELETE" });
        closeModal();
        await refreshData();
        toast("Folder access revoked.");
      },
    );
  } else if (action === "decide")
    await decideProposal(id, button.dataset.approve === "true");
  else if (action === "continue-chat") {
    await loadConversation(id);
    await sendMessage(
      "Use the approved tool results to help with my request. Do not repeat actions that already completed.",
    );
  } else if (action === "copy-command") await copyText(value);
  else if (action === "copy-message") {
    const message = state.messages.find((m) => m.id === id);
    if (message) await copyText(message.content);
  } else if (action === "speak-message") {
    const message = state.messages.find((m) => m.id === id);
    if (message) {
      await api("/speech", {
        method: "POST",
        body: { text: message.content.slice(0, 5000) },
      });
      toast(
        message.content.length > 5000
          ? "Reading the first 5,000 characters on your Mac."
          : "Reading aloud on your Mac.",
      );
    }
  } else if (action === "test-speech") {
    await api("/speech", {
      method: "POST",
      body: {
        text: "Hello. I’m SHETTY. A little help for your everyday. Local on your Mac, and always asking before I act.",
      },
    });
    toast("Playing through your Mac’s speakers.");
  } else if (action === "stop-speech") {
    await api("/speech/stop", { method: "POST" });
    toast("Speech stopped.");
  } else if (action === "unload-model") {
    button.disabled = true;
    try {
      await api("/model/unload", { method: "POST" });
      toast("Model unloaded. It will load again on your next message.");
      await refreshStatus();
    } finally {
      if (button.isConnected) button.disabled = false;
    }
  } else if (action === "service-guide") serviceGuide();
  else if (action === "close-modal") closeModal();
  else if (action === "confirm" && state.confirm) {
    button.disabled = true;
    try {
      await state.confirm();
    } finally {
      if (button.isConnected) button.disabled = false;
    }
  } else if (action === "reload") location.reload();
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (button && !button.disabled)
    handleAction(button).catch((error) => toast(error.message, true));
});
$("#sidebar-scrim").addEventListener("click", () => {
  $("#sidebar").classList.remove("open");
  $("#sidebar-scrim").hidden = true;
});
$("#modal").addEventListener("close", () => {
  state.confirm = null;
});
$("#modal").addEventListener("click", (event) => {
  if (event.target === $("#modal")) {
    const rect = $("#modal").getBoundingClientRect();
    if (
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom
    )
      closeModal();
  }
});
document.addEventListener("input", (event) => {
  if (event.target.id === "composer-input") {
    state.draft = event.target.value;
    const send = $("#send-button");
    if (send) send.disabled = state.busy || !state.draft.trim();
  }
  if (event.target.id === "memory-search") {
    state.memoryQuery = event.target.value;
    $("#memory-grid").innerHTML = memoryCards();
  }
});
document.addEventListener("change", (event) => {
  if (event.target.id === "remind-checkbox") {
    $("#due-field").hidden = !event.target.checked;
    $("#due-field input").required = event.target.checked;
  }
  if (event.target.id === "model-select")
    state.desiredModel = event.target.value;
});
document.addEventListener("keydown", (event) => {
  if (event.isComposing) return;
  if (
    (event.metaKey || event.ctrlKey) &&
    event.key.toLowerCase() === "k" &&
    !$("#modal").open
  ) {
    event.preventDefault();
    navigate("memory");
    setTimeout(() => $("#memory-search")?.focus(), 30);
  }
  if (
    (event.metaKey || event.ctrlKey) &&
    event.key.toLowerCase() === "j" &&
    !$("#modal").open
  ) {
    event.preventDefault();
    newChat().catch((error) => toast(error.message, true));
  }
  if (
    event.target.id === "composer-input" &&
    event.key === "Enter" &&
    !event.shiftKey
  ) {
    event.preventDefault();
    if (!state.busy) sendMessage().catch((error) => toast(error.message, true));
  }
});
document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (
    ![
      "chat-form",
      "memory-form",
      "task-form",
      "folder-form",
      "tool-form",
      "model-form",
    ].includes(form.id)
  )
    return;
  event.preventDefault();
  if (form.id === "chat-form") {
    await sendMessage().catch((error) => toast(error.message, true));
    return;
  }
  const submit = $("button[type=submit]", form);
  if (submit?.disabled) return;
  if (submit) submit.disabled = true;
  const errorBox = $(".form-error", form);
  if (errorBox) errorBox.hidden = true;
  const data = new FormData(form);
  try {
    if (form.id === "memory-form") {
      const body = {
        title: data.get("title"),
        content: data.get("content"),
        kind: data.get("kind"),
      };
      await api(`/memories${form.dataset.id ? "/" + form.dataset.id : ""}`, {
        method: form.dataset.id ? "PUT" : "POST",
        body,
      });
      closeModal();
      await refreshData();
      toast("A thought worth keeping. Memory saved.");
    } else if (form.id === "task-form") {
      let due_at = null;
      if (data.get("remind")) {
        const when = new Date(data.get("due_at"));
        if (Number.isNaN(when.getTime()) || when.getTime() <= Date.now())
          throw new Error("Choose a future time for your reminder.");
        due_at = when.toISOString();
      }
      await api("/tasks", {
        method: "POST",
        body: { title: data.get("title"), due_at },
      });
      closeModal();
      await refreshData();
      toast(
        due_at
          ? "A gentle nudge, scheduled."
          : "Task added. One less thing to hold onto.",
      );
    } else if (form.id === "folder-form") {
      await api("/folders", {
        method: "POST",
        body: { label: data.get("label"), path: data.get("path") },
      });
      closeModal();
      await refreshData();
      toast("Folder approved. Each file read still asks first.");
    } else if (form.id === "tool-form") {
      await api("/proposals", {
        method: "POST",
        body: {
          tool: form.dataset.tool,
          arguments: Object.fromEntries(data),
          conversation_id: state.conversation?.id || null,
        },
      });
      closeModal();
      state.activityFilter = "pending";
      await refreshData();
      navigate("activity");
      toast("Request prepared. Review it before approving.");
    } else if (form.id === "model-form") {
      state.status = await api("/model", {
        method: "PUT",
        body: { model: data.get("model") },
      });
      state.desiredModel = "";
      await refreshData();
      toast("Local model selected. No model was downloaded.");
    }
  } catch (error) {
    if (errorBox && form.isConnected) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    } else toast(error.message, true);
  } finally {
    if (submit?.isConnected) submit.disabled = false;
  }
});

async function init() {
  hydrateIcons();
  state.page = pageNames[location.hash.slice(1)]
    ? location.hash.slice(1)
    : "assistant";
  try {
    state.boot = await api("/bootstrap");
    renderPage();
    refreshStatus().catch((error) => toast(error.message, true));
    setInterval(() => {
      if (document.hidden) return;
      refreshData({ passive: true }).catch(() => {});
      refreshStatus().catch(() => {});
    }, 15000);
  } catch (error) {
    $("#page").innerHTML =
      `<div class="load-error"><div class="page-eyebrow">A QUICK CONNECTION CHECK</div><h1>Let’s get your workspace back.</h1><p>${escapeHtml(error.message)}</p><button class="button secondary" data-action="reload">${icon("refresh")} Try again</button></div>`;
  }
}
init();
