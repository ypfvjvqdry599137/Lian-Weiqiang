const { loadApp } = require('./helpers/loadPage');

function flushPromises() {
  return new Promise((resolve) => setImmediate(resolve));
}

describe('App authenticated requests', () => {
  let app;

  beforeEach(() => {
    app = loadApp();
    wx.request.mockReset();
    wx.login.mockReset();
    wx.showToast.mockReset();
  });

  test('cached session sends bearer token for private routes only', () => {
    wx.request.mockImplementation(({ success }) => success({ statusCode: 200, data: {} }));
    app.request({ url: '/client/orders' });
    app.request({ url: '/client/products' });
    expect(wx.request.mock.calls[0][0].header.Authorization).toBe('Bearer test-client-token');
    expect(wx.request.mock.calls[1][0].header.Authorization).toBeUndefined();
  });

  test('new session logs in before requesting private data', async () => {
    app.clearAuth();
    wx.login.mockImplementation(({ success }) => success({ code: 'wechat-code' }));
    wx.request.mockImplementation(({ url, success, header }) => {
      if (url.endsWith('/client/wechat/login')) {
        expect(header.Authorization).toBeUndefined();
        success({ statusCode: 200, data: { user: { id: 7, openid: 'openid-7' }, token: 'new-token' } });
      } else {
        expect(header.Authorization).toBe('Bearer new-token');
        success({ statusCode: 200, data: { orders: [] } });
      }
    });
    const onSuccess = jest.fn();
    app.request({ url: '/client/orders', success: onSuccess });
    await flushPromises();
    expect(onSuccess).toHaveBeenCalledTimes(1);
    expect(wx.request.mock.calls.map(([request]) => request.url)).toEqual([
      'https://xianpeiju.site/client/wechat/login',
      'https://xianpeiju.site/client/orders'
    ]);
  });

  test('expired session retries once with a fresh login', async () => {
    wx.login.mockImplementation(({ success }) => success({ code: 'renew-code' }));
    wx.request.mockImplementation(({ url, success, header }) => {
      if (url.endsWith('/client/wechat/login')) {
        success({ statusCode: 200, data: { user: { id: 7 }, token: 'renewed-token' } });
      } else if (header.Authorization === 'Bearer test-client-token') {
        success({ statusCode: 401, data: {} });
      } else {
        success({ statusCode: 200, data: { orders: [] } });
      }
    });
    const onSuccess = jest.fn();
    app.request({ url: '/client/orders', success: onSuccess });
    await flushPromises();
    expect(onSuccess).toHaveBeenCalledTimes(1);
    expect(wx.request).toHaveBeenCalledTimes(3);
    expect(app.globalData.authToken).toBe('renewed-token');
  });
});
