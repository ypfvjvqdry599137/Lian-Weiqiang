App({
  globalData: {
    userInfo: null,
    authToken: null,
    cartCount: 0,
    cartTotalPrice: '0.00',
    selectedAddress: null, // 默认选中的地址
    baseUrl: 'https://xianpeiju.site' // 您的域名
  },

  onLaunch() {
    this.checkLogin();
  },

  checkLogin() {
    const userInfo = wx.getStorageSync('userInfo');
    const authToken = wx.getStorageSync('authToken');
    if (userInfo && authToken) {
      this.globalData.userInfo = userInfo;
      this.globalData.authToken = authToken;
    } else {
      this.clearAuth();
    }
  },

  clearAuth() {
    this.globalData.userInfo = null;
    this.globalData.authToken = null;
    wx.removeStorageSync('userInfo');
    wx.removeStorageSync('authToken');
  },

  updateCartCount(callback) {
    // ???????????????
    this.request({
      url: '/client/cart',
      success: (res) => {
        if (res.data && res.data.cart_items) {
          let count = 0;
          res.data.cart_items.forEach(item => {
            count += item.quantity;
          });
          this.globalData.cartCount = count;
          this.globalData.cartTotalPrice = res.data.total_price || '0.00';
          if (callback) {
            callback({
              count: this.globalData.cartCount,
              totalPrice: this.globalData.cartTotalPrice
            });
          }
        }
      }
    });
  },

  ensureWechatUser() {
    if (this.globalData.authToken && this.globalData.userInfo) {
      return Promise.resolve(this.globalData.userInfo);
    }

    if (this._wechatLoginPromise) {
      return this._wechatLoginPromise;
    }

    this._wechatLoginPromise = new Promise((resolve, reject) => {
      wx.login({
        success: (loginRes) => {
          if (!loginRes || !loginRes.code) {
            reject(new Error('微信登录失败'));
            return;
          }

          this.request({
            url: '/client/wechat/login',
            method: 'POST',
            auth: false,
            silent: true,
            data: {
              code: loginRes.code
            },
            success: (res) => {
              const user = res.data && res.data.user;
              const token = res.data && res.data.token;
              if (!user || !token) {
                reject(new Error('微信登录未返回有效会话'));
                return;
              }
              this.globalData.userInfo = user;
              this.globalData.authToken = token;
              wx.setStorageSync('userInfo', user);
              wx.setStorageSync('authToken', token);
              resolve(user);
            },
            fail: reject
          });
        },
        fail: reject
      });
    }).finally(() => {
      this._wechatLoginPromise = null;
    });

    return this._wechatLoginPromise;
  },

  async payWechatOrder(orderSn) {
    wx.showLoading({ title: '支付中...' });

    try {
      await this.ensureWechatUser();

      const payment = await new Promise((resolve, reject) => {
        this.request({
          url: `/client/orders/${orderSn}/wechat-pay`,
          method: 'POST',
          success: (res) => {
            const data = res.data || {};
            resolve(data.payment || data);
          },
          fail: reject
        });
      });

      await new Promise((resolve, reject) => {
        wx.requestPayment({
          ...payment,
          success: resolve,
          fail: reject
        });
      });

      return await new Promise((resolve, reject) => {
        this.request({
          url: `/client/orders/${orderSn}/pay`,
          method: 'POST',
          success: (res) => {
            resolve(res.data || res);
          },
          fail: reject
        });
      });
    } finally {
      wx.hideLoading();
    }
  },

  request(options) {
    const baseUrl = this.globalData.baseUrl;
    const method = options.method || 'GET';
    const fullUrl = baseUrl + options.url;
    const isPublic = options.auth === false ||
      /^\/client\/(categories|products(?:\/[^/]+)?|delivery-zones|delivery\/check)(?:\?.*)?$/.test(options.url);

    const fail = (error, message) => {
      if (!options.silent) {
        wx.showToast({ title: message, icon: 'none' });
      }
      if (options.fail) {
        options.fail(error);
      }
    };

    const send = (retried) => {
      const header = {
        'content-type': 'application/json',
        ...(options.header || {})
      };
      if (!isPublic) {
        header.Authorization = `Bearer ${this.globalData.authToken}`;
      }

      wx.request({
        url: fullUrl,
        method,
        data: options.data,
        header,
        success: (res) => {
          if (res.statusCode === 401 && !isPublic && !retried) {
            this.clearAuth();
            this.ensureWechatUser().then(() => send(true)).catch((error) => {
              fail(error, '微信登录失败，请重试');
            });
            return;
          }
          if (res.statusCode < 200 || res.statusCode >= 300) {
            console.error('[wx.request status error]', {
              url: fullUrl,
              method,
              statusCode: res.statusCode,
              response: res.data
            });
            fail(res, res.data && res.data.message ? res.data.message : '请求失败');
            return;
          }
          if (options.success) {
            options.success(res);
          }
        },
        fail: (error) => {
          console.error('[wx.request network fail]', {
            url: fullUrl,
            method,
            errMsg: error && error.errMsg ? error.errMsg : '未知网络错误'
          });
          fail(error, '网络请求失败');
        }
      });
    };

    if (isPublic) {
      send(false);
    } else if (this.globalData.authToken && this.globalData.userInfo) {
      send(false);
    } else {
      this.ensureWechatUser().then(() => send(false)).catch((error) => {
        fail(error, '微信登录失败，请重试');
      });
    }
  }
})
