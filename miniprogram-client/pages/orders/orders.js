const app = getApp();

Page({
  data: {
    orders: [],
    currentTab: 'all'
  },

  onLoad() {
    this.loadOrders();
  },

  onShow() {
    this.loadOrders();
  },

  switchTab(e) {
    this.setData({
      currentTab: e.currentTarget.dataset.tab
    });
    this.loadOrders();
  },

  loadOrders() {
    wx.showLoading({ title: '加载中' });
    app.request({
      url: '/client/orders',
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.orders) {
          this.setData({
            orders: res.data.orders
          });
        }
      },
      fail: () => {
        wx.hideLoading();
      }
    });
  },

  goToDetail(e) {
    const orderSn = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/order-detail/order-detail?sn=${orderSn}`
    });
  }
})
