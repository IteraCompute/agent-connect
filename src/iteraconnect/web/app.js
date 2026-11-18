"use strict";
const $ = (id) => document.getElementById(id);
const clientIcons = {
  claude: "✳",
  codex: "⌘",
  workbuddy: "W",
  "workbuddy-ai": "W",
  "visual-studio": "VS",
  vscode: "〈〉",
  openclaw: "◈",
  hermes: "H",
};
const protocols = {
  chat: "Chat Completions",
  responses: "Responses",
  anthropic: "Anthropic Messages",
  gemini: "Gemini",
};
const caseLabels = {
  text: "文本回复",
  stream: "流式输出",
  "tool-roundtrip": "工具调用往返",
};
const modelCatalogs = new Map();
let token = sessionStorage.getItem("agent-connect-token") || "";
if (/^#[A-Za-z0-9_-]{43}$/.test(location.hash)) {
  token = location.hash.slice(1);
  sessionStorage.setItem("agent-connect-token", token);
  history.replaceState(null, "", "/");
}
let state,
  selectedClient,
  resultSelection,
  adding = false,
  working = false;
function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("icon");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(svg.namespaceURI, "use");
  use.setAttribute("href", "#i-" + name);
  svg.append(use);
  return svg;
}
function textElement(tag, className, text) {
  const el = document.createElement(tag);
  el.className = className;
  el.textContent = text;
  return el;
}
async function api(path, body) {
  const options = { headers: { "X-Agent-Connect": token } };
  if (body !== undefined) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch("/api/" + path, options);
  } catch {
    throw new Error(
      "无法连接本地服务。请确认启动窗口仍在运行，再重新打开页面。",
    );
  }
  const data = await response.json();
  if (!response.ok) {
    if (data.state) render(data.state);
    throw new Error(data.error || "操作未完成，请重试。");
  }
  return data;
}
function result(title, message, kind = "", data) {
  resultSelection = undefined;
  $("setup-guide").hidden = true;
  $("guide-fields").replaceChildren();
  $("result").className = "result-box" + (kind ? " " + kind : "");
  $("result-title").textContent = title;
  $("result-message").textContent = message;
  $("result-symbol").replaceChildren(
    icon(kind === "success" ? "check" : kind === "busy" ? "refresh" : "info"),
  );
  $("result-cards").replaceChildren();
  $("result-cards").hidden = true;
  $("result-details").hidden = !data;
  $("result-details").open = false;
  $("details-label").textContent = "查看测试详情";
  $("details-note").textContent = "仅显示脱敏结果";
  $("copy-export").hidden = true;
  $("copy-export").replaceChildren(
    icon("copy"),
    document.createTextNode("复制配置"),
  );
  $("result-json").textContent = data ? JSON.stringify(data, null, 2) : "";
}
function updateAvailability() {
  document.querySelectorAll("button,input,select").forEach((el) => {
    el.disabled = working || !state;
  });
  $("workspace").setAttribute("aria-busy", String(working));
  if (!state || working) return;
  const client = state.clients.find((c) => c.id === selectedClient);
  const matched = client.protocols.some((p) => selectedProtocols().includes(p));
  ["connect", "probe", "smoke", "export"].forEach((id) => {
    $(id).disabled = !matched;
  });
  $("disconnect").disabled = !client.connected;
  $("provider").disabled = adding;
  $("add-provider").disabled = adding;
}
async function busy(message, work) {
  if (working) return;
  working = true;
  updateAvailability();
  result("正在处理", message, "busy");
  let focusId;
  try {
    await work();
  } catch (e) {
    result("操作未完成", e.message, "error");
    focusId = e.focusId;
  } finally {
    working = false;
    updateAvailability();
    if (focusId) $(focusId).focus();
  }
}
function clearErrors() {
  ["provider-id", "api-key", "model", "base-url"].forEach((id) => {
    $(id).removeAttribute("aria-invalid");
    $(id + "-error").hidden = true;
  });
}
function invalid(id, message) {
  $(id).setAttribute("aria-invalid", "true");
  $(id + "-error").textContent = message;
  $(id + "-error").hidden = false;
  if (id === "base-url") $("advanced").open = true;
  const error = new Error(message);
  error.focusId = id;
  throw error;
}
function selectedProtocols() {
  return [...document.querySelectorAll("[name=protocol]:checked")].map(
    (el) => el.value,
  );
}
function catalogKey() {
  return (
    (adding ? $("provider-id").value.trim() : $("provider").value) +
    "|" +
    $("base-url").value.trim()
  );
}
function renderCatalog() {
  $("model-list").replaceChildren();
  const models = modelCatalogs.get(catalogKey()) || [];
  models.forEach((id) => {
    const option = document.createElement("option");
    option.value = id;
    $("model-list").append(option);
  });
  $("model-help").textContent = models.length
    ? `已获取 ${models.length} 个模型，点击输入框可选择，也可直接输入。`
    : "可直接输入模型 ID，也可从 API 获取列表。";
}
function loadProvider() {
  const p = state.settings.providers[$("provider").value];
  if (!p) return;
  adding = false;
  clearErrors();
  $("new-fields").hidden = true;
  $("provider-id").value = "";
  $("provider-name").value = "";
  $("api-key").value = "";
  $("api-key").placeholder = p.has_key
    ? "已保存，留空保留原 key"
    : "填写你的 API key";
  $("model").value = p.model;
  $("base-url").value = p.base_url;
  document.querySelectorAll("[name=protocol]").forEach((el) => {
    el.checked = p.protocols.includes(el.value);
  });
  renderCatalog();
  updatePath();
}
function selectionSnapshot() {
  return JSON.stringify([
    adding ? $("provider-id").value.trim() : $("provider").value,
    selectedClient,
    $("model").value.trim(),
    $("base-url").value.trim(),
    selectedProtocols(),
    Boolean($("api-key").value.trim()),
  ]);
}
function clientNextStep(client) {
  const values = {
    provider: adding ? $("provider-id").value.trim() : $("provider").value,
    model: $("model").value.trim(),
  };
  return client.next_step.replace(
    /\{(provider|model)\}/g,
    (_, name) => values[name] || "…",
  );
}
function updatePath() {
  if (!state) return;
  if (resultSelection && resultSelection !== selectionSnapshot()) {
    result("设置已更改", "请重新测试或导出当前 API、模型与客户端的配置。");
  }
  const p = state.settings.providers[$("provider").value];
  const client = state.clients.find((c) => c.id === selectedClient);
  const currentProtocols = selectedProtocols();
  const protocol = client.protocols.find((p) => currentProtocols.includes(p));
  const matched = Boolean(protocol);
  const keyEntered = Boolean($("api-key").value.trim());
  $("key-status").textContent = keyEntered
    ? "待保存"
    : !adding && p.has_key
      ? "已保存在本机"
      : "尚未填写";
  $("path-provider").textContent = adding
    ? $("provider-name").value.trim() || "我的 API"
    : p.name;
  $("path-model").textContent = $("model").value.trim() || "请选择模型";
  $("path-client").textContent = client.name;
  $("path-client-icon").textContent = clientIcons[client.id];
  $("native-actions").hidden = client.guided;
  $("smoke-label").textContent = client.manual_test
    ? "查看实测步骤"
    : "客户端实测";
  $("connect-label").textContent = client.guided
    ? "获取 Visual Studio 接入信息"
    : "连接 " + client.name;
  $("required-protocol").textContent =
    protocols[protocol || client.protocols[0]];
  $("protocol-match").textContent = matched ? "协议匹配" : "需要配置";
  $("protocol-match").classList.toggle("missing", !matched);
  $("protocol-summary").textContent = `${currentProtocols.length} 种协议`;
  $("compatibility").hidden = matched;
  $("compatibility-text").textContent =
    `此客户端支持 ${client.protocols.map((p) => protocols[p]).join(" 或 ")}。请确认 API 支持后，在地址与协议中勾选。`;
  $("connection-status").textContent = client.connected
    ? "此软件有备份"
    : client.guided
      ? "在软件内添加"
      : "尚未连接";
  $("connection-status").className =
    "badge " + (client.connected ? "good" : "neutral");
  const nextStep = clientNextStep(client);
  $("client-hint").textContent = client.guided
    ? nextStep
    : "接入后：" + nextStep;
  document.querySelectorAll(".client").forEach((el) => {
    const selected = el.dataset.id === selectedClient;
    el.classList.toggle("selected", selected);
    el.setAttribute("aria-checked", String(selected));
    el.tabIndex = selected ? 0 : -1;
  });
  const dirty =
    adding ||
    keyEntered ||
    $("provider").value !== state.settings.selected_provider ||
    selectedClient !== state.settings.client ||
    $("model").value.trim() !== p.model ||
    $("base-url").value.trim() !== p.base_url ||
    [...currentProtocols].sort().join() !== [...p.protocols].sort().join();
  $("save-state").textContent = dirty ? "有未保存更改" : "已保存到本机";
  $("save-state").className = "badge " + (dirty ? "changed" : "neutral");
  updateAvailability();
}
function render(next) {
  const first = !state;
  state = next;
  selectedClient = next.settings.client;
  $("provider").replaceChildren();
  Object.entries(next.settings.providers).forEach(([id, p]) => {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = p.name;
    $("provider").append(option);
  });
  $("provider").value = next.settings.selected_provider;
  renderClients();
  $("settings-location").textContent =
    "本地配置：" + next.settings_path.split(/[\\/]/).pop();
  $("settings-location").title = next.settings_path;
  loadProvider();
  if (first && next.settings.providers[next.settings.selected_provider].has_key)
    result("已读取本地配置", "选择客户端即可连接，也可以先测试 API。");
}
function renderClients() {
  $("client-count").textContent = state.clients.length + " 个客户端";
  $("clients").replaceChildren();
  state.clients.forEach((c) => {
    const button = document.createElement("button");
    button.className = "client";
    button.dataset.id = c.id;
    button.setAttribute("role", "radio");
    button.setAttribute("aria-label", c.name);
    const labels = textElement("span", "client-labels", "");
    labels.append(
      textElement("span", "client-name", c.name),
      textElement(
        "span",
        "client-type",
        c.guided ? "应用内引导" : "自动写入配置",
      ),
      textElement(
        "span",
        "client-status" + (c.connected || c.installed ? " detected" : ""),
        c.connected
          ? "已配置 · 可恢复"
          : c.guided
            ? "Windows · Copilot Chat"
            : c.installed
              ? "已检测到安装"
              : c.config_detected
                ? "发现配置目录"
                : "可配置 · 未检测到",
      ),
    );
    const mark = textElement("span", "client-check", "");
    mark.append(icon("check"));
    const badge = textElement("span", "client-icon", clientIcons[c.id]);
    badge.setAttribute("aria-hidden", "true");
    mark.setAttribute("aria-hidden", "true");
    button.append(badge, labels, mark);
    button.onclick = () => {
      selectedClient = c.id;
      updatePath();
    };
    button.onkeydown = (event) => {
      const keys = [
        "ArrowLeft",
        "ArrowRight",
        "ArrowUp",
        "ArrowDown",
        "Home",
        "End",
      ];
      if (!keys.includes(event.key)) return;
      event.preventDefault();
      const index = state.clients.findIndex(
        (item) => item.id === selectedClient,
      );
      const at =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? state.clients.length - 1
            : (index +
                (["ArrowLeft", "ArrowUp"].includes(event.key) ? -1 : 1) +
                state.clients.length) %
              state.clients.length;
      selectedClient = state.clients[at].id;
      updatePath();
      $("clients").children[at].focus();
    };
    $("clients").append(button);
  });
}
function form({ catalog = false, requireKey = false } = {}) {
  clearErrors();
  const id = adding ? $("provider-id").value.trim() : $("provider").value;
  if (!/^[a-z][a-z0-9-]{0,47}$/.test(id))
    invalid(
      "provider-id",
      "标识需以小写字母开头，使用小写字母、数字或短横线，最多 48 个字符。",
    );
  if (adding && Object.hasOwn(state.settings.providers, id))
    invalid("provider-id", "此标识已存在，请换一个标识。");
  const key = $("api-key").value.trim();
  if (requireKey && !key && (adding || !state.settings.providers[id].has_key))
    invalid("api-key", "请先填写此 API 的 key。");
  if (key && !/^[\x21-\x7e]+$/.test(key))
    invalid("api-key", "API key 不能包含空格或非英文字符，请检查复制内容。");
  const base = $("base-url").value.trim();
  let url;
  try {
    url = new URL(base);
  } catch {
    invalid(
      "base-url",
      "请输入完整 API 地址，例如 https://api.example.com/v1。",
    );
  }
  if (
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    (url.protocol !== "https:" &&
      !(
        url.protocol === "http:" &&
        ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)
      ))
  )
    invalid(
      "base-url",
      "请使用 HTTPS 地址（本机接口可用 HTTP），不要包含账号、查询参数或片段。",
    );
  const model = $("model").value.trim();
  if (!catalog && !model)
    invalid("model", "请选择或输入模型 ID，也可先点击「获取模型」。");
  if (!selectedProtocols().length) {
    $("advanced").open = true;
    throw new Error("请至少选择一种 API 实际支持的协议。");
  }
  return {
    provider: id,
    client: selectedClient,
    name: adding
      ? $("provider-name").value.trim() || id
      : state.settings.providers[id].name,
    api_key: key,
    base_url: base,
    model,
    protocols: selectedProtocols(),
  };
}
async function save(options) {
  render(await api("save", form(options)));
}
function showTest(data, type) {
  const passed = type === "probe" ? data.passed : data.status === "passed";
  let message = data.message;
  if (!message)
    message =
      type === "probe"
        ? passed
          ? "文本回复、完整流式输出和工具调用往返均成功。"
          : "部分项目未通过。展开详情查看；遇到 429 可稍后重试，Auto 失败时可选择具体模型。"
        : passed
          ? "已从实际客户端回复中确认 ITERACONNECT_OK。"
          : data.status === "not-installed"
            ? "未检测到客户端，请先安装后重试。"
            : "客户端实测未通过，请展开详情查看。";
  const manual =
    data.status === "manual-required" || data.status === "not-installed";
  result(
    passed
      ? type === "probe"
        ? "API 测试通过"
        : "客户端实测通过"
      : manual
        ? data.status === "not-installed"
          ? "尚未检测到客户端"
          : "需要在客户端继续操作"
        : "测试未全部通过",
    message,
    passed ? "success" : manual ? "" : "error",
    data,
  );
  const cases =
    type === "probe"
      ? data.results || []
      : [{ case: selectedClient, status: data.status, seconds: data.seconds }];
  cases.forEach((item) => {
    const ok = item.status === "passed";
    const card = textElement(
      "div",
      "result-card" + (ok ? "" : manual ? " manual" : " failed"),
      "",
    );
    const labels = document.createElement("div");
    labels.append(
      textElement(
        "strong",
        "",
        type === "probe"
          ? caseLabels[item.case] || item.case
          : state.clients.find((c) => c.id === selectedClient).name,
      ),
      textElement(
        "small",
        "",
        (ok
          ? "通过"
          : item.status === "not-installed"
            ? "未检测到安装"
            : manual
              ? "待手动验证"
              : "未通过") +
          (typeof item.seconds === "number"
            ? ` · ${item.seconds.toFixed(1)} 秒`
            : ""),
      ),
    );
    card.append(icon(ok ? "check" : "info"), labels);
    $("result-cards").append(card);
  });
  $("result-cards").hidden = cases.length === 0;
  resultSelection = selectionSnapshot();
}
$("provider").onchange = loadProvider;
["provider-name", "model", "api-key", "base-url", "provider-id"].forEach(
  (id) => {
    $(id).oninput = () => {
      clearErrors();
      if (["base-url", "provider-id"].includes(id)) renderCatalog();
      if (id === "api-key") {
        modelCatalogs.delete(catalogKey());
        renderCatalog();
      }
      updatePath();
    };
  },
);
document.querySelectorAll("[name=protocol]").forEach((el) => {
  el.onchange = updatePath;
});
$("fix-protocol").onclick = () => {
  $("advanced").open = true;
  document
    .querySelector(
      `[name=protocol][value="${state.clients.find((c) => c.id === selectedClient).protocol}"]`,
    )
    .focus();
};
$("add-provider").onclick = () => {
  adding = true;
  clearErrors();
  $("new-fields").hidden = false;
  $("advanced").open = true;
  ["api-key", "provider-id", "provider-name", "base-url", "model"].forEach(
    (id) => {
      $(id).value = "";
    },
  );
  $("api-key").placeholder = "填写新的 API key";
  document.querySelectorAll("[name=protocol]").forEach((el) => {
    el.checked = el.value === "chat";
  });
  renderCatalog();
  updatePath();
  $("provider-id").focus();
};
$("cancel-provider").onclick = loadProvider;
$("save").onclick = () =>
  busy("正在保存本地设置…", async () => {
    await save();
    result(
      "设置已保存",
      "API 设置已保存到本机。选择客户端即可连接。",
      "success",
    );
  });
