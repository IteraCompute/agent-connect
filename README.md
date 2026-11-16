# IteraCompute Agent Connect

[English](README.en.md) · [接入与测试](docs/testing.md) · [覆盖范围](docs/coverage.md) · [贡献](CONTRIBUTING.md)

把 **CC Switch 的供应商切换、Magpie 的协议转换和客户端适配**组合在一起，默认连接
IteraCompute，也可以选择任意兼容 API、Magpie 原生供应商或社区插件。

这是独立的开源组合层。CC Switch 和 Magpie 保持独立运行，保留各自的界面与功能；
本项目提供统一的启动、供应商配置、导入与验收命令。没有把两套桌面应用合并为一个新 UI。

```text
Claude Code / Codex / WorkBuddy / OpenClaw / Hermes / 其他客户端
                         │
           CC Switch 配置切换 / Magpie 客户端适配
                         │
               Magpie 本机协议转换（可选）
                         │
            Agent Connect 本机转发 :18423
                         │
       IteraCompute（默认） / 你选择的其他供应商 API
```

## 开始使用

需要 Python 3.11+。运行时没有 Python 第三方依赖。开发中的实现可从 PR 的分支安装，
管理员审核合并后从 `main` 安装。

```bash
git clone https://github.com/IteraCompute/agent-connect.git
cd agent-connect
# 初始 PR 合并前：git switch feat/agent-connect
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
itera-connect init
itera-connect install-magpie
read -rsp 'IteraCompute API key: ' ITERACOMPUTE_API_KEY
export ITERACOMPUTE_API_KEY
itera-connect up --web
```

Magpie 下载版本及 SHA-256 固定在 [上游锁文件](src/iteraconnect/upstreams.lock.json)，
支持 Linux、macOS、Windows 的 x64/ARM64 CLI。Windows 用 `.venv\Scripts\Activate.ps1` 激活，
通过系统环境变量或密钥管理器设置 key。CC Switch 从[官方发布页](https://github.com/farion1231/cc-switch/releases)安装。

默认 OpenAI Base URL 是 `https://api.iteracompute.com/v1`，Anthropic Base URL 是
`https://api.iteracompute.com`。模型从供应商当前目录读取，默认模型为 `Auto`；
真实可用性及工具支持以 key 权限和验收结果为准。

在另一个终端连接客户端：

```bash
itera-connect connect claude
itera-connect connect codex
itera-connect connect workbuddy
itera-connect connect openclaw
itera-connect connect hermes
```

`connect` 使用 Magpie 的原生配置写入和恢复机制，会修改对应客户端配置。WorkBuddy
连接后需要重启，在新任务的模型列表选择 `iteraconnect-iteracompute/…`。
`disconnect <客户端>` 恢复之前的供应商。操作前请备份自己的配置；多个配置管理器不要同时切换同一个客户端。

只想单次启动、不改全局配置：

```bash
itera-connect run claude --via magpie -- -p 'Reply only OK'
itera-connect run codex --via magpie -- exec --skip-git-repo-check 'Reply only OK'
```

也支持 `--via gateway` 原生协议转发和 `--via direct` 直接访问供应商。

## CC Switch 导入

```bash
itera-connect cc-link claude
itera-connect cc-link codex
itera-connect cc-link openclaw
itera-connect cc-link hermes
# 供应商只有 Chat 时，先由 Magpie 转换为 Codex 所需的 Responses
itera-connect cc-link codex --via magpie
```

把生成的 `ccswitch://` 链接交给已安装的 CC Switch，检查后导入并选择该供应商。
链接只携带本机网关凭据，不携带供应商密钥，仍应作为本机凭据保管。
CC Switch 上游暂不支持 WorkBuddy 的供应商深链导入，本项目使用 Magpie 的 WorkBuddy 适配器。

## 选择其他 API

```bash
itera-connect provider add my-relay --name 'My Relay' --key-env MY_RELAY_API_KEY \
  --model my-model --chat https://relay.example/v1
itera-connect provider use my-relay
# 设置 MY_RELAY_API_KEY，重启 up，再连接客户端
itera-connect connect codex --provider my-relay --model my-model
```

支持 `--chat`、`--responses`、`--anthropic`、`--gemini` 原生端点。只填服务实际支持的协议；
Magpie 会转换其他客户端所需的协议。供应商 key 只留在转发进程的环境中。

上游的其他供应商、订阅登录、路由组、MCP、skills 等选项保留原生入口：

```bash
itera-connect magpie -- presets
itera-connect magpie -- ls
itera-connect magpie -- tui
itera-connect cc-switch
```

通过 Magpie 自己添加的供应商按其原生规则存储凭据，并直接由 Magpie 访问。
详情见[配置说明](docs/configuration.md)和[覆盖范围](docs/coverage.md)。

## 验收与开源治理

```bash
itera-connect doctor
itera-connect probe --via gateway --out reports/api-contract.json
itera-connect probe --via magpie --protocol chat --protocol responses --protocol anthropic
itera-connect smoke claude codex openclaw --via magpie --out reports/native-clients.json
```

`probe` 检查文本、SSE 完整结束、工具调用与结果回传；`smoke` 在临时 HOME 中启动真实客户端。
配置验证、模拟后端验证与真实 API 验证分别记录，详见[当前验收状态](docs/acceptance.md)。
测试会产生少量 API 用量；收到专用测试 key 后再完成真实 API 验收。

MIT 开源，欢迎 Issues、Discussions 与 PR。`main` 要求管理员 CODEOWNER 审核、CI 通过、
过期批准失效、最新修改获得批准，规则同样约束管理员。初始实现通过 PR 提交，不自动合并。
