# 中国移动10086 Home Assistant 集成（HAOS 浏览器实验版）

此版本以 [ChinaMobileMonitor](https://github.com/shiranzby/ChinaMobileMonitor) 的持久化 Chromium 查询方式为基础。**在 Home Assistant 集成界面输入手机号和短信验证码**；HAOS 加载项在后台操作中国移动官方网页登录页，之后复用浏览器状态查询话费、流量和通话余量。电脑不需要一直开机，也不需要手机代理抓包或粘贴请求 JSON。官网出现滑块等额外验证时，可打开加载项的远程浏览器完成。

> 真实账号尚未完成端到端验证。上游浏览器方案也说明：登录状态失效时仍需重新验证。此版不会自动读取短信验证码，不能承诺长期免登录。查询只读取账号数据，不执行充值、订购或退订。

## 安装

参见 [安装和测试说明](INSTALL.md)。需要同时安装：

1. [自定义集成 ZIP](https://github.com/cumtwjq/china-mobile-10086-ha/releases/download/v0.2.4/china_mobile_10086-experimental.zip)。
2. [HAOS 加载项 ZIP](https://github.com/cumtwjq/china-mobile-10086-ha/releases/download/v0.2.4/china_mobile_10086-haos-app.zip)。

先启动加载项，再在“添加集成”里输入手机号并提交短信验证码。登录会话保存在 HAOS 加载项 `/data/browser_profile`，不会写进集成配置；查询值经 HAOS `/share/china_mobile_10086/account.json` 共享给集成。加载项界面由 Home Assistant Ingress 保护，不开放额外的局域网端口。

## 查询和失效提示

- 加载项每 **30 分钟**打开已登录的中国移动页面查询；登录成功后会立即首次查询。
- 集成每 **1 分钟**读取加载项的最新结果。
- “浏览器登录状态”为 `ok` 时，数值可用；`authenticating` 表示短信登录正在进行；`login_required` 时 HA 会提示“重新认证”，在集成界面输入新的短信验证码；`query_failed` 表示官方页面显示升级公告或未返回可识别数据；`waiting_for_app` 或 `stale` 表示加载项未运行或长时间没有更新。
- 从旧版升级时，旧抓包请求会从集成配置中移除；登录需使用当前的短信验证流程。

目前从页面提取话费余额、总/通用/定向/其他流量的余量、已用量和总量，以及通话余量、已用量和总量。已用流量为 MB，余量和总量为 GB。接口没有返回的字段会显示为不可用，不会用旧值填充。

话费余额优先读取网页上明确标注的金额；网页未显示该金额时，才回退到 `fareBalance` 接口字段。这是为修正网页显示 116.63 元而接口字段返回 126.63 元的实际案例。

## 来源与鸣谢

浏览器登录、持久化浏览器状态和查询接口以 [ChinaMobileMonitor](https://github.com/shiranzby/ChinaMobileMonitor)（MIT License）为基础，其许可文本随加载项一同提供；配置与重新认证交互参考 [Shaobo-Pocket-Carrier](https://github.com/Shaobor/Shaobo-Pocket-Carrier)（MIT License），未使用其联通、电信接口。感谢 **Codex** 全程指导、编写代码并整理文档；感谢账号持有人提供实际数据并在 Home Assistant 中测试。
