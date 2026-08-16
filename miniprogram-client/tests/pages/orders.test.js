const { loadApp, loadPage } = require('../helpers/loadPage');

describe('Orders page', () => {
  let app;
  let page;

  beforeEach(() => {
    jest.clearAllMocks();
    app = loadApp();
    page = loadPage('pages/orders/orders');
    app.payWechatOrder = jest.fn().mockResolvedValue({
      message: '支付成功',
      order_status: 20
    });
    page.loadOrders = jest.fn();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('continuePay calls the shared payment helper and refreshes the list', async () => {
    jest.useFakeTimers();

    await page.continuePay({
      currentTarget: {
        dataset: {
          sn: 'ORD202608160001'
        }
      }
    });

    expect(app.payWechatOrder).toHaveBeenCalledWith('ORD202608160001');
    expect(wx.showToast).toHaveBeenCalledWith({
      title: '支付成功',
      icon: 'success'
    });

    jest.runAllTimers();
    expect(page.loadOrders).toHaveBeenCalledTimes(1);
  });

  test('continuePay cancel shows a cancel toast', async () => {
    app.payWechatOrder = jest.fn().mockRejectedValue({
      errMsg: 'requestPayment:fail cancel'
    });

    await page.continuePay({
      currentTarget: {
        dataset: {
          sn: 'ORD202608160002'
        }
      }
    });

    expect(wx.showToast).toHaveBeenCalledWith({
      title: '已取消支付',
      icon: 'none'
    });
  });
});
