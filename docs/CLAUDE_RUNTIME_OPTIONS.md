# Claude 运行接入澄清：Windows SSH 开发不等于 Pi 已有 Claude

日期：2026-10-30（America/Los_Angeles）。本说明纠正 STABILIZATION_REVIEW §4.1 的环境假设。用户明确：当前是 Windows Claude 通过 SSH 操作 Pi，尚未证明 Pi 本机安装并登录了 Claude Code。不要把“Pi Claude 最终编辑”写成已存在、可生产调用的能力。

## 已知与尚待验证

- Windows Claude 是开发入口，不应成为每日任务必须在线的依赖。Windows 登录不会自动赋予 Pi 本机 Claude 登录状态。
- Claude Code 官方支持 Linux ARM64，需核对 Pi 的实际 64 位系统、内存和网络环境。
- 官方支持以 claude.ai 订阅账号登录 Claude Code；也支持 `claude -p` 的非交互执行。2026-10-30 查阅的官方帮助说明，订阅登录时 Agent SDK / `claude -p` 仍使用订阅限额；使用 Console API key 则属于 API 路径。不能把两个路径的额度混为一谈。
- Pi 上的正式登录、无人值守调用、额度、凭据刷新及重启后运行环境均未在本轮验证。

## 推荐的最小接入：直接调用 Pi 本机官方 CLI

让 Windows Claude 通过 SSH 协助检查/准备 Pi 上的官方 Claude Code。首次 claude.ai 登录需 owner 在浏览器完成授权：官方说明允许在浏览器没有自动打开时复制登录 URL，必要时将登录验证码输入远程终端。不要把 token/验证码提交 Git 或放入模型材料。

随后 Python 流水线可分别调用：

- 现有隔离 Hermes / MiMo：候选、初稿和第一轮检查。
- Pi 本机官方 Claude Code CLI adapter：最终编辑及必要的正常历史题材起草/审稿。

不要求 Hermes 把 Claude 当作它的 provider，也不要求 Windows 电脑持续开机。Pi 运行的是官方客户端，推理仍使用云端服务；正式 systemd 环境需有相同的账户身份、配置目录和绝对 executable 路径。

本机连接 smoke test 的形式为：

```bash
claude auth login
claude -p "Reply with OK only." --output-format json
```

这些命令必须在 Pi 的 shell 中执行，而不是只在 Windows 端执行。此处只是说明步骤，不代表本轮已经安装、登录或运行。

adapter 需要进程组超时、输出与调用预算、严格结构校验、最终正文/证据 hash、模型和 CLI 版本记录。认证失效或额度用尽进入待处理/告警，使用已审库存，不循环重试、不静默放宽准入。订阅与 Windows 使用共享相应账号限额，不是无限使用保证。

验证工具、MCP、hooks、记忆与目录上下文的加载范围，不照搬 Hermes 的旧 flags。特别注意：当前官方文档说明 `--bare` 不读取订阅 OAuth 登录，要求 API 认证；不能为了隔离直接加 bare 后又声称仍使用订阅。根据安装版本选择可用的限制方式并测试。不要自动升级现有 Hermes 或改其全局认证。

## Hermes 也已有一种可选接入，但当前 Pi 版本不能直接假定可用

NousResearch 的官方插件目录目前有实验性 `claude-subscription-directsdk`，通过未修改的官方 Claude Code CLI 使用 Pro/Max 订阅；它不是把 Windows 会话凭据自动变成 Pi 的服务。

2026-10-30 查阅的插件 README 要求 Hermes **0.21.4+**，或指定 revision 后的 main，并要求本机官方 Claude CLI 已安装和登录。项目先前报告的 Pi Hermes 为 **0.14.0**，因此不能未经验证直接套用。插件仍保留 Hermes 的 agent loop/工具和权限管理；不能假定安装插件就自动是无工具的事实编辑器。

本项目已有 Hermes 内部 API 隔离调用器，并共享新闻与 gateway，升级是独立工作，需回归其兼容性。为只增加一个编辑器，先尝试独立 CLI adapter 更小。这里不是禁止以后使用插件，而是不把生产 Hermes 升级作为默认前置条件。

## 下一步验证范围

1. Windows Claude SSH 只读检查 Pi 的架构、系统、`command -v claude`、版本和认证状态。状态输出脱敏，不输出凭据。
2. 若尚未安装，准备官方安装步骤并按用户授权执行；首次登录由 owner 自己在浏览器完成。不能假称 Windows 的登录已自动继承。
3. 从 Pi 做中性非交互 smoke test，再在接近 systemd 的非交互环境中测试，确认使用订阅而非意外 API key 路径。
4. 测试工具/上下文限制与故障行为，再用 ancient 和 modern 各一份证据包验证最终编辑和记录导入。
5. 以上通过才选择该路径作为自动最终编辑；若不愿在 Pi 登录或实际不适用，再单独比较其他可用模型 API 的费用与质量，不静默增加付费依赖。

## 官方来源（查阅于 2026-10-30）

- https://code.claude.com/docs/en/setup
- https://code.claude.com/docs/en/authentication
- https://code.claude.com/docs/en/headless
- https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan
- https://hermes-agent.nousresearch.com/docs/plugins/claude-subscription-directsdk
