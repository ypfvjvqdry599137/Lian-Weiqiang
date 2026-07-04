const app = getApp();

Page({
  data: {
    products: [],
    flashProducts: [],
    loading: false,
    selectedAddress: null,
    quickNavItems: [
      { id: 1, name: '新鲜蔬菜', icon: '🥬', bg: '#E8F5E9' },
      { id: 2, name: '时令水果', icon: '🍎', bg: '#FFF3E0' },
      { id: 3, name: '肉禽蛋奶', icon: '🥩', bg: '#FFEBEE' },
      { id: 4, name: '海鲜水产', icon: '🐟', bg: '#E3F2FD' },
      { id: 5, name: '粮油调味', icon: '🌾', bg: '#FFF8E1' },
      { id: 6, name: '更多分类', icon: '📦', bg: '#F3E5F5' }
    ]
  },

  onLoad() {
    this.loadProducts();
    // 从全局状态中读取保存的地址
    if (app.globalData.selectedAddress) {
      this.setData({ selectedAddress: app.globalData.selectedAddress });
    }
    // 尝试加载地址列表
    this.loadAddresses();
  },

  onShow() {
    // 页面显示时刷新数据
    app.updateCartCount();
    // 更新地址信息
    if (app.globalData.selectedAddress) {
      this.setData({ selectedAddress: app.globalData.selectedAddress });
    }
  },

  // 加载地址列表
  loadAddresses() {
    app.request({
      url: '/client/addresses',
      success: (res) => {
        if (res.data && res.data.addresses && res.data.addresses.length > 0) {
          // 优先用默认地址，或者第一个地址
          const address = res.data.addresses.find(a => a.is_default) || res.data.addresses[0];
          app.globalData.selectedAddress = address;
          this.setData({ selectedAddress: address });
        }
      }
    });
  },

  // 点击选择地址
  goToSelectAddress() {
    const selectedId = this.data.selectedAddress ? this.data.selectedAddress.id : '';
    wx.navigateTo({
      url: `/pages/address/address?canSelect=true&selectedId=${selectedId}`
    });
  },

  loadProducts() {
    this.setData({ loading: true });
    app.request({
      url: '/client/products',
      success: (res) => {
        if (res.data && res.data.products) {
          const products = res.data.products;
          // 取前4个作为限时特惠
          const flashProducts = products.slice(0, 4);
          this.setData({
            products: products,
            flashProducts: flashProducts
          });
        }
        this.setData({ loading: false });
      },
      fail: () => {
        this.setData({ loading: false });
      }
    });
  },

  focusSearch() {
    wx.showToast({
      title: '搜索功能开发中',
      icon: 'none'
    });
  },

  goToIndex(e) {
    // 已经在首页了，不需要跳转
  },

  goToCategory(e) {
    wx.redirectTo({
      url: '/pages/category/category'
    });
  },

  goToCart(e) {
    wx.redirectTo({
      url: '/pages/cart/cart'
    });
  },

  goToOrders(e) {
    wx.redirectTo({
      url: '/pages/orders/orders'
    });
  },

  goToDetail(e) {
    const productId = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/product/product?id=${productId}`
    });
  },

  addToCart(e) {
    const productId = e.currentTarget.dataset.id;
    app.request({
      url: '/client/cart',
      method: 'POST',
      data: {
        product_id: productId,
        quantity: 1
      },
      success: (res) => {
        wx.showToast({
          title: '已加入购物车',
          icon: 'success'
        });
        app.updateCartCount();
      }
    });
  }
})
