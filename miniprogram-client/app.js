App({
  globalData: {
    userInfo: null,
    cartCount: 0,
    selectedAddress: null, // 默认选中的地址
    baseUrl: 'http://xianpeiju.site' // 您的域名
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

  updateCartCount() {
    // 更新购物车数量
    this.request({
      url: '/client/cart',
      success: (res) => {
        if (res.data && res.data.cart_items) {
          let count = 0;
          res.data.cart_items.forEach(item => {
            count += item.quantity;
          });
          this.globalData.cartCount = count;
          // 可以在这里设置tabbar的badge
        }
      }
    });
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
