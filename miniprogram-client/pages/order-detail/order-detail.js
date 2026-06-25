const app = getApp();

Page({
  data: {
    order: null
  },

  onLoad(options) {
    if (options.sn) {
      this.loadOrderDetail(options.sn);
    }
  },

  loadOrderDetail(orderSn) {
    wx.showLoading({ title: '加载中...' });
    app.request({
      url: `/client/orders/${orderSn}`,
      success: (res) => {
        wx.hideLoading();
        if (res.data) {
          this.setData({
            order: res.data
          });
        }
      },
      fail: () => {
        wx.hideLoading();
      }
    });
  },

  goBack() {
    wx.navigateBack();
  }
})
