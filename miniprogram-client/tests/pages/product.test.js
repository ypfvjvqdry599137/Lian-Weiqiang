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

describe('Product page', () => {
  let app;
  let page;

  beforeEach(() => {
    jest.clearAllMocks();
    app = loadApp();
    page = loadPage('pages/product/product');
    app.updateCartCount = jest.fn();
  });

  test('onLoad without id shows an error and does not request data', () => {
    page.onLoad({});

    expect(wx.showToast).toHaveBeenCalledWith({
      title: '商品不存在',
      icon: 'none'
    });
    expect(wx.request).not.toHaveBeenCalled();
  });

  test('loadProduct hydrates product state and updates the title', () => {
    mockRequestByUrl([
      {
        match: '/client/products/42',
        data: {
          id: 42,
          name: 'Fresh Cabbage',
          available_stock: 8,
          processing_options: ['切片', '整颗']
        }
      }
    ]);

    page.loadProduct(42);

    expect(page.data.loading).toBe(false);
    expect(page.data.product.id).toBe(42);
    expect(page.data.hasProcessingOptions).toBe(true);
    expect(page.data.processingOptions).toEqual(['切片', '整颗']);
    expect(page.data.selectedProcessingOption).toBe('切片');
    expect(wx.setNavigationBarTitle).toHaveBeenCalledWith({
      title: 'Fresh Cabbage'
    });
  });

  test('loadProduct missing payload shows a failure toast', () => {
    mockRequestByUrl([
      {
        match: '/client/products/404',
        data: {}
      }
    ]);

    page.loadProduct(404);

    expect(wx.showToast).toHaveBeenCalledWith({
      title: '商品加载失败',
      icon: 'none'
    });
    expect(page.data.loading).toBe(false);
  });

  test('increaseQuantity and decreaseQuantity respect stock and minimum quantity', () => {
    page.setData({
      product: { available_stock: 3 },
      quantity: 3
    });

    page.increaseQuantity();

    expect(wx.showToast).toHaveBeenCalledWith({
      title: '库存不足',
      icon: 'none'
    });
    expect(page.data.quantity).toBe(3);

    page.setData({ quantity: 2 });
    page.decreaseQuantity();
    expect(page.data.quantity).toBe(1);

    page.decreaseQuantity();
    expect(page.data.quantity).toBe(1);
  });

  test('addToCart posts the product payload and refreshes the cart count', () => {
    mockRequestByUrl([
      {
        match: '/client/cart',
        data: {
          cart_items: [{ quantity: 2 }],
          total_price: '19.80'
        }
      }
    ]);

    page.setData({
      product: {
        id: 77
      },
      quantity: 2,
      hasProcessingOptions: true,
      processingOptions: ['切片', '整颗'],
      selectedProcessingOption: '整颗'
    });

    page.addToCart();

    const requestCall = wx.request.mock.calls[0][0];
    expect(requestCall.method).toBe('POST');
    expect(requestCall.url).toContain('/client/cart');
    expect(requestCall.data).toEqual({
      product_id: 77,
      quantity: 2,
      processing_option: '整颗'
    });
    expect(wx.showToast).toHaveBeenCalledWith({
      title: '已加入购物车',
      icon: 'success'
    });
    expect(app.updateCartCount).toHaveBeenCalledTimes(1);
  });

  test('buyNow posts the product payload and navigates to checkout', () => {
    mockRequestByUrl([
      {
        match: '/client/cart',
        data: {
          cart_items: [{ quantity: 1 }],
          total_price: '9.90'
        }
      }
    ]);

    page.setData({
      product: {
        id: 88
      },
      quantity: 1,
      hasProcessingOptions: false
    });

    page.buyNow();

    const requestCall = wx.request.mock.calls[0][0];
    expect(requestCall.method).toBe('POST');
    expect(requestCall.data).toEqual({
      product_id: 88,
      quantity: 1,
      processing_option: ''
    });
    expect(app.updateCartCount).toHaveBeenCalledTimes(1);
    expect(wx.navigateTo).toHaveBeenCalledWith({
      url: '/pages/confirm-order/confirm-order'
    });
  });
});
