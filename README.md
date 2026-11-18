# Agent Connect

**选择 API → 选择客户端 → 点击连接。**

[**中文**](README.md) | [**English**](README.en.md)

一个在本机运行的轻量连接工具，让 Claude Code、Codex、WorkBuddy、WorkBuddy AI、Visual Studio、VS Code、OpenClaw 和 Hermes 使用你选择的模型 API。
默认提供 IteraCompute，也可以保存和切换其他兼容服务。界面、配置管理和转发均为独立实现，没有复制 CC Switch 或 Magpie 的应用代码。
正常使用只需要 **Python 3.11+**；无需 pip install、Node.js、CC Switch 或 Magpie。

![Agent Connect 本地工作台](docs/images/client.jpg)

本 README 与英文版包含相同的完整使用流程。客户端界面目前使用中文；英文版附有按钮对照表。

**导航：** [快速开始](#快速开始) · [填写配置文件](#填写配置文件) · [其他-api](#接入其他-api) · [客户端操作](#连接不同的客户端) · [测试](#确认接入是否成功) · [恢复](#切换与恢复配置) · [常见问题](#常见问题) · [开源治理](#开发与开源治理)

## 快速开始

### 1. 准备运行环境

- 安装 Python **3.11 或更新版本**，并确保终端能运行它。
- 安装需要连接的客户端。未安装时也可先生成配置，但“连接成功”不代表已经完成真实推理。
- 准备一个有目标模型访问权限的 API key。测试可能产生 API 用量。

检查 Python 版本：

```bash
# macOS / Linux
python3 --version
```

```powershell
# Windows PowerShell
py -3 --version
```

Windows 没有 `py` 启动器时，可使用 `python --version` 和 `python start.py`，前提是该 Python 为 3.11+。

### 2. 下载并启动

首次发布的代码已通过 [PR #1](https://github.com/IteraCompute/agent-connect/pull/1) 合并到默认的 `main` 分支。下载并启动：

```bash
git clone https://github.com/IteraCompute/agent-connect.git
cd agent-connect
python3 start.py
```

Windows 将最后一行换成 `py -3 start.py`。不使用 Git 时，可下载 [`main` 分支 ZIP](https://github.com/IteraCompute/agent-connect/archive/refs/heads/main.zip)，解压后进入包含 `start.py` 的目录。

| 系统 | 推荐启动方式 | 可选启动方式 |
| --- | --- | --- |
| Windows | 在项目目录执行 `py -3 start.py` | 双击 `Start.bat` |
| macOS | 在项目目录执行 `python3 start.py` | 双击 `Start.command`；系统不允许执行时使用终端方式 |
| Linux | 在项目目录执行 `python3 start.py` | 使用你自己的终端启动器 |

启动后会打开本地工作台。首次运行还会在项目目录生成 `agent-connect.local.toml`。
如果浏览器没有打开，请复制终端打印的**完整地址**，包括 `#` 后的本地管理令牌；只打开 `http://127.0.0.1:18424/` 的新浏览器会话可能无法管理配置。

### 3. 填写 API 与模型

1. 保持默认的 **IteraCompute**，在 **API key** 输入框填写你的 key。
2. 模型默认是验收时通过的 `openai/gpt-6-luna`。也可点击 **获取模型**，再在输入框选择或填写完整模型 ID。
3. 可点击 **保存 API 设置**。连接、导出或测试时也会自动保存。

“获取模型”只请求目录，不进行生成、不保存草稿，也不会替换当前转发使用的密钥。
模型是否可用，以你的账号权限和当前 API 返回为准；历史验收记录见[测试状态](docs/acceptance.md)。

### 4. 选择客户端并连接

1. 点击需要使用的客户端卡片，例如 **Claude Code**。
2. 检查“本次连接”的 API、模型与协议。显示 **协议匹配** 后，点击 **连接 Claude Code** 等对应按钮。
3. 对标有“自动写入配置”的软件，Agent Connect 会备份原配置，并写入这个客户端的用户配置。完全退出并重新启动对应客户端，再新建会话。
4. Visual Studio 选择 **获取 Visual Studio 接入信息**，在 IDE 内添加模型。VS Code 选择 **连接 VS Code**，重新加载后在聊天中选模型。WorkBuddy / WorkBuddy AI 需要在任务的模型菜单中选择新增的 `custom-local` 模型，详见[客户端操作](#连接不同的客户端)。

使用客户端期间，请保持 Agent Connect 的启动终端运行。关闭浏览器标签页不会停止服务；在启动终端按 `Ctrl+C` 才会停止。
下次执行同一个启动命令即可读取已保存的设置。仅重新启动 Agent Connect、地址和模型都没有变化时，无需重复填写 key。

## 填写配置文件

也可以完全通过文件填写 key。推荐先启动一次，再编辑已经生成的 `agent-connect.local.toml`：

```toml
selected_provider = "iteracompute"
client = "claude"

[providers.iteracompute]
name = "IteraCompute"
api_key = "" # 在引号内填写你的 key
base_url = "https://api.iteracompute.com"
model = "openai/gpt-6-luna"
protocols = ["chat", "responses", "anthropic"]
```

这是一份完整示例。通常只需要填写 `api_key`，其余值保留默认。
保存文件后，在界面点击 **重新读取**；如果服务尚未启动，直接启动即可。
也可使用空白模板 [config.example.toml](config.example.toml)，但不要覆盖已经填写过 key 的本地文件。

| 字段 | 用途 |
| --- | --- |
| `selected_provider` | 本次使用的 API 标识，须与某个 `[providers.<标识>]` 一致 |
| `client` | `claude`、`codex`、`workbuddy`、`workbuddy-ai`、`visual-studio`、`vscode`、`openclaw` 或 `hermes` |
| `name` | 界面显示名称 |
| `api_key` | 此服务商的凭据；不会返回给网页或写入客户端配置 |
| `base_url` | API 根地址或 OpenAI 兼容的 `/v1` 地址 |
| `model` | 完整模型 ID；保留服务商提供的 `/` 等字符 |
| `protocols` | API 实际提供的原生协议，不能通过勾选增加服务端能力 |

本地文件已被 Git 忽略，POSIX 系统使用仅当前用户可读写的权限；Windows 请将项目保存在自己的用户目录。
界面不回显已保存的 key，输入框留空表示保留它；要删除 key，请在文件中设为 `api_key = ""` 后重新读取。
简化客户端只读取此文件中的 key，不会使用终端里已有的其他供应商 key。
请勿将填过 key 的文件、本地管理地址或导出的网关令牌公开到 Issue、PR 或截图中。

如果你编辑文件后网页提示“本地配置文件已被修改”，点击 **重新读取** 后再操作。程序会停止保存，避免旧页面覆盖刚填好的 key。

## 接入其他 API

### 在工作台添加

1. 点击 **添加 API**。
2. 输入唯一标识，例如 `my-api`。标识以小写字母开头，只含小写字母、数字和短横线，最多 48 个字符。
3. 输入显示名称、此 API 的 key，并在 **地址与协议** 中填写 API 地址。
4. 勾选该 API **实际支持**的协议，再点击 **获取模型**，或直接输入模型 ID。
5. 选择客户端后点击连接，或先保存，以后从 API 服务商菜单切换。

新增服务商时 key 为空，不会沿用另一家的凭据。点击 **取消添加** 会丢弃新增草稿，回到原服务商设置。
模型目录接口不存在时，可以直接填写供应商提供的模型 ID。

### 地址与协议如何填写

| API 类型 | 地址示例 | 勾选的协议 | 可直接接入的客户端 |
| --- | --- | --- | --- |
| OpenAI Chat 兼容 | `https://api.example.com/v1` | `chat` | WorkBuddy、WorkBuddy AI、VS Code、Visual Studio、OpenClaw、Hermes |
| OpenAI Responses 兼容 | `https://api.example.com/v1` | `responses` | Codex CLI、VS Code |
| Anthropic Messages 兼容 | `https://api.example.com` | `anthropic` | Claude Code |
| 同时提供多个原生协议 | 供应商的 API 基地址 | 只勾选实际提供的协议 | 对应协议的客户端 |
| 本地 OpenAI 兼容服务 | `http://127.0.0.1:你的端口/v1` | 按服务能力勾选 | 对应协议的客户端 |

上表使用的是基地址，**不要**填写 `/chat/completions`、`/responses` 或 `/v1/messages` 等完整推理路径。
公网地址使用 HTTPS；本机回环服务允许 HTTP。对于无需鉴权的本地服务，仍需填一个非空占位 key，例如 `local`。

不同协议位于不同路径时，可在本地 TOML 中设置 `endpoints`。例如在已有的服务商表后追加：

```toml
[providers.my-api.endpoints]
chat = "https://api.example.com/openai/v1"
responses = "https://api.example.com/openai/v1"
anthropic = "https://api.example.com/anthropic"
```

前提是已经存在 `[providers.my-api]`，且它的 `protocols` 包含这些协议。完整规则见[配置说明](docs/configuration.md)。

本地转发保留原生协议，不会自动把 Chat 转换为 Responses 或 Messages。
只有 Chat 的服务不能直接供 Claude Code 或 Codex 使用；需要转换时，参阅[可选 Magpie 高级入口](docs/advanced.md)。
配置支持 Gemini 基地址，但当前八个客户端入口使用的是 Chat、Responses 或 Messages；Gemini 专用接入见[覆盖范围](docs/coverage.md)。

## 连接不同的客户端

工作台提供以下接入方式。无需额外向客户端填写供应商 key；客户端使用本地网关令牌，由 Agent Connect 转发请求。

| 客户端 | 所需原生协议 | 配置位置或操作入口 |
| --- | --- | --- |
| Claude Code | Anthropic Messages | `~/.claude/settings.json` |
| Codex CLI | OpenAI Responses | `~/.codex/config.toml` |
| WorkBuddy | OpenAI Chat Completions | `~/.workbuddy/models.json` |
| WorkBuddy AI | OpenAI Chat Completions | `~/.workbuddy-ai/models.json` |
| Visual Studio（Windows） | OpenAI Chat Completions | Copilot Chat → 管理模型 → 添加模型 |
| VS Code（桌面稳定版） | 优先 OpenAI Responses，也支持 Chat Completions | 用户配置目录下的 `chatLanguageModels.json` |
| OpenClaw | OpenAI Chat Completions | `~/.openclaw/openclaw.json` |
| Hermes | OpenAI Chat Completions | `~/.hermes/config.yaml` |

`~` 表示当前用户主目录，Windows 通常为 `C:\Users\你的用户名`。设置了客户端配置目录环境变量时，实际位置会随之变化，见[文件位置](#文件位置与启动选项)。

### Claude Code

选择 **Claude Code** 并连接，然后退出旧进程，在新终端启动新的 `claude` 会话。
适配器配置 Messages 地址、模型和本地鉴权，并保留不相关设置。项目配置、环境变量或企业策略仍可能覆盖用户配置。
确认接入可先使用工作台的 **客户端实测**，或在新会话发送下方的固定测试消息。

### Codex

选择 **Codex CLI** 并连接，再重新启动 `codex`。适配器配置名为 `iteraconnect` 的 Responses 提供方及所选模型。
如果用户文件中已经有来源不明的同名提供方，程序会报错并保留原文件；请改名后重试，或使用 **导出配置** 手动合并。
这里只验证了 Codex CLI；不把 CLI 测试结果当作其他桌面、IDE 或云端运行方式的验收结果。

### WorkBuddy / WorkBuddy AI

选择与安装版本对应的卡片，连接并重启应用，然后新建任务。
在任务模型菜单选择 `custom-local:iteracompute/模型ID`；自定义服务商时将 `iteracompute` 替换为你的 API 标识。
模型显示名称包含 `Agent Connect · 模型ID`。现有模型会保留，新增配置的 `vendor` 为 `iteraconnect`。

工作台会提示在原应用手动验证，因为当前没有自动执行桌面应用推理的测试。仅配置写入成功不算真实接入通过。

### Visual Studio（Windows）

打开 **获取 Visual Studio 接入信息**，逐项复制地址、模型 ID 和本地网关令牌。在 Visual Studio 2026 18.10 或更高版本的 Copilot Chat 中打开“管理模型”，添加 Custom Endpoint 或支持自定义地址的 OpenAI，选择 Completions 格式。在 Agent 模式开启新对话并选择该模型。需要移除时，在同一菜单删除端点。[微软模型管理指南](https://learn.microsoft.com/en-us/visualstudio/ide/copilot-select-add-models?view=visualstudio)

### VS Code

在与 Agent Connect 同一台设备上的 VS Code 桌面稳定版使用 Copilot Chat 的 Custom Endpoint。服务商声明支持 Responses 时工作台优先使用它，只提供 Chat 时自动配置 Chat Completions。点击 **连接 VS Code**，重新加载窗口，在本地聊天的模型菜单中选择 Agent Connect 下的目标模型。默认写入默认配置文件（profile）。使用命名配置文件或便携版时，把 `ITERACONNECT_VSCODE_USER_DIR` 指向该配置文件中存放 `chatLanguageModels.json` 的目录，再启动工作台。[VS Code 模型设置](https://code.visualstudio.com/docs/agent-customization/language-models)

### OpenClaw

选择 **OpenClaw** 并连接，再按原来的运行方式重启相关进程、开始新会话。
适配器更新提供方和默认模型，并将接入模型加入已有的模型允许列表；不会替你开启消息渠道投递。
工作台实测会使用独立临时配置运行本地单轮测试，不复用日常会话。

### Hermes

选择 **Hermes** 并连接，再重新启动 Hermes、新建会话。
适配器使用 `custom:iteraconnect` 提供方和明确的 Chat transport，保留其他无关设置。
自动 **客户端实测** 基于 Hermes 0.23.1 的 JSONL 输出；旧版本可以在原客户端手动测试。
复杂 YAML 会明确报错，原文件不会被重写；此时使用导出片段或高级适配器。

## 确认接入是否成功

连接不是测试的前置强制步骤；可以先测试 API，再连接客户端。**测试不会自动在启动时运行。**

| 操作 | 验证内容 | 用量与边界 |
| --- | --- | --- |
| **获取模型** | 供应商模型目录 | 一次目录请求，不进行生成，不保存草稿 |
| **测试 API** | 所选客户端协议的文本、完整 SSE、工具调用与结果回传 | 最多 4 次生成请求，每次输出预算 256 token |
| **客户端实测** | 启动已安装的 Claude Code / Codex / OpenClaw / Hermes，检查实际回复 | 会产生 API 用量；临时配置、独立目录，不复制日常登录和聊天 |
| **查看实测步骤**（WorkBuddy 两版、VS Code、Visual Studio） | 原应用内发送消息与工具任务 | 需手动验收，工作台会明确提示 |

推荐顺序：

1. 选定 API、模型、客户端，点击 **测试 API**，检查三张结果卡是否全部通过。
2. 对支持自动测试的已安装客户端，点击 **客户端实测**。
3. 点击连接，重启原客户端，在新会话发送：

   ```text
   Reply with exactly ITERACONNECT_OK.
   ```

4. 在可丢弃的测试目录里，再让客户端创建并读取一个小文件，检查其真实工具工作流。

API 工具测试只回传固定字符串，不执行模型生成的命令。客户端单轮回复通过，不代表它的完整工具循环、长会话、图像、权限或异常恢复均已验收。

2026-11-18 逐个客户端的结果、测试环境与复跑命令见[本轮验收记录](docs/client-setup-acceptance.md)。

![文本、流式与工具调用的独立结果卡](docs/images/test-passed.jpg)

此结果卡截图使用**本地模拟后端**展示界面。真实 IteraCompute 验收发生于 2026-11-16：
`openai/gpt-6-luna` 的三个原生协议及四个真实 CLI 通过了记录中的检查；WorkBuddy 桌面推理仍待手动验收。
`Auto` 曾返回 400/429，另一次 Haiku 工具测试曾返回 502，这些失败均保留在[验收记录](docs/acceptance.md)，不会被模拟测试结果覆盖。

[GitHub CI](https://github.com/IteraCompute/agent-connect/actions/runs/44015209371) 已通过 Ubuntu、macOS、Windows × Python 3.11 / 3.14 的单元与模拟后端测试，以及构建、Magpie 与必需检查。跨平台 CI 不替代真实客户端的各平台验收。

### 读懂界面状态

| 状态 | 含义 |
| --- | --- |
| 有未保存更改 | 修改了 API、模型、协议或客户端；连接、导出和测试会自动保存 |
| 协议匹配 / 需要配置 | 只检查声明的协议；缺少协议时连接与测试不可用，可点“检查协议”定位 |
| 已检测到安装 | 在 PATH 中找到启动命令。仅找到目录时单独显示“发现配置目录” |
| 已配置 · 可恢复 | 存在原配置备份，不等于当前模型已通过推理测试 |
| API 测试通过 | 三项协议检查通过；报告默认收起，可展开查看脱敏详情 |
| 客户端实测通过 | 从真实客户端输出中确认了预期回复 |

修改 API、模型或客户端后，旧测试结果会清除。客户端卡片支持 Tab、方向键、Home / End；窄屏会自动堆叠显示。

## 切换与恢复配置

**换模型或服务商：** 选择另一个 API / 模型，保持目标客户端卡片选中，再点击连接，随后重启客户端。
只保存 API 设置不会改写客户端文件。切换一个客户端不会自动配置其他客户端；请逐个连接。

已连接的客户端仍使用它最近一次连接时写入的服务商和模型；修改同一服务商的 key / 地址会影响本地转发。
不要删除仍被客户端使用的服务商配置。使用多个配置管理器前，先恢复原配置，避免相互覆盖。

**恢复：** 对自动写入的软件，选中目标客户端，点击 **恢复原配置**，再重启客户端。
第一次连接前会保存原始内容；重复连接仍保留这份原始备份。原文件原本不存在时，恢复会移除由本工具创建的文件。

如果客户端或其他工具在连接后改写了该文件，自动恢复会停止，避免覆盖后续修改。请对照 `native-backups` 中的备份手动合并；不要为了恢复而直接删除整个客户端配置目录。
支持标准 JSON、Codex TOML 和 Hermes 常见缩进 YAML / JSON。JSON5 或复杂结构会报错并保留原文件。

**手动导出：** 点击 **导出配置**，展开片段并点击 **复制配置**，手动合并到对应文件。
导出不会写入目标客户端，也不算“已连接”。片段含本地网关令牌，请仅在本机使用。

## 文件位置与启动选项

| 文件 / 端口 | 默认值 | 作用 |
| --- | --- | --- |
| 私密 API 设置 | 项目内 `agent-connect.local.toml` | 保存 API key、服务商、模型与上次选择 |
| 状态目录 | `~/.config/iteraconnect` | 本地网关 key、备份等 |
| 原配置备份 | 状态目录内 `native-backups` | 每个客户端的原始内容与冲突检测信息 |
| 本地工作台 | `127.0.0.1:18424` | 需本次启动管理令牌，检查 Host / Origin |
| 推理转发 | `127.0.0.1:18423` | 客户端连接的本地 API |

`ITERACONNECT_HOME` 覆盖状态目录；否则状态目录遵循 `XDG_CONFIG_HOME`。
客户端适配器遵循 `CLAUDE_CONFIG_DIR`、`CODEX_HOME`、`WORKBUDDY_CONFIG_DIR`、`WORKBUDDY_AI_CONFIG_DIR`、`OPENCLAW_STATE_DIR` / `OPENCLAW_CONFIG_PATH` 和 `HERMES_HOME`。

```bash
# 修改端口；Windows 将 python3 换成 py -3
python3 start.py --port 18434 --relay-port 18433

# 不自动打开浏览器，使用终端显示的完整地址
python3 start.py --no-browser

# 查看可用启动选项
python3 start.py --help
```

更换转发端口后，必须重新连接对应客户端。使用同一组端口时只启动一个实例。
需要把私密配置保存在其他目录时，在源码目录执行：

```bash
python3 -m pip install .
itera-connect app --settings /absolute/path/to/private.toml
```

这里的 `pip install .` 是从当前源码安装，不代表已发布到 PyPI。简化客户端 TOML 与高级入口 JSON 配置相互独立。
更新源码可在项目目录执行 `git pull --ff-only`，然后重启 Agent Connect；已填写的本地 TOML 被 Git 忽略，更新时请保留它。

## 常见问题

| 现象 | 检查与处理 |
| --- | --- |
| `python3` / `py` 不存在，或提示版本过低 | 安装 Python 3.11+，重新打开终端；Windows 可检查 `python --version` |
| 找不到 `start.py` | 确认从默认的 `main` 分支下载，并进入解压或克隆后包含该文件的目录 |
| 页面打不开、地址占用 | 停止旧实例，或使用上面的两个端口参数；浏览器未打开时复制终端完整地址 |
| 本地页面提示未授权 | 使用本次启动打印的完整地址；重启服务后管理令牌会变化 |
| API 返回 401 / 403 | 核对 key、账号和模型权限；修改文件后点“重新读取” |
| 429 / 502 / 超时 | 查看脱敏详情，稍后重试或选择其他已授权模型；具体模型通常比 `Auto` 更容易排查 |
| 获取模型失败 | 核对 API 基地址；供应商可能没有目录接口，可直接输入模型 ID |
| 连接或测试按钮不可用 | 检查所选客户端需要的协议；不要只为启用按钮而勾选服务并不支持的协议 |
| 配置成功但客户端仍用旧模型 | 完全退出旧进程并新建会话，检查项目配置、环境变量、企业策略以及 WorkBuddy 的任务模型选择 |
| 提示未安装，但实际已安装 | 检查启动 Agent Connect 的终端能否找到客户端命令，以及实际配置目录；也可先连接后在原应用手测 |
| 修改文件后无法保存 | 先点“重新读取”，再操作，避免覆盖外部修改 |
| 恢复被拒绝 / JSON5 或 YAML 报错 | 原文件保留；对照备份手动合并，或使用高级适配器 |
| 关闭工作台后客户端报连接失败 | 保持启动终端运行；如果已停止，重新启动 Agent Connect |

供应商原始错误正文和任意客户端日志不会直接返回，避免泄露凭据或私密上下文。
当前工作台只服务本机；远程共享、协议转换和其他上游选项见[高级指南](docs/advanced.md)。

## 开发与开源治理

```bash
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell：.venv\Scripts\Activate.ps1
python -m pip install -e . -r requirements-dev.txt
python -m unittest discover -v
ruff check .
ruff format --check .
python -m build
```

运行时只有 Python 标准库；上面的 Ruff / build 是开发依赖。网页源码位于 `src/iteraconnect/web`，原生适配器位于 `native.py`，转发位于 `gateway.py`。
[测试指南](docs/testing.md)说明模拟后端、真实 CLI、真实 API 验收的区别及可选命令。

MIT 开源，欢迎 [Issues](https://github.com/IteraCompute/agent-connect/issues)、[Discussions](https://github.com/IteraCompute/agent-connect/discussions) 和 PR。
公开讨论请提供版本、协议、模型 ID 与脱敏复现步骤。社区可以提交建议与代码，合并由管理员审核。
`main` 的审核、CI、首次 CODEOWNERS 设置与当前修复进度见[治理记录](docs/governance.md)。

需要 Magpie 协议转换、更多客户端、订阅登录、MCP、skills 或 CC Switch 导入时，使用[高级入口](docs/advanced.md)与[覆盖矩阵](docs/coverage.md)。
可选上游组件的版本、来源和许可证见 [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES) 与锁文件；它们遵循各自的存储和授权方式。
