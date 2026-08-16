App({
  globalData: {
    userInfo: null,
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
    if (userInfo) {
      this.globalData.userInfo = userInfo;
    }
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
    if (this.globalData.userInfo && this.globalData.userInfo.openid) {
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
            data: {
              code: loginRes.code
            },
            success: (res) => {
              const user = res.data && res.data.user ? res.data.user : res.data;
              this.globalData.userInfo = user;
              wx.setStorageSync('userInfo', user);
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

  request(options) {
    const baseUrl = this.globalData.baseUrl;
    wx.request({
      url: baseUrl + options.url,
      method: options.method || 'GET',
      data: options.data,
      header: {
        'content-type': 'application/json'
      },
      success: (res) => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          const message = res.data && res.data.message ? res.data.message : '请求失败';
          wx.showToast({
            title: message,
            icon: 'none'
          });
          if (options.fail) {
            options.fail(res);
          }
          return;
        }
        if (options.success) {
          options.success(res);
        }
      },
      fail: (err) => {
        wx.showToast({
          title: '网络请求失败',
          icon: 'none'
        });
        if (options.fail) {
          options.fail(err);
        }
      }
    });
  }
})
