# 中国移动10086 Home Assistant 集成（实验版）

从自己的“中国移动10086”微信服务号读取话费、流量和通话余量，每 30 分钟更新一次。所有网络请求都是只读的；不会充值、订购、退订或修改账号。

## 在 Home Assistant 中的效果

下图是设备页面，可查看话费余额及各类流量的剩余量、已用量和总量。截图中的数值仅为展示时的账号状态。

![中国移动10086 集成在 Home Assistant 中的设备页面](image/ha-device-overview.png)

## 下载与安装

从 [Releases](https://github.com/cumtwjq/china-mobile-10086-ha/releases/latest) 下载：

- `china_mobile_10086-experimental.zip`：Home Assistant 集成安装包。
- `china_mobile_10086-local-capture.zip`：Windows 本地抓取工具，包含 Python 和 mitmproxy，无需另外安装。

按[安装说明](INSTALL.md)安装。首次配置用[本地抓取工具](local_tool/本地抓取说明.md)获取自己账号的只读请求 JSON，并粘贴到 HA 配置页。仓库和下载包不包含个人抓包数据、Cookie 或 CSRF 凭证。

## 传感器

- 话费余额。
- 总流量、国内通用流量、国内其他流量的剩余量、已用量和总量。
- 剩余通话、已用通话、通话总量。
- 每个流量套餐的剩余量；总量、已用量和到期日放在传感器属性中。

单位按服务号页面脚本核对：流量接口的单位代码 `1` 为 MB，HA 中的 GB 以 1024 MB 换算。登录凭证失效后，在集成的“配置”中导入新的本地抓取请求。

登录请求没有可读取的固定有效期；失效后重新抓取。`wx.10086.cn` 对部分 Python TLS 客户端只提供旧版 TLS 1.2 密码套件，本集成仅对该域名使用兼容配置，仍校验证书。
