const app = getApp();

Page({
  data: {
    products: [],
    totalPrice: '0.00',
    stationName: '阳光小区自提点',
    stationAddress: '阳光路123号',
    selectedTime: '',
    timeSlots: ['今天 16:00-18:00', '今天 18:00-20:00', '明天 09:00-11:00', '明天 16:00-18:00', '明天 18:00-20:00'],
    receiverName: '',
    receiverPhone: '',
    remark: ''
  },

  onLoad() {
    this.loadCart();
  },

  loadCart() {
    wx.showLoading({ title: '加载中' });
    app.request({
      url: '/client/cart',
      success: (res) => {
        wx.hideLoading();
        if (res.data) {
          this.setData({
            products: res.data.cart_items || [],
            totalPrice: res.data.total_price || '0.00'
          });
        }
      },
      fail: () => {
        wx.hideLoading();
      }
    });
  },

  onTimeChange(e) {
    this.setData({
      selectedTime: this.data.timeSlots[e.detail.value]
    });
  },

  onNameInput(e) {
    this.setData({ receiverName: e.detail.value });
  },

  onPhoneInput(e) {
    this.setData({ receiverPhone: e.detail.value });
  },

  onRemarkInput(e) {
    this.setData({ remark: e.detail.value });
  },

  submitOrder() {
    if (!this.data.receiverName) {
      wx.showToast({ title: '请填写收货人姓名', icon: 'none' });
      return;
    }
    if (!this.data.receiverPhone) {
      wx.showToast({ title: '请填写手机号', icon: 'none' });
      return;
    }
    if (!this.data.selectedTime) {
      wx.showToast({ title: '请选择自提时间', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '提交中...' });
    
    app.request({
      url: '/client/orders',
      method: 'POST',
      data: {
        station_id: 1,
        pickup_time: this.data.selectedTime,
        receiver_name: this.data.receiverName,
        receiver_phone: this.data.receiverPhone,
        remark: this.data.remark
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.order_sn) {
          const orderSn = res.data.order_sn;
          wx.showModal({
            title: '订单提交成功',
            content: '是否立即支付？',
            success: (modalRes) => {
              if (modalRes.confirm) {
                this.payOrder(orderSn);
              } else {
                wx.switchTab({
                  url: '/pages/orders/orders'
                });
              }
            }
          });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '订单提交失败', icon: 'none' });
      }
    });
  },

  payOrder(orderSn) {
    wx.showLoading({ title: '支付中...' });
    
    app.request({
      url: `/client/orders/${orderSn}/pay`,
      method: 'POST',
      success: (res) => {
        wx.hideLoading();
        wx.showToast({
          title: '支付成功',
          icon: 'success',
          duration: 2000
        });
        setTimeout(() => {
          wx.navigateTo({
            url: '/pages/orders/orders'
          });
        }, 2000);
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '支付失败', icon: 'none' });
      }
    });
  },

  goBack() {
    wx.navigateBack();
  }
})
