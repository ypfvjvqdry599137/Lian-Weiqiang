# 项目交接（2026-10-01，Asia/Shanghai）

> 给完全没看过历史聊天的新 Codex。**本轮只做交接，不开始新功能。**生产环境会变化，以下的历史线上验证不能当作今日实时状态；操作前必须重新核对。文档不含口令或私钥。

## 1. 代码保存状态

- 原电脑工作区是 `D:\sxps`，远端仓库 `https://github.com/ypfvjvqdry599137/Lian-Weiqiang.git`，分支 `main`。
- 创建本文件前，`git status --short --branch` 只显示 `## main...origin/main`，没有未提交改动；本机 `HEAD` 与已获取的 `origin/main` 同为 `184d9e0988354ff0d40fb8ae636dae9b3b403198`。最近业务提交 `184d9e0` 是客户隔离和后台登录修复。这个结论只涉及已获取的远端跟踪引用，不等于当日重新查询 GitHub 或生产服务器。
- 新增本文件后应重新检查 `git status`。**只有把本文件传到另一台电脑，新 Codex 才能看到它。**注意 `.github/workflows/deploy.yml`：对 `main` 的任何推送（包括纯文档）都会触发生产部署并重启后端；未经用户确认不要仅为传文档推送 `main`。
- Git 忽略 `.env`、`backend/.env`、`backend/.wechatpay/`、SQLite、uploads、虚拟环境、`node_modules`、`miniprogram-client/project.config.json` 等。这些不会随克隆迁移，也不应提交到仓库或贴在聊天里。

## 2. 最终目标

- 让生鲜小程序在当前目标服务器和正式域名安全上线：不同微信用户的购物车、地址、订单严格隔离；下单、微信支付、查询/回调、取消/退款与订单履约可核对；管理员、供应商、站点流程可用；真机无需代理即可访问。
- 前端商品只有一份，不按区域复制。配送区域由地图中心及配送半径确定，每个区域有负责的配送站；蔬菜、海鲜等原料供应商按区域/品类供货到站点，站点统一打包配送；一个供应商可供多个站点。
- **目前不能宣称全面正式上线。**用户确认旧服务器上曾成功支付，但这不能替代当前安全版本的完整支付和真机验证。

## 3. 已完成的工作

- 项目结构：`backend/` 是 Flask + SQLAlchemy API（`backend/app.py` 含 `create_app()` 应用工厂；受版本管理的 `deploy/fresh-produce.service` 用 Gunicorn 启动 `app:create_app()`）；`miniprogram-client/` 是微信小程序；`admin-panel/` 是主后台、供应商及商家页面；`schema/` 与 `deploy/` 提供数据库和部署材料。仓库**没有** `backend/run.py`，不要照旧服务器截图把它当作可迁移入口。
- 已实现配送区域/站点、供应商按区域和品类的供货规则、商品原料清单、按供应商与站点拆分供货单、异常记录。核心在 `backend/models.py`、`backend/fulfillment.py`、`backend/fulfillment_admin_routes.py`、`backend/admin_routes.py` 及 `admin-panel/`。供货解析优先有效区域/品类规则，再回退原料默认供应商。
- 提交 `184d9e0`：`backend/auth.py` 建立角色区分的签名时效 Token；微信 OpenID 映射独立客户身份，购物车/地址/订单/支付绑定当前身份，不再共享“首个用户”。旧的共享数据没有自动迁给新用户。私有客户接口要求身份；主后台加入服务端管理员登录与鉴权，供应商接口绑定供应商身份；已支付订单不能由客户直接取消、也不能在后台随意删除或更改关键支付状态。
- `backend/config.py` 从项目根目录/后端 `.env` 加载配置；生产启动要求有效的 `AUTH_SIGNING_KEY`、`ADMIN_PASSWORD_HASH`。小程序请求层已适配客户 Token；自动测试覆盖身份隔离与后台权限。
- 2026-09-29 在备份后清理了旧共享身份产生的 20 笔未收款/取消测试订单。**保留了 1 笔已付 ¥3.99 的旧单**：微信查询返回 `SUCCESS`，当时未确认退款，用户明确要求退款确认后再清理。当时备份在目标服务器 `backups/mysql/before-legacy-order-cleanup-20260929-221037.sql.gz` 且校验过 SHA256。最后一次当时的只读统计是 `order_master=1`、`order_item=1`、`supplier_order=0`、`client_identity=0`，另有旧地址 8 条、用户 2 条；这些不是今天的实时数据，清理前必须重查并再备份。
- 2026-10-01 本机运行 `backend` 单测 14 项通过；`miniprogram-client` Jest 7 套件、44 项通过。2026-09-29 目标服务器曾确认运行 `184d9e0`、匿名私有客户接口 401、公开商品接口 200、管理员登录和站点接口可访问。2026-10-01 本机 HTTPS 检查：商品接口 200，后台登录页 200，未登录订单接口 401；但当日 SSH 审计连接在 banner 阶段超时，**没有重新确认线上 Git 提交、进程或数据库**。HTTP 可达不是支付全链路验收。

