const app = getApp();

Page({
  data: {
    cartItems: [],
    totalPrice: '0.00',
    totalQuantity: 0
  },

  onLoad() {
    this.loadCart();
  },

  onShow() {
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
            cartItems: res.data.cart_items || [],
            totalPrice: res.data.total_price || '0.00'
          });
          this.calculateTotal();
        }
      },
      fail: () => {
        wx.hideLoading();
      }
    });
  },

  calculateTotal() {
    let total = 0;
    let quantity = 0;
    this.data.cartItems.forEach(item => {
      total += parseFloat(item.item_price) || 0;
      quantity += item.quantity || 0;
    });
    this.setData({
      totalPrice: total.toFixed(2),
      totalQuantity: quantity
    });
  },

  updateQuantity(e) {
    const itemId = e.currentTarget.dataset.id;
    const newQuantity = parseInt(e.currentTarget.dataset.quantity);
    
    if (newQuantity <= 0) {
      // 删除商品
      this.removeItem(itemId);
      return;
    }

    app.request({
      url: `/client/cart/${itemId}`,
      method: 'PUT',
      data: {
        quantity: newQuantity
      },
      success: () => {
        this.loadCart();
        app.updateCartCount();
      }
    });
  },

  removeItem(itemId) {
    wx.showModal({
      title: '提示',
      content: '确定要删除这个商品吗？',
      success: (res) => {
        if (res.confirm) {
          app.request({
            url: `/client/cart/${itemId}`,
            method: 'DELETE',
            success: () => {
              wx.showToast({ title: '已删除', icon: 'success' });
              this.loadCart();
              app.updateCartCount();
            }
          });
        }
      }
    });
  },

  goShopping() {
    wx.navigateBack({ delta: 1 });
  },

  goCheckout() {
    if (this.data.cartItems.length === 0) {
      wx.showToast({
        title: '购物车是空的',
        icon: 'none'
      });
      return;
    }
    wx.navigateTo({
      url: '/pages/confirm-order/confirm-order'
    });
  },

  goToIndex(e) {
    wx.redirectTo({
      url: '/pages/index/index'
    });
  },

  goToCategory(e) {
    wx.redirectTo({
      url: '/pages/category/category'
    });
  },

  goToOrders(e) {
    wx.redirectTo({
      url: '/pages/orders/orders'
    });
  }
})
