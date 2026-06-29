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
    let newQuantity = e.currentTarget.dataset.quantity;
    
    if (newQuantity <= 0) {
      // 删除商品
      this.removeItem(itemId);
      return;
    }

    // 更新数量（这里需要API支持，暂时先模拟，实际项目中应该调用更新接口）
    // 目前我们的API没有直接更新数量的接口，所以我们简化处理：
    // 先删除，再添加
    // 实际项目中应该实现一个PUT /client/cart/:id 接口
    
    // 找到对应商品ID
    const item = this.data.cartItems.find(i => i.id === itemId);
    if (item) {
      // 先加载购物车找到当前product_id
      // 这里简化处理，直接重新加载
      this.loadCart();
    }
  },

  removeItem(itemId) {
    wx.showModal({
      title: '提示',
      content: '确定要删除这个商品吗？',
      success: (res) => {
        if (res.confirm) {
          this.loadCart();
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
      url: '/pages/checkout/checkout'
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
