# Sell Monitor Config

```dotenv
# 卖出监控 / 开仓检查 总配置
SELL_MONITOR_PROVIDER=akshare

# 卖出监控输出目录
SELL_MONITOR_OBSIDIAN_MONITOR_ENABLED=true
SELL_MONITOR_OBSIDIAN_MONITOR_DIR=E:\tools\OB\Obsidian\Trade\notes\monitor\sell

# 开仓检查输出目录
SELL_MONITOR_OBSIDIAN_ENTRY_ENABLED=true
SELL_MONITOR_OBSIDIAN_ENTRY_DIR=E:\tools\OB\Obsidian\Trade\notes\monitor\entry

# Obsidian 配置文件路径
SELL_MONITOR_SELL_WATCHLIST_PATH=E:\tools\OB\Obsidian\Trade\notes\monitor\config\sell-watchlist.md
SELL_MONITOR_ENTRY_WATCHLIST_PATH=E:\tools\OB\Obsidian\Trade\notes\monitor\config\entry-watchlist.md
SELL_MONITOR_POSITIONS_PATH=E:\tools\OB\Obsidian\Trade\notes\monitor\config\positions.md
SELL_MONITOR_USER_RULES_PATH=E:\tools\OB\Obsidian\Trade\notes\monitor\config\user_rules.md

# 静态测试数据
SELL_MONITOR_MARKET_DATA_PATH=C:\Users\admin\Documents\New project\sell-monitor\examples\market_data.json

# 邮件提醒
# 163 邮箱常用配置示例：
#   Host: smtp.163.com
#   Port: 465
#   Use SSL: true
#   Use TLS: false
#   Username / From / To: 你的 163 邮箱地址
#   Password: 不是邮箱登录密码，而是 SMTP 授权码
SELL_MONITOR_SMTP_HOST=smtp.example.com
SELL_MONITOR_SMTP_PORT=587
SELL_MONITOR_SMTP_USE_SSL=false
SELL_MONITOR_SMTP_USE_TLS=true
SELL_MONITOR_SMTP_USERNAME=you@example.com
SELL_MONITOR_SMTP_PASSWORD=your-app-password
SELL_MONITOR_EMAIL_FROM=you@example.com
SELL_MONITOR_EMAIL_TO=you@example.com
SELL_MONITOR_EMAIL_SUBJECT_PREFIX=[SellMonitor]

# Telegram 提醒
# 卖出侧：仅在卖出分数 >= 5 且动作是 reduce / stop_loss / exit_all 时发送
# 开仓侧：仅在 allowed=yes 时发送
SELL_MONITOR_TELEGRAM_BOT_TOKEN=your-bot-token
SELL_MONITOR_TELEGRAM_CHAT_ID=your-chat-id
SELL_MONITOR_TELEGRAM_SUBJECT_PREFIX=[SellMonitor]
SELL_MONITOR_TELEGRAM_API_BASE_URL=https://api.telegram.org
# 如果本机直连 Telegram 不通，可填写本地代理，例如 http://127.0.0.1:7890
# SELL_MONITOR_TELEGRAM_PROXY=http://127.0.0.1:7890
```