$("reload").onclick = () =>
  busy("正在重新读取配置文件…", async () => {
    render(await api("reload", {}));
    result("配置已更新", "已重新读取本地配置文件。", "success");
  });
$("models").onclick = () =>
  busy("正在获取当前 API 的模型列表…", async () => {
    const draft = form({ catalog: true, requireKey: true });
    const data = await api("models", draft);
    modelCatalogs.set(catalogKey(), data.models);
    renderCatalog();
    result(
      data.models.length ? "模型列表已更新" : "API 未返回模型列表",
      data.models.length
        ? `已获取 ${data.models.length} 个模型。点击模型输入框选择，或直接输入模型 ID。当前设置尚未自动保存。`
        : "仍可在模型输入框中直接填写 API 提供的模型 ID。",
      data.models.length ? "success" : "",
    );
  });
async function submitAction(route, requireKey = false) {
  const { state: next, ...data } = await api(route, form({ requireKey }));
  render(next);
  return data;
}
function showGuide(data) {
  result(
    "接入信息已准备好",
    "在 Visual Studio 中添加模型后，发送测试消息确认回复。",
  );
  const fields = [
    ["base_url", "端点地址"],
    ["model", "模型 ID"],
    ["local_key", "API Key（本地网关令牌）"],
  ];
  fields.forEach(([name, label]) => {
    const row = textElement("div", "guide-value", "");
    const input = document.createElement("input");
    input.id = "guide-" + name;
    input.type = name === "local_key" ? "password" : "text";
    input.readOnly = true;
    input.value = data[name];
    const title = textElement("label", "", label);
    title.htmlFor = input.id;
    const copy = textElement("button", "secondary", "复制");
    copy.setAttribute("aria-label", "复制" + label);
    copy.onclick = async () => {
      try {
        await navigator.clipboard.writeText(input.value);
        copy.textContent = "已复制";
      } catch {
        input.type = "text";
        input.focus();
        input.select();
        copy.textContent = "请手动复制";
      }
    };
    row.append(title, input, copy);
    $("guide-fields").append(row);
  });
  $("setup-guide").hidden = false;
  $("guide-title").focus();
  resultSelection = selectionSnapshot();
}
$("connect").onclick = () =>
  busy("正在准备接入…", async () => {
    const data = await submitAction("connect", true);
    if (data.setup === "guided") return showGuide(data);
    result("客户端已配置", data.message, "success");
    resultSelection = selectionSnapshot();
    $("client-hint").textContent = data.message;
  });
