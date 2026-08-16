const app = getApp();

Page({
  data: {
    orderSn: '',
    order: null
  },

  onLoad(options) {
    if (options.sn) {
      this.setData({ orderSn: options.sn });
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

  async continuePay() {
    const order = this.data.order;
    if (!order || !order.can_pay) {
      wx.showToast({ title: '当前订单不能支付', icon: 'none' });
      return;
    }

    try {
      await app.payWechatOrder(order.order_sn);
      wx.showToast({
        title: '支付成功',
        icon: 'success'
      });
      setTimeout(() => {
        this.loadOrderDetail(order.order_sn);
      }, 300);
    } catch (error) {
      const errorMessage = error && error.errMsg ? String(error.errMsg) : '';
      if (errorMessage.includes('cancel')) {
        wx.showToast({ title: '已取消支付', icon: 'none' });
        return;
      }
      wx.showToast({ title: '支付失败', icon: 'none' });
    }
  },

  cancelOrder() {
    const order = this.data.order;
    if (!order || !order.can_cancel) {
      wx.showToast({ title: '当前订单不能取消', icon: 'none' });
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
          url: `/client/orders/${order.order_sn}/cancel`,
          method: 'POST',
          success: () => {
            wx.hideLoading();
            wx.showToast({ title: '订单已取消', icon: 'success' });
            this.loadOrderDetail(order.order_sn);
          },
          fail: () => {
            wx.hideLoading();
          }
        });
      }
    });
  },

  goBack() {
    wx.navigateBack();
  }
});
