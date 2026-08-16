const { loadApp, loadPage } = require('../helpers/loadPage');

describe('Order detail page', () => {
  let app;
  let page;

  beforeEach(() => {
    jest.clearAllMocks();
    app = loadApp();
    page = loadPage('pages/order-detail/order-detail');
    app.payWechatOrder = jest.fn().mockResolvedValue({
      message: '支付成功',
      order_status: 20
    });
    page.loadOrderDetail = jest.fn();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('continuePay calls the shared payment helper and refreshes the detail view', async () => {
    jest.useFakeTimers();
    page.setData({
      order: {
        order_sn: 'ORD202608160003',
        can_pay: true
      }
    });

    await page.continuePay();

    expect(app.payWechatOrder).toHaveBeenCalledWith('ORD202608160003');
    expect(wx.showToast).toHaveBeenCalledWith({
      title: '支付成功',
      icon: 'success'
    });

    jest.runAllTimers();
    expect(page.loadOrderDetail).toHaveBeenCalledWith('ORD202608160003');
  });

  test('continuePay cancel shows a cancel toast', async () => {
    app.payWechatOrder = jest.fn().mockRejectedValue({
      errMsg: 'requestPayment:fail cancel'
    });
    page.setData({
      order: {
        order_sn: 'ORD202608160004',
        can_pay: true
      }
    });

    await page.continuePay();

    expect(wx.showToast).toHaveBeenCalledWith({
      title: '已取消支付',
      icon: 'none'
    });
  });
});
