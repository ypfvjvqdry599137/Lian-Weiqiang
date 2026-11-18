# 供应商 PushPlus 微信提醒接入

后端通过 [PushPlus 官方 Python SDK](https://github.com/pushplus/perk-pushplus-python-sdk) 发送消息，依赖已锁定在 `backend/requirements.txt`。仅发送消息需要 `PUSHPLUS_TOKEN`；无需配置开放接口的 Secret Key。

## 准备接收群组

1. 在 PushPlus 会员账号的“发送消息 → 一对多消息”中，为每个供应商创建一个**私密群组**，记下群组编码。
2. 让每个供应商的备货人员关注“pushplus 推送加”公众号，扫码加入自己的群组，并确认公众号通知未被屏蔽。可先在 PushPlus 网页上向该群组试发一条消息。
3. 在鲜配居主后台“供应商管理 → 编辑”中填入对应的“PushPlus 私密群组编码”。留空表示该供应商不接收推送。群组编码只能使用字母、数字、下划线和短横线。

## 自定义通知内容

在主后台“供应商通知模板”分别编辑新备货单和停止备货的正文。消息标题统一为“鲜配居：…”。每条正文必须包含 `{order_sn}`；还可以使用 `{supplier_order_id}`、`{items}`、`{reason}` 和 `{supplier_url}`。页面提供示例订单预览，并可逐条恢复默认内容。修改只影响保存后新生成的消息；已经排队或发出的消息不会改动。不要在模板中填写顾客姓名、电话或地址。

## 启用服务器发送

部署代码后，服务器会安装 `fresh-produce-pushplus.service`，但在未配置发送账号前不会启动推送。

在服务器 `/home/ubuntu/Lian-Weiqiang/.env` 增加：

```dotenv
PUSHPLUS_TOKEN=从PushPlus网站复制的发送Token
PUSHPLUS_ACTIVATED_AT=YYYY-MM-DDTHH:MM:SSZ
```

`PUSHPLUS_ACTIVATED_AT` 必须填写**准备正式启用时的 UTC 时间**，可在服务器运行 `date -u +%Y-%m-%dT%H:%M:%SZ` 获取，然后粘贴到等号后。早于该时间的订单不会补发提醒。Token 只保存在服务器，勿放到前端或提交到 Git。

确保 `.env` 可由后端运行用户读取，之后执行：

```bash
sudo systemctl restart fresh-produce-pushplus.service
sudo systemctl status fresh-produce-pushplus.service --no-pager
sudo journalctl -u fresh-produce-pushplus.service -n 50 --no-pager
```

## 推送规则

- 用户付款成功、备货单处于待备货或备货中时，向该供应商私密群组发送一次“新备货单”。仅包含订单号、备货单号和原料数量，不含顾客姓名、电话、地址。
- 已通知过的订单申请退款、后台发起退款或订单取消时发送一次“停止备货”。即使退款后来关闭，原订单也不会恢复备货；顾客需重新下单。历史排队中的“暂停/恢复”通知会跳过。实际操作始终以供应商后台订单状态为准。
- 发送任务独立于微信支付回调。失败会记录并重试；同一备货单的同类提醒去重。会员频率按至少 2.1 秒一条控制，PushPlus 返回账号受限时所有提醒暂停 24 小时。
- PushPlus `code=200` 只表示平台受理，不能证明微信最终送达。上线前应在接收方微信里验证一笔新单和一次退款流程，并在 PushPlus“最新请求”查看最终投递结果。

关闭推送：清空服务器中的 `PUSHPLUS_TOKEN` 后重启服务，或执行 `sudo systemctl stop fresh-produce-pushplus.service`。后台在线提醒不受影响。