## 4. 当前做到哪一步

当前是**上线前安全修复后的支付一致性收尾与重新验收阶段**，不是新增供应商功能。代码已经提交，本机测试通过；但尚无证据证明“新版小程序 + 新客户身份 + 当前服务器”完整经过微信登录、下单、支付、回调、退款与履约。小程序在微信公众平台上的最新上传/发布状态未知。本轮只新增本交接文档，不改业务代码或生产数据。

## 5. 未完成事项（顺序）

1. **重新核对环境。**新电脑克隆/拉取仓库，核对 `HEAD`、`git status`，配置安全的本地开发环境。通过获准的 SSH/腾讯云控制台只读核对目标服务器提交、`fresh-produce.service`、Nginx、数据库备份、订单与退款状态；先核查，后部署。
2. **补支付资金一致性。**在 `backend/client_routes.py` 的微信回调和主动查询流程中，除验签/解密外，还须校验 AppID、商户号、商户订单号、金额、付款 OpenID 与本地订单一致；不要仅靠回调附加描述选择订单。支付落库需要幂等和并发保护，重复回调、主动查询、取消竞态均需回归测试。取消未支付订单前必须与微信支付状态/关闭预支付协调，不能只改本地状态并释放库存。
3. **补退款闭环。**为已支付订单建立能核对的退款处理及状态记录（自动退款或有审计的人工流程）。历史 ¥3.99 订单在微信确认退款前不得删除；“删除订单”不是退款。
4. **修本地启动和过时说明。**`backend/run_dev.py` 的 `DevConfig` 目前只有数据库地址，没有新要求的签名密钥和管理员密码哈希，直接运行本地开发入口会失败。提供不含生产秘密的开发配置。`WECHAT_PAY_LAUNCH_CHECKLIST.md` 有 GitHub Secrets 自动同步支付变量的旧说法，与当前工作流不一致；实际业务支付变量来自服务器 `.env`，以代码和工作流为准。
5. **清遗留安全债。**旧数据库口令曾出现在 Git 历史，当前工作树已去除；有回滚预案时轮换生产口令并同步受控 `.env`。`backend/merchant_routes.py` 商家仍使用明文 `merchant_password` 和旧式确定性密钥，与新角色鉴权不一致；先设计迁移和测试，避免直接切断商家使用。
6. **端到端验收及微信发布。**备份并经授权部署后，确认微信小程序 request 合法域名含 `xianpeiju.site`、工具使用正确 AppID。真机用至少两个不同微信身份验购物车/地址/订单隔离、小额支付及回调、重复通知、取消/退款、按站点拆单和供应商流程。Git 后端部署**不会自动发布小程序**；仍须开发者工具上传及微信公众平台体验/审核/发布。完成验收和回滚准备后再开放给公众。

## 6. 已知缺陷和风险

| 级别 | 风险 | 代码/处理 |
| --- | --- | --- |
| 阻断全面上线 | 支付回调/查询未完整核对商户、AppID、订单号、金额、付款 OpenID；重复回调和并发落库保护不足 | `backend/client_routes.py`、`backend/wechat_pay_support.py`；验签不等于业务字段已核对 |
| 阻断全面上线 | 取消未付订单只改本地状态/库存，支付与取消并发可能导致已收款但本地订单已取消 | `backend/client_routes.py`；需要微信侧状态/关单或等效资金对账 |
| 阻断全面上线 | 退款闭环缺失；历史已付 ¥3.99 订单待确认退款 | 不得直接删除、改成未支付或分配给新用户 |
| 高 | 当前版本未有新的端到端真机支付证明；微信平台发布状态未知 | 旧服务器成功支付不可代替本次验收 |
| 高 | 旧数据库密码存在过 Git 历史 | 应轮换；不在文档中记录任何口令 |
| 中 | `backend/run_dev.py` 未适配必需鉴权配置 | 本地直接启动可能失败 |
| 中 | 商家明文密码/旧式鉴权尚未迁移 | `backend/merchant_routes.py` 与模型 |
| 中 | `main` 推送即生产部署；部分支付上线文档过时 | `.github/workflows/deploy.yml`、`WECHAT_PAY_LAUNCH_CHECKLIST.md` |
| 待核实 | 2026-10-01 SSH 超时，线上数据库和服务状态未重查 | 不要把历史检查写成实时状态 |

## 7. 最近修改/接手必读文件

