# 客户端接入验收 · 2026-11-18

验证环境为 Linux x64，真实服务为 IteraCompute，模型为 `openai/gpt-6-luna`。四个 CLI 在临时用户目录中读取工作台适配器生成的配置，各发起一次单轮任务。仅当客户端报告成功并返回约定文本时计为通过。

| 客户端 | 工作台验证 | 本轮客户端结果 |
| --- | --- | --- |
| Codex CLI 0.156.1 | 连接、切换模型、保留已有 TOML 并恢复 | 真实 API 单轮通过，24.527 秒 |
| Claude Code 2.1.312 | 连接、切换模型、保留无关环境项并恢复 | 真实 API 单轮通过，11.253 秒 |
| WorkBuddy | 数组及对象配置、模型白名单、重名冲突、切换和恢复，生成的 URL 完成模拟请求 | 本机未安装桌面版，待在已登录的客户端选择模型并发送消息 |
| WorkBuddy AI | 国际版独立配置目录，白名单、切换和恢复，生成的 URL 完成模拟请求 | 本机未安装国际版，桌面会话待验收 |
| Visual Studio | 工作台生成指定服务商的端点、模型及本地令牌，模拟服务验证模型目录和聊天请求 | 需要 Windows 和支持自定义端点的 Visual Studio。模型管理器中的保存、选模、回复待验收 |
| VS Code 1.141.0 | Custom Endpoint 配置写入、切换、JSONC 注释保留、冲突拒绝、逐字节恢复，生成的端点完成模拟请求 | 真实 IDE 对模拟服务完成单轮回复并恢复，见下文 |
| OpenClaw 2026.10.2 | 连接、默认模型、允许列表和恢复 | 真实 API 单轮通过，15.986 秒 |
| Hermes 0.23.1 | 连接、提供方与 transport、切换和恢复 | 真实 API 单轮通过，33.345 秒 |

## VS Code 桌面验证

在 VS Code 1.141.0 的独立桌面窗口中，从磁盘加载机器上安装的 GitHub Copilot Chat 0.69.0。以空用户目录启动，由适配器写入默认 profile，验证模型出现在聊天栏，在本地聊天中发送固定单轮消息。模拟服务实际收到 Chat Completions POST，界面显示了完整预期回复；退出后成功恢复。运行方式见[桌面验证命令](testing.md#reproduce-the-client-setup-checks)。[VS Code 模拟后端回复截图](images/vscode-fixture.png)

首次测试时，IDE 选中了模型，直接写入提供方的 `apiKey` 字段却导致本地网关拒绝了请求。适配器改用 Custom Endpoint 支持的模型级 Authorization 请求头，内容为本地网关令牌。浏览器工作台和文件配置测试均未捕获这个问题，保留了桌面对话回归测试。

## 真实协议测试

每种协议做一次普通回复、一次完整 SSE，以及一次包含两次请求的工具调用往返。表中为用时（秒），九项均通过。四个客户端的单轮回复和服务商层的工具往返分别计数。

| 原生协议 | 文本 | 流式 | 工具往返 |
| --- | ---: | ---: | ---: |
| Chat Completions | 9.673 | 5.696 | 20.751 |
| Responses | 7.904 | 7.901 | 25.027 |
| Anthropic Messages | 5.998 | 10.119 | 18.981 |

## 复跑与取证

1. 按[开发测试说明](testing.md)安装开发依赖。运行 `python -m unittest discover -v`。本机启用固定版本 Magpie 和四个 CLI 后运行了 58 项测试。适配器测试会预置已有用户设置、连接、再次切换、恢复并比较原始内容。
2. 运行 `python -m tests.workbench_browser`。Chromium 对八个入口逐个点击，验证七个文件适配器的写入与恢复，以及 Visual Studio 引导的生成和字段复制。桌面宽度 1360 px，窄屏 390 px。测试使用本机模拟服务。[桌面工作台截图](images/client.jpg)
3. 在私有 TOML 中选择测试服务商、模型并填入专用凭据。按测试说明运行 `scripts/check_live.py`，可用 `--clients` 或 `--protocols` 单独复跑某一项。将状态、版本、日期和用时记入验收记录。
4. 桌面验收时，在目标软件的新会话选择刚接入的模型，发送 `Reply with exactly ITERACONNECT_OK.` 并核对回复。WorkBuddy 两个版本在任务菜单选择工作台显示的完整 `custom-local:` 模型。VS Code 在本地聊天中选择 Agent Connect 模型，Visual Studio 在 Copilot Chat 的模型管理器保存端点并选中模型。
5. 在一次性工作目录中验证一次创建并读取小文件的工具流程。退出后恢复配置，或在 Visual Studio 模型管理器中移除测试端点。分别记录回复、工具、恢复结果。截图只保留软件版本、模型选择和测试结果。

接入方式参考了 CC Switch 的客户端选择与服务商切换流程。WorkBuddy 已启用非空白名单时需要同步更新模型 ID，空白名单表示显示全部。微软两个 IDE 分别使用模型管理器和用户配置文件。[CC Switch 工作台](https://github.com/farion1231/cc-switch) · [WorkBuddy 白名单处理](https://github.com/farion1231/cc-switch/blob/09acca04941a359096bb16ea4fa4073c5e2c46e5/src-tauri/src/workbuddy_config.rs) · [Visual Studio 模型管理](https://learn.microsoft.com/en-us/visualstudio/ide/copilot-select-add-models?view=visualstudio) · [VS Code Custom Endpoint](https://code.visualstudio.com/docs/agent-customization/language-models)
