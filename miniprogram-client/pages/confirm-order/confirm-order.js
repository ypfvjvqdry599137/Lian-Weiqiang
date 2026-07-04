const app = getApp();

Page({
  data: {
    products: [],
    totalPrice: '0.00',
    selectedAddress: null,
    deliveryZones: [],
    deliveryZone: null,
    inRange: false,
    remark: '',
    finalPrice: '0.00'
  },

  onLoad() {
    this.loadCart();
    this.loadDeliveryZones();
    // 检查全局地址
    if (app.globalData.selectedAddress) {
      this.setData({ selectedAddress: app.globalData.selectedAddress });
      this.checkDeliveryRange();
    }
  },

  onShow() {
    // 更新地址
    if (app.globalData.selectedAddress) {
      this.setData({ selectedAddress: app.globalData.selectedAddress });
      this.checkDeliveryRange();
    }
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
          this.calculateFinalPrice();
        }
      },
      fail: () => {
        wx.hideLoading();
      }
    });
  },

  loadDeliveryZones() {
    app.request({
      url: '/client/delivery-zones',
      success: (res) => {
        if (res.data && res.data.zones) {
          this.setData({ deliveryZones: res.data.zones });
          // 如果已经有地址，检查配送范围
          if (this.data.selectedAddress) {
            this.checkDeliveryRange();
          }
        }
      }
    });
  },

  // 检查配送范围，找到最近的配送区
  checkDeliveryRange() {
    if (!this.data.selectedAddress || this.data.deliveryZones.length === 0) {
      return;
    }

    const addr = this.data.selectedAddress;
    if (!addr.lng || !addr.lat) {
      // 如果没有经纬度，默认选择第一个
      const firstZone = this.data.deliveryZones[0];
      this.setData({
        deliveryZone: firstZone,
        inRange: true
      });
      this.calculateFinalPrice();
      return;
    }

    // 计算距离，找到最近的配送区
    let nearestZone = null;
    let nearestDistance = Infinity;

    for (const zone of this.data.deliveryZones) {
      if (!zone.center_lng || !zone.center_lat) continue;

      const distance = this.getDistance(
        parseFloat(addr.lat), parseFloat(addr.lng),
        parseFloat(zone.center_lat), parseFloat(zone.center_lng)
      );

      const radius = zone.radius || 3000; // 默认3公里

      if (distance <= radius && distance < nearestDistance) {
        nearestDistance = distance;
        nearestZone = zone;
      }
    }

    this.setData({
      deliveryZone: nearestZone,
      inRange: !!nearestZone
    });

    this.calculateFinalPrice();
  },

  // 计算两点之间距离（米）
  getDistance(lat1, lng1, lat2, lng2) {
    const radLat1 = lat1 * Math.PI / 180.0;
    const radLat2 = lat2 * Math.PI / 180.0;
    const a = radLat1 - radLat2;
    const b = lng1 * Math.PI / 180.0 - lng2 * Math.PI / 180.0;

    let s = 2 * Math.asin(Math.sqrt(Math.pow(Math.sin(a / 2), 2) +
      Math.cos(radLat1) * Math.cos(radLat2) * Math.pow(Math.sin(b / 2), 2)));
    s = s * 6378137.0;
    s = Math.round(s * 10000) / 10000;
    return s;
  },

  // 计算最终价格
  calculateFinalPrice() {
    const totalPrice = parseFloat(this.data.totalPrice || '0');
    const deliveryFee = this.data.deliveryZone ? parseFloat(this.data.deliveryZone.delivery_fee || '0') : 0;
    const final = (totalPrice + deliveryFee).toFixed(2);
    this.setData({ finalPrice: final });
  },

  goToSelectAddress() {
    const selectedId = this.data.selectedAddress ? this.data.selectedAddress.id : '';
    wx.navigateTo({
      url: `/pages/address/address?canSelect=true&selectedId=${selectedId}`
    });
  },

  onRemarkInput(e) {
    this.setData({ remark: e.detail.value });
  },

  submitOrder() {
    if (!this.data.selectedAddress) {
      wx.showToast({ title: '请先选择收货地址', icon: 'none' });
      return;
    }
    if (!this.data.inRange) {
      wx.showToast({ title: '当前地址不在配送范围内', icon: 'none' });
      return;
    }
    if (!this.data.deliveryZone) {
      wx.showToast({ title: '请先选择配送区域', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '提交中...' });

    app.request({
      url: '/client/orders',
      method: 'POST',
      data: {
        zone_id: this.data.deliveryZone.id,
        address_id: this.data.selectedAddress.id,
        receiver_name: this.data.selectedAddress.receiver_name,
        receiver_phone: this.data.selectedAddress.receiver_phone,
        receiver_address: this.data.selectedAddress.address,
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
                wx.redirectTo({
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
          wx.redirectTo({
            url: '/pages/orders/orders'
          });
        }, 2000);
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '支付失败', icon: 'none' });
      }
    });
  }
})
