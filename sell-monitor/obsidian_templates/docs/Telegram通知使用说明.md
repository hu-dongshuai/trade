# Telegram 通知使用说明

## 作用

当前 Telegram 通知只在两种情况下发送：

- 卖出监控：卖出分数 `>= 8`，且动作为 `reduce`、`stop_loss`、`exit_all`
- 开仓检查：判定为允许开仓

通知内容包含：

- 股票代码
- 买入 / 卖出类型
- 主要触发理由

## 第一步：创建机器人

1. 在 Telegram 里搜索 `@BotFather`
2. 发送 `/newbot`
3. 按提示设置机器人名称和用户名
4. 创建完成后，`@BotFather` 会返回一串 `bot token`

这串 `bot token` 就是配置里的：

```dotenv
SELL_MONITOR_TELEGRAM_BOT_TOKEN=你的 bot token
```

## 第二步：拿到 chat id

1. 先给你刚创建的机器人发一条消息，比如 `hello`
2. 在浏览器打开：

```text
https://api.telegram.org/bot<你的bot token>/getUpdates
```

3. 在返回内容里找到：

```json
"chat": {
  "id": 123456789,
  ...
}
```

这里的 `id` 就是你的 `chat id`

把它写到配置里：

```dotenv
SELL_MONITOR_TELEGRAM_CHAT_ID=123456789
```

## 第三步：写入监控配置

打开：

```text
E:\tools\OB\Obsidian\Trade\notes\monitor\config\sell-monitor-config.md
```

补上：

```dotenv
SELL_MONITOR_TELEGRAM_BOT_TOKEN=你的 bot token
SELL_MONITOR_TELEGRAM_CHAT_ID=你的 chat id
SELL_MONITOR_TELEGRAM_SUBJECT_PREFIX=[SellMonitor]
SELL_MONITOR_TELEGRAM_API_BASE_URL=https://api.telegram.org
```

## 常见问题

### 1. 不想启用 Telegram，怎么办

把 `SELL_MONITOR_TELEGRAM_BOT_TOKEN` 或 `SELL_MONITOR_TELEGRAM_CHAT_ID` 留空即可，系统会自动跳过 Telegram 通知。

### 2. `getUpdates` 里没有 `chat.id`

通常是因为你还没有先给机器人发过消息。先手动给机器人发一条，再刷新 `getUpdates`。

### 3. 发送失败会不会影响监控

不会。Telegram 发送失败只会在终端打印错误，不会中断卖出监控或开仓检查本身。
