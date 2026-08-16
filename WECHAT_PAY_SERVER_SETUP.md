# 微信支付服务器配置指南

这份说明是给 Ubuntu 服务器上的正式环境用的。目标是把微信支付相关的敏感配置放在服务器本地，不放进 GitHub 仓库。

## 你需要准备什么

从微信小程序后台准备：

- 小程序 AppID
- 小程序 AppSecret

从微信支付商户平台准备：

- 商户号 `mchid`
- APIv3 密钥
- 商户 API 证书序列号
- 商户 API 私钥文件，通常是 `apiclient_key.pem`
- 支付回调地址 `notify_url`

如果项目会用到地图能力，再准备腾讯地图 Key。

## 放到哪里

建议把这些值写到服务器上的项目根目录 `.env`，例如：

- `/你的项目目录/.env`

商户私钥建议单独放一个固定路径，例如：

- `/你的项目目录/backend/.wechatpay/apiclient_key.pem`

只要 `WECHAT_PAY_PRIVATE_KEY_PATH` 指向这个绝对路径就行。

## `.env` 里要填什么

在服务器上的 `.env` 里放这些变量：

```env
PUBLIC_BASE_URL=https://你的正式域名
WECHAT_MINI_PROGRAM_APPID=wx1234567890abcdef
WECHAT_MINI_PROGRAM_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WECHAT_PAY_MCHID=1900000001
WECHAT_PAY_API_V3_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WECHAT_PAY_SERIAL_NO=1234567890ABCDEF1234567890ABCDEF12345678
WECHAT_PAY_PRIVATE_KEY_PATH=/你的项目目录/backend/.wechatpay/apiclient_key.pem
WECHAT_PAY_NOTIFY_URL=https://你的正式域名/client/wechat/pay/notify
TENCENT_MAP_KEY=如果页面需要地图就填
```

如果数据库配置也是环境变量管理，就一并放进去：

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=你的数据库用户
DB_PASSWORD=你的数据库密码
DB_NAME=你的数据库名
```

## 微信上对应关系

- `WECHAT_MINI_PROGRAM_APPID`：小程序 AppID
- `WECHAT_MINI_PROGRAM_SECRET`：小程序 AppSecret
- `WECHAT_PAY_MCHID`：商户号
- `WECHAT_PAY_API_V3_KEY`：APIv3 密钥
- `WECHAT_PAY_SERIAL_NO`：商户 API 证书序列号
- `WECHAT_PAY_PRIVATE_KEY_PATH`：商户 API 私钥文件路径
- `WECHAT_PAY_NOTIFY_URL`：微信支付异步回调地址

## 服务器上怎么操作

1. SSH 登录到 Ubuntu 服务器。
2. 进入项目目录。
3. 找到项目根目录的 `.env`。
4. 把上面的变量填进去。
5. 把 `apiclient_key.pem` 放到 `WECHAT_PAY_PRIVATE_KEY_PATH` 指定的位置。
6. 收紧权限：

```bash
chmod 600 .env
chmod 600 backend/.wechatpay/apiclient_key.pem
```

## 如果你不知道项目目录在哪

先找正在跑的服务：

```bash
systemctl list-units --type=service | grep -Ei 'gunicorn|uwsgi|flask|app|backend|sxps'
```

查工作目录：

```bash
systemctl show -p WorkingDirectory 服务名
systemctl cat 服务名
```

如果你是 Git 自动部署，也可以去 GitHub Actions 里看部署时配置的 `PROJECT_DIR`。

## 配完以后

1. 重启服务。
2. 看日志确认没有报错。
3. 做一次微信支付下单和回调测试。

```bash
sudo systemctl restart 服务名
journalctl -u 服务名 -f
```

## 记住这条原则

- 微信支付敏感配置只放服务器。
- 仓库里只保留代码，不放商户私钥和 APIv3 密钥。
- GitHub Actions 只负责拉代码和重启服务。
