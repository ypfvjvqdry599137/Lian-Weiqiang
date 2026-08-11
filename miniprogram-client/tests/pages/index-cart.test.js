/**
 * 首页 - 购物车按钮交互逻辑测试
 * 覆盖：addToCart、goToCart、goToCheckout、onShow 刷新购物车
 */
const { loadPage, loadApp } = require('../helpers/loadPage');

/**
 * 让 wx.request 返回成功响应的辅助函数
 * app.request 内部调用 wx.request，通过 mock wx.request 触发 success 回调链
 */
function mockWxRequestSuccess(data) {
  wx.request.mockImplementation((cfg) => {
    cfg.success({ statusCode: 200, data });
  });
}

describe('首页 - 购物车按钮', () => {
  let page;
  let app;

  beforeEach(() => {
    app = loadApp();
    page = loadPage('pages/index/index');
  });

  describe('addToCart 加购行为', () => {
    beforeEach(() => {
      // 所有 wx.request 都返回购物车数据（addToCart 不读 data，updateCartCount 读）
      mockWxRequestSuccess({
        cart_items: [{ quantity: 2 }],
        total_price: '19.80'
      });
    });

    test('点击加购应调用 app.request 发起 POST /client/cart', () => {
      page.addToCart({ currentTarget: { dataset: { id: 42 } } });
      expect(wx.request).toHaveBeenCalled();
      const callArg = wx.request.mock.calls[0][0];
      expect(callArg.url).toContain('/client/cart');
      expect(callArg.method).toBe('POST');
    });

    test('加购请求体包含正确的 product_id 和 quantity', () => {
      page.addToCart({ currentTarget: { dataset: { id: 99 } } });
      const callArg = wx.request.mock.calls[0][0];
      expect(callArg.data).toEqual({ product_id: 99, quantity: 1 });
    });

    test('加购成功后应弹出"已加入购物车"提示', () => {
      page.addToCart({ currentTarget: { dataset: { id: 42 } } });
      expect(wx.showToast).toHaveBeenCalledWith({
        title: '已加入购物车',
        icon: 'success'
      });
    });

    test('加购成功后应调用 app.updateCartCount 刷新购物车数量', () => {
      page.addToCart({ currentTarget: { dataset: { id: 42 } } });
      // updateCartCount 内部会再发一次 GET /client/cart
      // 所以 wx.request 至少被调用 2 次（加购 + 刷新）
      expect(wx.request.mock.calls.length).toBeGreaterThanOrEqual(2);
      const refreshCall = wx.request.mock.calls[1][0];
      expect(refreshCall.url).toContain('/client/cart');
      expect(refreshCall.method).toBe('GET'); // updateCartCount 不传 method，默认 GET
    });

    test('刷新后应 setData 更新 cartCount 和 cartTotalPrice', () => {
      page.addToCart({ currentTarget: { dataset: { id: 42 } } });
      // setData 至少被调用一次，且某次包含 cartCount
      const setDataCalls = page.setData.mock.calls.map((c) => c[0]);
      const hasCartCount = setDataCalls.some((d) => 'cartCount' in d);
      expect(hasCartCount).toBe(true);
      // 最终 data 里的值应为 mock 返回的 2 和 19.80
      expect(page.data.cartCount).toBe(2);
      expect(page.data.cartTotalPrice).toBe('19.80');
    });
  });

  describe('goToCart 跳转购物车页', () => {
    test('应调用 wx.redirectTo 到 /pages/cart/cart', () => {
      page.goToCart({});
      expect(wx.redirectTo).toHaveBeenCalledTimes(1);
      expect(wx.redirectTo).toHaveBeenCalledWith({
        url: '/pages/cart/cart'
      });
    });

    test('不应使用 navigateTo（购物车是 tab 级页面，用 redirectTo 替换）', () => {
      page.goToCart({});
      expect(wx.navigateTo).not.toHaveBeenCalled();
    });
  });

  describe('goToCheckout 跳转结算页', () => {
    test('应调用 wx.navigateTo 到 /pages/confirm-order/confirm-order', () => {
      page.goToCheckout();
      expect(wx.navigateTo).toHaveBeenCalledTimes(1);
      expect(wx.navigateTo).toHaveBeenCalledWith({
        url: '/pages/confirm-order/confirm-order'
      });
    });

    test('不应使用 redirectTo（保留首页在页面栈中，便于返回）', () => {
      page.goToCheckout();
      expect(wx.redirectTo).not.toHaveBeenCalled();
    });
  });

  describe('onShow 刷新购物车数据', () => {
    test('页面显示时应调用 app.updateCartCount', () => {
      // updateCartCount 内部走 app.request → wx.request
      mockWxRequestSuccess({ cart_items: [], total_price: '0.00' });
      page.onShow();
      expect(wx.request).toHaveBeenCalled();
      const callArg = wx.request.mock.calls[0][0];
      expect(callArg.url).toContain('/client/cart');
    });

    test('刷新到数据后应 setData 更新 cartCount 和 cartTotalPrice', () => {
      mockWxRequestSuccess({
        cart_items: [{ quantity: 1 }, { quantity: 4 }],
        total_price: '58.60'
      });
      page.onShow();
      expect(page.data.cartCount).toBe(5);
      expect(page.data.cartTotalPrice).toBe('58.60');
    });

    test('购物车为空时应更新为 0 数量和 0.00 金额', () => {
      mockWxRequestSuccess({ cart_items: [], total_price: '0.00' });
      page.onShow();
      expect(page.data.cartCount).toBe(0);
      expect(page.data.cartTotalPrice).toBe('0.00');
    });
  });

  describe('cart-bar 显示条件', () => {
    test('cartCount 为 0 时不显示购物车悬浮条（由 wxml wx:if 控制，此处验证数据初值）', () => {
      const freshPage = loadPage('pages/index/index');
      expect(freshPage.data.cartCount).toBe(0);
    });

    test('加购后 cartCount > 0 满足显示条件', () => {
      mockWxRequestSuccess({
        cart_items: [{ quantity: 3 }],
        total_price: '29.90'
      });
      page.addToCart({ currentTarget: { dataset: { id: 1 } } });
      expect(page.data.cartCount).toBeGreaterThan(0);
    });
  });
});
