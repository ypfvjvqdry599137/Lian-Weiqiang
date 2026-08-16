const { loadApp, loadPage } = require('../helpers/loadPage');

function mockRequestByUrl(rules) {
  wx.request.mockImplementation((cfg) => {
    const rule = rules.find((item) => cfg.url.includes(item.match));
    if (!rule) {
      throw new Error('Unexpected request: ' + cfg.url);
    }

    if (rule.fail) {
      if (typeof cfg.fail === 'function') {
        cfg.fail(rule.fail);
      }
      return;
    }

    if (typeof cfg.success === 'function') {
      cfg.success({
        statusCode: rule.statusCode || 200,
        data: rule.data
      });
    }
  });
}

describe('Confirm order page', () => {
  let app;
  let page;

  beforeEach(() => {
    jest.clearAllMocks();
    app = loadApp();
    page = loadPage('pages/confirm-order/confirm-order');
    app.ensureWechatUser = jest.fn().mockResolvedValue({ openid: 'openid-test' });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('onLoad loads cart and delivery data', () => {
    app.globalData.selectedAddress = {
      id: 12,
      lng: '121.4737',
      lat: '31.2304',
      receiver_name: 'Li',
      receiver_phone: '13800000000',
      address: 'Shanghai'
    };

    mockRequestByUrl([
      {
        match: '/client/cart',
        data: {
          cart_items: [{ quantity: 2, item_price: '18.50' }],
          total_price: '18.50'
        }
      },
      {
        match: '/client/delivery-zones',
        data: {
          zones: [{ id: 1, zone_name: 'Central', delivery_fee: '5.00' }]
        }
      },
      {
        match: '/client/delivery/check',
        data: {
          available: true,
          zone_id: 1,
          zone_name: 'Central',
          radius: 3000,
          delivery_fee: '5.00',
          delivery_time: '30 min',
          distance: 1.2
        }
      }
    ]);

    page.onLoad();

    expect(page.data.products).toEqual([{ quantity: 2, item_price: '18.50' }]);
    expect(page.data.deliveryZones).toEqual([{ id: 1, zone_name: 'Central', delivery_fee: '5.00' }]);
    expect(page.data.inRange).toBe(true);
    expect(page.data.deliveryZone.zone_name).toBe('Central');
    expect(page.data.finalPrice).toBe('23.50');
  });

  test('checkDeliveryRange rejects invalid coordinates', () => {
    page.setData({
      selectedAddress: {
        lng: 'None',
        lat: '31.2304'
      },
      totalPrice: '12.00'
    });

    page.checkDeliveryRange();

    expect(wx.showToast).toHaveBeenCalledWith({
      title: '请选择带定位的收货地址',
      icon: 'none'
    });
    expect(page.data.inRange).toBe(false);
    expect(page.data.deliveryZone).toBe(null);
    expect(page.data.finalPrice).toBe('12.00');
  });

  test('submitOrder validates before posting', () => {
    page.setData({ selectedAddress: null });
    page.submitOrder();

    expect(wx.showToast).toHaveBeenCalledWith({
      title: '请先选择收货地址',
      icon: 'none'
    });

    page.setData({
      selectedAddress: {
        id: 9,
        receiver_name: 'Li',
        receiver_phone: '13800000000',
        address: 'Shanghai'
      },
      inRange: false
    });
    page.submitOrder();

    expect(wx.showToast).toHaveBeenCalledWith({
      title: '当前地址不在配送范围内',
      icon: 'none'
    });

    page.setData({
      inRange: true,
      deliveryZone: null
    });
    page.submitOrder();

    expect(wx.showToast).toHaveBeenCalledWith({
      title: '请先选择配送区域',
      icon: 'none'
    });
  });

  test('submitOrder confirm path still calls payOrder and cancel path redirects', () => {
    mockRequestByUrl([
      {
        match: '/client/orders',
        data: { order_sn: 'ORD20260815001' }
      }
    ]);

    page.setData({
      selectedAddress: {
        id: 9,
        receiver_name: 'Li',
        receiver_phone: '13800000000',
        address: 'Shanghai'
      },
      inRange: true,
      deliveryZone: { id: 3 }
    });

    page.payOrder = jest.fn();
    wx.showModal.mockImplementation(({ success }) => {
      success({ confirm: true });
    });

    page.submitOrder();
    expect(page.payOrder).toHaveBeenCalledWith('ORD20260815001');

    wx.showModal.mockImplementation(({ success }) => {
      success({ confirm: false });
    });

    page.payOrder.mockClear();
    page.submitOrder();
    expect(wx.redirectTo).toHaveBeenCalledWith({
      url: '/pages/orders/orders'
    });
    expect(page.payOrder).not.toHaveBeenCalled();
  });

  test('payOrder runs payment flow and redirects on success', async () => {
    jest.useFakeTimers();
    mockRequestByUrl([
      {
        match: '/client/orders/ORD20260815002/wechat-pay',
        data: {
          payment: {
            timeStamp: '1720000000',
            nonceStr: 'nonce',
            package: 'prepay_id=prepay123',
            signType: 'RSA',
            paySign: 'sign'
          }
        }
      },
      {
        match: '/client/orders/ORD20260815002/pay',
        data: {
          message: '支付成功',
          order_status: 20
        }
      }
    ]);

    wx.requestPayment.mockImplementation(({ success }) => {
      success({ errMsg: 'requestPayment:ok' });
    });

    await page.payOrder('ORD20260815002');
    jest.runAllTimers();

    expect(app.ensureWechatUser).toHaveBeenCalledTimes(1);
    expect(wx.requestPayment).toHaveBeenCalledTimes(1);
    expect(wx.showToast).toHaveBeenCalledWith({
      title: '支付成功',
      icon: 'success',
      duration: 2000
    });
    expect(wx.redirectTo).toHaveBeenCalledWith({
      url: '/pages/orders/orders'
    });
  });

  test('payOrder cancel shows a cancel toast', async () => {
    mockRequestByUrl([
      {
        match: '/client/orders/ORD20260815003/wechat-pay',
        data: {
          payment: {
            timeStamp: '1720000000',
            nonceStr: 'nonce',
            package: 'prepay_id=prepay123',
            signType: 'RSA',
            paySign: 'sign'
          }
        }
      }
    ]);

    wx.requestPayment.mockImplementation(({ fail }) => {
      fail({ errMsg: 'requestPayment:fail cancel' });
    });

    await page.payOrder('ORD20260815003');

    expect(wx.showToast).toHaveBeenCalledWith({
      title: '已取消支付',
      icon: 'none'
    });
  });
});
