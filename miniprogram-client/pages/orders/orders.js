const app = getApp();

const TAB_STATUS_MAP = {
  all: null,
  pending: [10, 20, 30, 40],
  completed: [50],
  canceled: [60]
};

Page({
  data: {
    allOrders: [],
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
    this.filterOrders();
  },

  loadOrders() {
    wx.showLoading({ title: '加载中...' });
    app.request({
      url: '/client/orders',
      success: (res) => {
        wx.hideLoading();
        const orders = res.data && res.data.orders ? res.data.orders : [];
        this.setData({ allOrders: orders });
        this.filterOrders();
      },
      fail: () => {
        wx.hideLoading();
      }
    });
  },

  filterOrders() {
    const statusList = TAB_STATUS_MAP[this.data.currentTab];
    const orders = statusList
      ? this.data.allOrders.filter(order => statusList.indexOf(order.order_status) !== -1)
      : this.data.allOrders;

    this.setData({ orders });
  },

  goToDetail(e) {
    const orderSn = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/order-detail/order-detail?sn=${orderSn}`
    });
  },

  cancelOrder(e) {
    const orderSn = e.currentTarget.dataset.sn;
    if (!orderSn) {
      return;
    }

    wx.showModal({
      title: '取消订单',
      content: '确定要取消这个订单吗？',
      confirmText: '取消订单',
      confirmColor: '#e64340',
      success: (modalRes) => {
        if (!modalRes.confirm) {
          return;
        }

        wx.showLoading({ title: '取消中...' });
        app.request({
          url: `/client/orders/${orderSn}/cancel`,
          method: 'POST',
          success: () => {
            wx.hideLoading();
            wx.showToast({ title: '订单已取消', icon: 'success' });
            this.loadOrders();
          },
          fail: () => {
            wx.hideLoading();
          }
        });
      }
    });
  },

  goToIndex() {
    wx.redirectTo({
      url: '/pages/index/index'
    });
  },

  goToCategory() {
    wx.redirectTo({
      url: '/pages/category/category'
    });
  },

  goToCart() {
    wx.redirectTo({
      url: '/pages/cart/cart'
    });
  }
});