- 身份与配置：`backend/auth.py`、`backend/config.py`、`backend/app.py`、`backend/models.py`。
- 客户与后台：`backend/client_routes.py`、`backend/admin_routes.py`、`backend/fulfillment_admin_routes.py`、`backend/supplier_routes.py`。
- 支付/履约依赖：`backend/wechat_pay_support.py`、`backend/fulfillment.py`（不一定在最后一个提交，但继续开发必读）。
- 前端：`miniprogram-client/app.js`、`admin-panel/login.html`、`admin-panel/index.html`、`admin-panel/js/app.js`、`admin-panel/supplier_login.html`、`admin-panel/supplier_dashboard.html`。
- 测试：`backend/tests/test_auth_isolation.py`、`backend/tests/test_wechat_pay.py`、`miniprogram-client/tests/app-auth.test.js`、`miniprogram-client/tests/setup.js`。
- 部署/说明：`.github/workflows/deploy.yml`、`WECHAT_PAY_SERVER_SETUP.md`、`WECHAT_PAY_LAUNCH_CHECKLIST.md`。

## 8. 新电脑从哪里开始

1. 克隆远端仓库，执行 `git status --short --branch`、`git log -1 --oneline`，以当前代码为基线。如果 `HANDOFF.md` 未随克隆出现，向用户索取原电脑保存的该文件；不要猜以前的聊天。
2. 先读 `backend/app.py`、`backend/config.py`、`backend/auth.py`、`backend/client_routes.py`、`backend/wechat_pay_support.py`、`backend/models.py`，随后读鉴权/支付测试、部署工作流和区域供货代码。冲突时以代码及最新测试为准。
3. 建 Python 虚拟环境并安装 `backend/requirements.txt`；到 `miniprogram-client/` 执行 `npm ci`。重新运行基线测试：

   ```powershell
   cd backend
   python -m unittest discover -s tests -q
   cd ../miniprogram-client
   npm test -- --runInBand --silent
   ```

4. 本地运行应用前，用**开发专用**数据库和秘密配置 `DATABASE_URL`、长度足够的 `AUTH_SIGNING_KEY`、`ADMIN_PASSWORD_HASH` 等（看 `backend/config.py`），不要拷贝生产 `.env` 进仓库。微信开发者工具的本地 `project.config.json` 是忽略文件，需要在新电脑用正确小程序 AppID 设置。旧电脑临时 SSH 审计密钥也不会自动迁移。
5. 下一项代码工作优先写支付字段不匹配、重复回调和取消竞态的测试，再改支付实现。任何生产数据库操作、部署、微信发布前，先同用户确认备份、影响和回滚；`main` 推送会自动重启生产后端。

## 9. 线上环境与不要推翻的结构

- **当前目标服务器** `43.155.202.205`；`43.128.145.146` 是迁移前的来源服务器，不要反过来。历史正式域名：`https://xianpeiju.site`（小程序 API）和 `https://admin.xianpeiju.site`（后台），后台登录路径 `/admin-panel/login.html`。变更前重查 DNS/Nginx。
- 目标机项目曾位于 `/home/ubuntu/Lian-Weiqiang`，`fresh-produce.service` 运行后端，Nginx 反代 HTTPS。根目录 `.env`、`backend/.wechatpay/apiclient_key.pem`、数据库、uploads、Nginx/Let's Encrypt 证书独立于 Git。GitHub Actions Secrets 用于 SSH 等部署连接；支付变量由服务器 `.env` 加载。工作流在有 DB 环境变量时还会备份并执行 `schema/update_supplier_schema.sql`，然后重启服务。不要覆盖生产秘密、证书、上传文件或数据库。
- **不要推翻** OpenID 到独立用户的映射和所有私有接口的身份过滤；不要把旧共享用户的地址/订单无证据迁给新客户。
- **不要推翻** 一份商品 + 区域供货规则 + 各类供应商供货到区域配送站 + 站点统一打包配送 + 同一供应商可覆盖多站的模型。不要退回“每区域一个总供应商”，也不要按区域复制商品。
- **不要推翻** 支付/退款资金状态与业务订单状态分开、可追溯的原则；不要靠删除已付款订单或直接改状态处理资金问题。
- 管理员口令、APIv3 key、数据库口令、微信支付/SSH 私钥只在受控环境处理。不要在 Git、交接文件或聊天中贴出。更换电脑需单独建立可信访问。

## 10. 完成标准

只有支付字段核对、幂等/取消竞态、退款闭环及跨用户隔离的自动测试和真机测试通过，且当前目标服务器版本、备份、域名、微信合法域名及正式小程序版本重新确认后，才可讨论正式全面上线。历史成功测试不是当前环境的上线证明。
