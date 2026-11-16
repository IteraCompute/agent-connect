"use strict";
const $ = (id) => document.getElementById(id);
const icons = {
  claude: "✳",
  codex: "⌘",
  workbuddy: "W",
  "workbuddy-ai": "W",
  openclaw: "◈",
  hermes: "H",
};
let token =
  location.hash.slice(1) || sessionStorage.getItem("agent-connect-token") || "";
if (location.hash) {
  sessionStorage.setItem("agent-connect-token", token);
  history.replaceState(null, "", "/");
}
let state,
  selectedClient,
  adding = false,
  working = false;
async function api(path, body) {
  const options = { headers: { "X-Agent-Connect": token } };
  if (body !== undefined) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch("/api/" + path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "操作未完成，请重试。");
  return data;
}
function result(text, kind = "", data) {
  $("result").textContent = text;
  $("result").className = kind;
  $("result-details").hidden = !data;
  $("result-json").textContent = data ? JSON.stringify(data, null, 2) : "";
}
async function busy(message, work) {
  if (working) return;
  working = true;
  const fields = [...document.querySelectorAll("button,input,select")];
  fields.forEach((el) => (el.disabled = true));
  result(message, "busy");
  try {
    await work();
  } catch (e) {
    result(e.message, "error");
  } finally {
    working = false;
    document
      .querySelectorAll("button,input,select")
      .forEach((el) => (el.disabled = false));
  }
}
function loadProvider() {
  const p = state.settings.providers[$("provider").value];
  if (!p) return;
  adding = false;
  $("new-fields").hidden = true;
  $("api-key").value = "";
  $("api-key").placeholder = p.has_key
    ? "已保存，留空保留原 key"
    : "填写你的 API key";
  $("key-status").textContent = p.has_key ? "已保存在本机" : "尚未填写";
  $("model").value = p.model;
  $("base-url").value = p.base_url;
  document
    .querySelectorAll("[name=protocol]")
    .forEach((el) => (el.checked = p.protocols.includes(el.value)));
  updatePath();
}
function updatePath() {
  const p = state.settings.providers[$("provider").value];
  const c = state.clients.find((c) => c.id === selectedClient);
  $("path-provider").textContent = adding
    ? $("provider-name").value || "我的 API"
    : p.name;
  $("path-client").textContent = c.name;
  $("client-caption").textContent = "连接 " + c.name;
  $("client-hint").textContent = c.id.startsWith("workbuddy")
    ? "连接后重启 WorkBuddy，在任务中选择 custom-local 模型。"
    : c.installed
      ? "自动配置，连接后重启客户端即可使用。"
      : "尚未检测到安装；可先配置，再安装客户端。";
  document.querySelectorAll(".client").forEach((el) => {
    el.classList.toggle("selected", el.dataset.id === selectedClient);
    el.setAttribute("aria-pressed", String(el.dataset.id === selectedClient));
  });
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
  $("clients").replaceChildren();
  next.clients.forEach((c) => {
    const button = document.createElement("button");
    button.className = "client";
    button.dataset.id = c.id;
    button.disabled = working;
    const icon = document.createElement("span");
    icon.className = "client-icon";
    icon.textContent = icons[c.id];
    const labels = document.createElement("span");
    const name = document.createElement("span");
    name.className = "client-name";
    name.textContent = c.name;
    const status = document.createElement("span");
    status.className = "client-status";
    status.textContent = c.connected
      ? "已连接 · 可恢复"
      : c.installed
        ? "已检测到安装"
        : "可配置 · 未检测到安装";
    labels.append(name, status);
    button.append(icon, labels);
    button.onclick = () => {
      selectedClient = c.id;
      updatePath();
    };
    $("clients").append(button);
  });
  $("settings-location").textContent =
    "本地配置：" + next.settings_path.split(/[\\/]/).pop();
  $("settings-location").title = next.settings_path;
  loadProvider();
  if (
    first &&
    next.settings.providers[next.settings.selected_provider].has_key
  ) {
    result("已读取本地 API 配置。选择客户端即可连接，或先运行测试。");
  }
}
function form() {
  const id = adding ? $("provider-id").value.trim() : $("provider").value;
  if (!id) throw new Error("请填写 API 标识，例如 my-api。");
  return {
    provider: id,
    client: selectedClient,
    name: adding
      ? $("provider-name").value.trim()
      : state.settings.providers[id].name,
    api_key: $("api-key").value.trim(),
    base_url: $("base-url").value.trim(),
    model: $("model").value.trim(),
    protocols: [...document.querySelectorAll("[name=protocol]:checked")].map(
      (el) => el.value,
    ),
  };
}
async function save() {
  render(await api("save", form()));
}
function summarize(data, type) {
  if (data.message) return data.message;
  if (type === "probe") {
    const labels = {
      text: "文本回复",
      stream: "流式输出",
      "tool-roundtrip": "工具调用",
    };
    const failed = (data.results || []).filter(
      (item) => item.status !== "passed",
    );
    return data.passed
      ? "API 测试通过：文本回复、完整流式输出和工具调用往返均成功。"
      : "API 测试未全部通过：" +
          failed.map((item) => labels[item.case] || item.case).join("、") +
          "。请查看详情；遇到 429 请稍后重试，Auto 失败时可选择具体模型。";
  }
  if (data.status === "passed")
    return "客户端实测通过：已从实际客户端的回复中确认 ITERACONNECT_OK。";
  if (data.status === "manual-required")
    return "请在原客户端手动发送测试消息，确认回复。";
  if (data.status === "not-installed") return "未检测到客户端，请先安装。";
  return "客户端实测未通过，请查看详情。";
}
$("provider").onchange = loadProvider;
$("provider-name").oninput = updatePath;
$("add-provider").onclick = () => {
  adding = true;
  $("new-fields").hidden = false;
  $("advanced").open = true;
  $("api-key").value = "";
  $("key-status").textContent = "新 API";
  $("api-key").placeholder = "填写新的 API key";
  $("base-url").value = "";
  $("model").value = "";
  document
    .querySelectorAll("[name=protocol]")
    .forEach((el) => (el.checked = el.value === "chat"));
  updatePath();
  $("provider-id").focus();
};
$("save").onclick = () =>
  busy("正在保存本地设置…", async () => {
    await save();
    result("API 设置已保存到本机。", "success");
  });
