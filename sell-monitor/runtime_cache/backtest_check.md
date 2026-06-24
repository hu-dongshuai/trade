# 卖出提醒策略回测 2026-05-20 至 2026-05-21

- 生成时间: 2026-06-05 15:34:50
- 回测事件数: 2
- 减仓提醒: 0，命中 0，误报 0
- 清仓/止损提醒: 2，命中 0，误报 2
- 漏报: 0

## 判定口径

- 减仓命中: 触发后 15 个交易日内最大回撤 >= 7%。
- 清仓命中: 触发后 15 个交易日内最大回撤 >= 7%。
- 误报: 未达到对应回撤阈值，且触发后最大上涨 >= 7%。
- 漏报: HOLD 后 15 个交易日内最大回撤 >= 7%，且此前 15 个交易日内没有出现减仓/清仓/止损提醒。

## 支撑压力位

### 支撑压力位

| 股票 | 周期 | 等级 | 类型 | 区间下沿 | 区间上沿 | 净分 | 重要性 | 脆弱性 | 失效价 | 触达次数 | 标签 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 002241 | 1d | A | 压力 | 24.50 | 27.36 | 7 | 8 | 1 | 27.36 | 4 | daily_fibonacci, fib_0.382, fib_0.5, fib_0.618, fib_0.786, fib_ext_1.272, fresh_zone, merged_resistance, resistance, with_fibonacci, with_fvg, with_large_liquidity, with_liquidity, with_order_block, with_partially_filled_fvg |
| 002241 | 1d | B | 支撑 | 21.69 | 22.10 | 7 | 8 | 1 | 21.49 | 4 | support, fresh_zone, with_liquidity, with_large_liquidity, with_order_block |
| 002241 | 1d | B | 支撑 | 23.67 | 24.07 | 6 | 7 | 1 | 23.47 | 4 | support, with_liquidity, with_large_liquidity |
| 002241 | 1d | B | 支撑 | 24.37 | 24.78 | 5 | 7 | 2 | 24.17 | 3 | support, recently_tested, with_liquidity, with_large_liquidity, with_order_block |
| 002241 | 1d | B | 支撑 | 27.32 | 27.73 | 5 | 6 | 1 | 27.12 | 3 | support, fresh_zone, with_liquidity, with_order_block |
| 002241 | 1d | B | 压力 | 28.57 | 28.98 | 7 | 7 | 0 | 29.18 | 2 | daily_fibonacci, fib_ext_1.618, fresh_zone, merged_resistance, resistance, with_fibonacci, with_fresh_fvg, with_fvg |
| 002241 | 1w | B | 压力 | 31.46 | 32.18 | 4 | 4 | 0 | 32.54 | 2 | fresh_zone, higher_timeframe, resistance, weekly_resistance, with_order_block |

## 明细

| 日期 | 股票代码 | 股票名称 | 动作 | 分数 | 持有保护分 | 价格 | 15日最大回撤 | 15日最大上涨 | 结果 | 原因 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 2026-05-20 | 002241 | 002241 | exit_all | 10 | 1 | 24.90 | 3.11% | 16.35% | 误报 | 出现第三根危险上影线; 15:00 这根15分钟K线放量，且连续两根15分钟K线收在 MA20 下方 |
| 2026-05-21 | 002241 | 002241 | exit_all | 9 | 1 | 24.76 | 2.57% | 17.00% | 误报 | 出现第三根危险上影线; 跌破最近一次创出新高后的回调低点; 15:00 这根15分钟K线放量，且连续两根15分钟K线收在 MA20 下方 |
