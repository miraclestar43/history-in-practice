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

字段名为建议，实施后须与程序一致。文件例如 `~/.config/history-in-practice/runtime.env`，权限 0600，repo 外；检查配置只显示变量是否设置，不显示值。发送开关关闭时必须没有真实网络发信，即使已有凭据。

今夜可完成 multipart text/plain + text/html、SMTP TLS、逐收件人状态、稳定 Message-ID、未知结果处理与本地 SMTP 测试。保存 .eml/HTML 预览时使用虚构地址。

## 官方依据

- https://resend.com/pricing
- https://www.resend.com/changelog/smtp-service
- https://www.resend.com/migrate/postmark
- https://resend.com/blog/top-10-email-deliverability-tips
