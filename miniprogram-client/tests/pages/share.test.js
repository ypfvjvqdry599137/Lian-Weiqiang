const fs = require('fs');
const path = require('path');
const { loadPage } = require('../helpers/loadPage');

const projectRoot = path.resolve(__dirname, '../..');

describe('Public page sharing', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('home shares a public landing page with a local cover, not address data', () => {
    const page = loadPage('pages/index/index');
    page.setData({ selectedAddress: { receiver_name: 'Private Name', receiver_phone: '13800000000' } });

    expect(page.onShareAppMessage()).toEqual({
      title: '鲜配居，新鲜食材送到家',
      path: '/pages/index/index',
      imageUrl: '/images/categories/cat-vegetable.jpg'
    });
    expect(page.onShareTimeline()).toEqual({
      title: '鲜配居，新鲜食材送到家',
      imageUrl: '/images/categories/cat-vegetable.jpg'
    });
    expect(fs.existsSync(path.join(projectRoot, 'images/categories/cat-vegetable.jpg'))).toBe(true);
    page.onShow();
    expect(wx.showShareMenu).toHaveBeenCalledWith({
      menus: ['shareAppMessage', 'shareTimeline']
    });
    expect(fs.readFileSync(path.join(projectRoot, 'pages/index/index.wxml'), 'utf8'))
      .not.toContain('open-type="share"');
  });

  test('product shares the loaded product and its public image', () => {
    const page = loadPage('pages/product/product');
    page.setData({
      productId: '42',
      product: { id: 42, name: '新鲜番茄', image_url: 'https://xianpeiju.site/uploads/tomato.jpg' }
    });

    expect(page.onShareAppMessage()).toEqual({
      title: '新鲜番茄 - 鲜配居',
      path: '/pages/product/product?id=42',
      imageUrl: 'https://xianpeiju.site/uploads/tomato.jpg'
    });
    expect(page.onShareTimeline()).toEqual({
      title: '新鲜番茄 - 鲜配居',
      query: 'id=42',
      imageUrl: 'https://xianpeiju.site/uploads/tomato.jpg'
    });
    expect(fs.readFileSync(path.join(projectRoot, 'pages/product/product.wxml'), 'utf8'))
      .not.toContain('open-type="share"');
  });

  test('missing product shares home instead of a broken detail link', () => {
    const page = loadPage('pages/product/product');
    expect(page.onShareAppMessage().path).toBe('/pages/index/index');
    page.setData({ productId: '42', product: { id: 42, image_url: 'http://example.com/image.jpg' } });
    expect(page.onShareAppMessage().imageUrl).toBe('/images/categories/cat-vegetable.jpg');
  });

  test('shared category opens the selected product list', () => {
    const page = loadPage('pages/category/category');
    const app = getApp();
    app.request = jest.fn();

    page.onLoad({ categoryId: '12' });
    expect(app.request.mock.calls[0][0].url).toContain('category_id=12');
    app.request.mock.calls[1][0].success({
      data: { categories: [{ id: 12, name: '新鲜蔬菜' }, { id: 13, name: '时令水果' }] }
    });
    expect(page.data.currentCategory).toBe(1);
    expect(page.onShareAppMessage()).toEqual({
      title: '新鲜蔬菜 - 鲜配居',
      path: '/pages/category/category?categoryId=12',
      imageUrl: '/images/categories/cat-vegetable.jpg'
    });
    expect(page.onShareTimeline().query).toBe('categoryId=12');
    page.onShow();
    expect(wx.showShareMenu).toHaveBeenCalled();
  });

  test('private pages hide forwarding controls', () => {
    const privatePages = [
      'pages/cart/cart',
      'pages/address/address',
      'pages/confirm-order/confirm-order',
      'pages/orders/orders',
      'pages/order-detail/order-detail'
    ];
    getApp().globalData.selectedAddress = null;
    for (const pagePath of privatePages) {
      const page = loadPage(pagePath);
      page.onShow();
      expect(wx.hideShareMenu).toHaveBeenLastCalledWith({
        menus: ['shareAppMessage', 'shareTimeline']
      });
      expect(page.onShareAppMessage).toBeUndefined();
    }
    expect(wx.showShareMenu).not.toHaveBeenCalled();
  });
});
