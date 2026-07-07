# Telegram 通知使用说明

## 1. 什么时候会发 Telegram

当前只有两类通知：

- 卖出监控：动作属于 `reduce / stop_loss / exit_all`，且分数 `>= 5`
- 开仓检查：判定为 `allow_entry`

补充说明：

- 卖出侧的回溯补齐如果补出了卖出信号，还会按股票汇总发一条“回溯补齐卖出汇总”
- 开仓侧消息会额外写明当前路线是 `标准开仓` 还是 `T仓回补`

## 2. 第一步：创建机器人

1. 打开 Telegram，搜索 `@BotFather`
2. 发送 `/newbot`
3. 按提示设置机器人名称和用户名
4. 创建完成后拿到 `bot token`

把它写进配置：

```dotenv
SELL_MONITOR_TELEGRAM_BOT_TOKEN=你的 bot token
```

## 3. 第二步：获取 chat id

1. 先给你自己的机器人发一条消息，例如 `hello`
2. 打开：

```text
https://api.telegram.org/bot<你的bot token>/getUpdates
```

3. 在返回 JSON 里找到：

```json
"chat": {
  "id": 123456789
}
```

把这个值写进配置：

```dotenv
SELL_MONITOR_TELEGRAM_CHAT_ID=123456789
```

## 4. 配置位置

配置文件：

```text
E:\tools\OB\Obsidian\Trade\notes\monitor\config\sell-monitor-config.md
```

写入：

```dotenv
SELL_MONITOR_TELEGRAM_BOT_TOKEN=你的 bot token
SELL_MONITOR_TELEGRAM_CHAT_ID=你的 chat id
SELL_MONITOR_TELEGRAM_SUBJECT_PREFIX=[SellMonitor]
SELL_MONITOR_TELEGRAM_API_BASE_URL=https://api.telegram.org
```

## 5. 通知内容

### 5.1. 卖出通知

卖出通知会包含：

- 股票代码/中文名
- 类型：卖出
- 动作
- 分数
- 前几条主要理由
- 下一步建议

### 5.2. 开仓通知

开仓通知会包含：

- 股票代码/中文名
- 类型：买入
- 路线：`标准开仓` 或 `T仓回补`
- 动作
- 分数
- 前几条主要理由
- 计划挂单价
- 止损价
- 第一止盈位

### 5.3. 回溯补齐卖出汇总

若自动补齐历史槽位时补出了卖出信号，会发一条汇总消息，包含：

- 股票
- 时间范围
- 条数
- 每条信号的时间、动作、分数、价格、首条原因

## 6. 不想启用 Telegram

把下面任一项留空即可：

```dotenv
SELL_MONITOR_TELEGRAM_BOT_TOKEN=
SELL_MONITOR_TELEGRAM_CHAT_ID=
```

系统会自动跳过 Telegram 通道，不影响监控主流程。

## 7. 常见问题

### 7.1. `getUpdates` 里没有 `chat.id`

通常是因为你还没先给机器人发消息。

### 7.2. 发送失败会不会影响监控

不会。

发送失败只会在终端打印错误，不会中断卖出监控或开仓检查。
