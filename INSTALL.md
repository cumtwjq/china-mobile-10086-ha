# 安装

1. 从 [Releases](https://github.com/cumtwjq/china-mobile-10086-ha/releases/latest) 下载两个 ZIP。将 `china_mobile_10086-experimental.zip` 中的 `custom_components/china_mobile_10086` 目录解压到 HA 配置目录的 `custom_components` 下。
2. 重启 Home Assistant。
3. 将 `china_mobile_10086-local-capture.zip` 完整解压到 Windows 电脑，双击其中的 `获取10086请求.cmd`。按窗口提示配置手机代理、安装并信任证书，再打开“中国移动10086”服务号主页并刷新。
4. 抓齐后，工具会把只读请求 JSON 复制到电脑剪贴板。到 HA“设置 → 设备与服务 → 添加集成”，搜索“中国移动10086”，把剪贴板内容直接粘贴到配置页。
5. 把 iPhone 当前 Wi-Fi 的代理改回“关闭”，并复制普通文字覆盖电脑剪贴板。

HA 主机须能访问 `wx.10086.cn:443`。抓取内容含登录 Cookie 和 CSRF 凭证，保存在当前 Windows 用户的 DPAPI 加密文件中；HA 导入后保存在本机配置中。不要把导出的 JSON 发到聊天、网盘或公开仓库。登录失效时重新运行本地工具，然后在集成“配置”中更新请求。

集成的“帮助”链接指向 `wx.10086.cn` 首页。首页显示升级公告时，微信内页面仍可能正常；它不能单独证明接口停用。如果配置页提示“接口返回升级公告”，先在公众号确认查询正常，再重新抓取并验证请求。
