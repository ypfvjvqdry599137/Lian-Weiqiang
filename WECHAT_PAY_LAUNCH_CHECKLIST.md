# 微信支付上线检查清单

这份清单按「账号资质 -> 商户平台 -> 服务器环境变量 -> 联调验证 -> 上线前复核」排列，和当前代码里的配置名一致。

## 1. 账号与资质

- [ ] 小程序已完成微信认证
- [ ] 商户号已开通微信支付能力
- [ ] 商户号已与小程序 `AppID` 完成绑定
- [ ] 如果后续要做 H5 或公众号场景，再补配 `JSAPI` 支付授权目录
- [ ] 当前这套小程序内支付只走小程序调起，不需要额外的 H5 授权目录

## 2. 商户平台需要准备的值

- [ ] 微信小程序 `AppID`
- [ ] 微信小程序 `AppSecret`
- [ ] 微信支付商户号 `mchid`
- [ ] 商户 API 证书私钥
- [ ] 商户 API 证书序列号 `serial_no`
- [ ] `APIv3` 密钥，长度必须是 32 位
- [ ] 回调地址已配置并可公网访问
- [ ] 回调地址使用 `HTTPS`
- [ ] 商户 API 证书私钥保存到安全位置，不提交到仓库

## 3. 当前代码里实际使用的环境变量

如果你用这份 GitHub Actions 自动部署，建议把下面这些值写进 GitHub 仓库的 Secrets；workflow 会自动同步到服务器。

```env
PUBLIC_BASE_URL=https://api.example.com
WECHAT_MINI_PROGRAM_APPID=wx1234567890abcdef
WECHAT_MINI_PROGRAM_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WECHAT_PAY_MCHID=1900000001
WECHAT_PAY_API_V3_KEY=32位随机字符串请妥善保管
WECHAT_PAY_SERIAL_NO=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
WECHAT_PAY_PRIVATE_KEY_PATH=C:\secure\wechatpay\apiclient_key.pem
WECHAT_PAY_NOTIFY_URL=https://api.example.com/client/wechat/pay/notify
```

如果你选择把私钥内容直接放进 Secret，也可以额外准备 `WECHAT_PAY_PRIVATE_KEY`；workflow 会在服务器上生成 `backend/.wechatpay/apiclient_key.pem` 并自动写入路径。

代码里也兼容了这些旧变量名：

- `WECHAT_APPID`
- `WECHAT_APP_SECRET`
- `WECHAT_PAY_CERT_SERIAL`

## 4. 上线前必须确认的配置点

- [ ] `WECHAT_MINI_PROGRAM_APPID` 和小程序后台一致
- [ ] `WECHAT_MINI_PROGRAM_SECRET` 和小程序后台一致
- [ ] `WECHAT_PAY_MCHID` 和商户平台一致
- [ ] `WECHAT_PAY_API_V3_KEY` 已生成且未泄露
- [ ] `WECHAT_PAY_SERIAL_NO` 对应当前正在使用的商户 API 证书序列号
- [ ] `WECHAT_PAY_PRIVATE_KEY_PATH` 指向正确的私钥文件
- [ ] `WECHAT_PAY_NOTIFY_URL` 已指向正式环境可访问地址
- [ ] `PUBLIC_BASE_URL` 已是正式域名，不是本地地址
- [ ] 服务器时间已同步，避免签名和回调排查困难

## 5. 联调顺序

建议按这个顺序测，能最快发现配置问题：

1. [ ] 先测 `wx.login` -> `POST /client/wechat/login`
2. [ ] 再测下单接口 `POST /client/orders/<order_sn>/wechat-pay`
3. [ ] 确认小程序能正常拉起 `wx.requestPayment`
4. [ ] 支付成功后，调用 `POST /client/orders/<order_sn>/pay` 能返回成功
5. [ ] 微信支付回调 `POST /client/wechat/pay/notify` 能收到并正常落库
6. [ ] 重复回调不会重复扣库存、不会重复拆单
7. [ ] 未支付订单取消后，不会被后续支付回调误改状态
8. [ ] 订单详情页、订单列表页能看到正确的支付状态和交易号

## 6. 生产验收重点

- [ ] 只确认一次库存扣减
- [ ] 只生成一次供应商备货单
- [ ] 支付成功后订单状态为 `20`
- [ ] `transaction_id` 已写入订单
- [ ] `paid_at` 已写入订单
- [ ] 微信支付回调地址返回符合预期的状态码
- [ ] 失败日志里能看到明确的错误信息，方便排查商户号、证书、密钥和回调问题

## 7. 建议的上线前检查命令

先在生产环境或预发环境确认这些值：

- [ ] 检查应用启动时是否能读取 `.env` 或环境变量
- [ ] 检查回调地址是否能从公网访问
- [ ] 检查微信商户平台里 AppID 绑定是否生效
- [ ] 检查私钥文件权限是否只对部署账号可读
- [ ] 检查 `APIv3` 密钥是否和当前证书、回调配置一致

## 8. 官方文档参考

- [开发接入准备 - 小程序支付](https://pay.wechatpay.cn/doc/v3/merchant/4015459512)
- [配置 APIv3 密钥](https://pay.wechatpay.cn/doc/v3/merchant/4012072195)
- [管理商户号绑定的 APPID 账号](https://pay.wechatpay.cn/doc/v3/merchant/4013287504)
- [开发必要参数说明](https://pay.wechatpay.cn/doc/v3/merchant/4013070756)


