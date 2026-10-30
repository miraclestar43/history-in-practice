# 专用发信地址：待配置说明

此文件不包含真实收件人或凭据。

建议使用 Resend，验证子域 `read.starhub.vip` 后，以 `每日一鉴 <history@read.starhub.vip>` 为 From。这是专用发信身份，不要求先注册 Gmail 或购买完整收件邮箱。

截至 2026-10-30，Resend 官方免费发信配额为每月 3,000 封、每日 100 封；两人每日一封约每月 60–62 封，预计在配额内。额度和条款以开户时官方页面为准；不得自动启用付费、超额计费或非必要功能。

## 用户明早完成

1. 在 https://resend.com/ 注册账户，可使用已有邮箱注册，不必创建新的 Google 邮箱。
2. 添加发信子域 `read.starhub.vip`，按 Resend 实际返回的记录在 Cloudflare DNS 完成验证。记录名称和值由服务返回，不猜写，不替换根域现有邮件或网站记录。
3. 创建限定发送用途、能限定域时限定到该子域的 key，直接保存在 Pi 私密环境文件；不贴进 GitHub、网页前端或 LLM prompt。
4. 核实账号允许向两位实际收件人发送。测试域的仅发给自己限制不能代表正式域已就绪。
5. 集成时验证 Gmail 与 QQ 邮箱均收到、SPF/DKIM、垃圾箱和中英文排版；不保证两家投递表现相同。

若更希望专用 Gmail，可另选 Gmail SMTP，但需新账号及适用授权。当前只保留简单 SMTP 接口，不同时实现两家服务。

## 私密配置示意（全为占位符）

```dotenv
SMTP_HOST=smtp.resend.com
SMTP_PORT=465
SMTP_SECURITY=ssl
SMTP_USERNAME=resend
SMTP_PASSWORD=REPLACE_WITH_SENDING_KEY
EMAIL_FROM=每日一鉴 <history@read.starhub.vip>
EMAIL_RECIPIENTS=reader1@example.invalid,reader2@example.invalid
EMAIL_REPLY_TO=REPLACE_WITH_PRIVATE_REPLY_ADDRESS
EMAIL_SEND_ENABLED=false
```

文件在 `~/.config/history-in-practice/runtime.env`，权限 0600，repo 外；`bin/hip doctor` 只显示变量是否设置，并在 `email_config_problems` 列出缺项（不显示地址或密钥）。

**Reply-To 是必填项。** 邮件页脚写着“反馈：直接回复本邮件”“想暂停接收？直接回复这封邮件写‘暂停’”，而 `history@read.starhub.vip` 没有收件箱。因此 `EMAIL_REPLY_TO` 必须是一个你会查看的真实地址；未设置时程序拒绝任何真实发信（`hip doctor` 会提示）。

真实发信前，程序会校验：收件人非空、格式正确、无重复；SMTP 主机、端口、加密方式、用户名、密钥齐全；From 与 Reply-To 是有效地址。任一项缺失都不会“发送成功”，而是停下并报原因。每期第一次发送时冻结预期收件人集合（只存哈希），只有集合中每一位都被 SMTP 接收，这一期才算完成。

## 第一封真实测试（不打开正式发信开关）

`EMAIL_SEND_ENABLED` 保持 `false`，定时器保持未启用。用专门的一次性测试入口：

```bash
bin/hip doctor                                      # email_config_problems 必须为空
bin/hip send-test samples/D/article.json --confirm-real-email
```

- 它只在显式加 `--confirm-real-email` 时发送；使用独立的测试期次号（`sample-D-test-时间戳`），标题前加“【测试】”，不影响正式期次的发送状态。
- 发给私密配置中的全部收件人（目前两位）。命令返回每位收件人的 SMTP 结果；`accepted` 只表示服务器接收，不代表进了收件箱。
- 然后人工确认：Gmail 与 QQ 都收到；不在垃圾箱；邮件头 SPF/DKIM 通过；中英文排版正常；**在其中一封上点“回复”，确认回复到了 Reply-To 地址**。
- 都正常后，才把 `EMAIL_SEND_ENABLED=true` 写进私密配置，并按 `deploy/systemd/README.md` 启用定时器。

`hip send ARTICLE --real` 是正式发信入口，仍受 `EMAIL_SEND_ENABLED` 约束；开关为 false 时它会拒绝并返回非零，不会让人误以为已发出。

## 官方依据

- https://resend.com/pricing
- https://www.resend.com/changelog/smtp-service
- https://www.resend.com/migrate/postmark
- https://resend.com/blog/top-10-email-deliverability-tips