$("disconnect").onclick = () =>
  busy("正在检查并恢复原配置…", async () => {
    const data = await api("disconnect", { client: selectedClient });
    state.clients.find((c) => c.id === selectedClient).connected = false;
    renderClients();
    updatePath();
    result("已恢复原配置", data.message, "success");
  });
$("export").onclick = () =>
  busy("正在生成配置片段…", async () => {
    const data = await submitAction("export");
    result("配置片段已生成", data.message);
    $("result-json").textContent = data.fragment;
    $("details-label").textContent = "查看配置片段";
    $("details-note").textContent = "仅含本地网关令牌，请在本机使用";
    $("copy-export").hidden = false;
    $("result-details").hidden = false;
    $("result-details").open = true;
    resultSelection = selectionSnapshot();
  });
$("copy-export").onclick = async () => {
  try {
    await navigator.clipboard.writeText($("result-json").textContent);
    $("copy-export").replaceChildren(
      icon("check"),
      document.createTextNode("已复制"),
    );
  } catch {
    $("details-note").textContent =
      "浏览器未允许复制，请选中下方配置手动复制。";
  }
};
["probe", "smoke"].forEach((type) => {
  $(type).onclick = () => {
    const client = state.clients.find((c) => c.id === selectedClient);
    if (type === "smoke" && client.manual_test) {
      showTest(
        {
          status: "manual-required",
          message:
            clientNextStep(client) +
            " 在新会话发送：Reply with exactly ITERACONNECT_OK. 核对回复。",
        },
        type,
      );
      return;
    }
    return busy(
      type === "probe"
        ? "正在测试文本、流式与工具调用，请稍候…"
        : "正在启动隔离的客户端测试，最长约 90 秒…",
      async () => {
        showTest(await submitAction(type, true), type);
      },
    );
  };
});
updateAvailability();
api("state")
  .then(render)
  .catch((e) => {
    $("fatal").hidden = false;
    $("fatal").textContent = e.message;
    $("service-status").classList.add("unavailable");
    $("service-status").replaceChildren(
      textElement("span", "status-dot", ""),
      document.createTextNode("本地服务未连接"),
    );
    result("无法读取配置", e.message, "error");
  });