$("reload").onclick = () =>
  busy("正在重新读取配置文件…", async () => {
    render(await api("reload", {}));
    result("已重新读取本地配置。", "success");
  });
$("models").onclick = () =>
  busy("正在获取当前 API 的模型列表…", async () => {
    await save();
    const data = await api("models", {});
    $("model-list").replaceChildren();
    data.models.forEach((id) => {
      const o = document.createElement("option");
      o.value = id;
      $("model-list").append(o);
    });
    result(
      "已获取 " + data.models.length + " 个模型，点击模型输入框可选择。",
      "success",
    );
  });
$("connect").onclick = () =>
  busy("正在备份并连接客户端…", async () => {
    await save();
    const data = await api("connect", {});
    render(await api("state"));
    result(data.message, "success");
  });
$("disconnect").onclick = () =>
  busy("正在检查并恢复原配置…", async () => {
    await save();
    const data = await api("disconnect", {});
    render(await api("state"));
    result(data.message, "success");
  });
$("export").onclick = () =>
  busy("正在生成配置片段…", async () => {
    await save();
    const data = await api("export", {});
    result(data.message);
    $("result-json").textContent = data.fragment;
    $("result-details").hidden = false;
    $("result-details").open = true;
  });
["probe", "smoke"].forEach(
  (type) =>
    ($(type).onclick = () =>
      busy(
        type === "probe"
          ? "正在测试 API 的文本、流式与工具调用，请稍候…"
          : "正在启动隔离的客户端测试，最长约 90 秒…",
        async () => {
          await save();
          const data = await api(type, {});
          const ok = data.passed || data.status === "passed";
          result(
            summarize(data, type),
            ok ? "success" : data.status === "manual-required" ? "" : "error",
            data,
          );
        },
      )),
);
api("state")
  .then(render)
  .catch((e) => {
    $("fatal").hidden = false;
    $("fatal").textContent = e.message;
    document.querySelectorAll("button").forEach((el) => (el.disabled = true));
  });
