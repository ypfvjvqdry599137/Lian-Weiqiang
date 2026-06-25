App({
  globalData: {
    userInfo: null,
    cartCount: 0,
    stationId: 1, // 默认自提点ID
    baseUrl: 'http://119.28.159.16:5000' // 服务器地址
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
