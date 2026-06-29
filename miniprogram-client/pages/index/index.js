const app = getApp();

Page({
  data: {
    products: [],
    flashProducts: [],
    loading: false,
    stationName: '阳光小区自提点',
    stationAddress: '阳光路123号',
    stations: [],
    selectedStationId: 1,
    showStationPicker: false,
    tempSelectedStation: null,
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
    this.loadStations();
    // 从全局状态中读取保存的自提点
    if (app.globalData.stationId) {
      this.setData({
        selectedStationId: app.globalData.stationId,
        stationName: app.globalData.stationName || '阳光小区自提点',
        stationAddress: app.globalData.stationAddress || '阳光路123号'
      });
    }
  },

  onShow() {
    // 页面显示时刷新数据
    app.updateCartCount();
  },

  loadStations() {
    app.request({
      url: '/client/stations',
      success: (res) => {
        if (res.data && res.data.stations && res.data.stations.length > 0) {
          const stations = res.data.stations;
          // 如果还没选择过的话，默认选第一个
          if (!this.data.selectedStationId) {
            const station = stations[0];
            app.globalData.stationId = station.id;
            app.globalData.stationName = station.station_name;
            app.globalData.stationAddress = station.address;
            this.setData({
              selectedStationId: station.id,
              stationName: station.station_name,
              stationAddress: station.address
            });
          }
          this.setData({ stations: stations });
        }
      }
    });
  },

  // 显示自提点选择器
  showStationPicker() {
    this.setData({
      showStationPicker: true,
      tempSelectedStation: null
    });
  },

  // 隐藏选择器
  hideStationPicker() {
    this.setData({ showStationPicker: false });
  },

  // 选中一个自提点
  selectStation(e) {
    const id = e.currentTarget.dataset.id;
    const name = e.currentTarget.dataset.name;
    const address = e.currentTarget.dataset.address;
    this.setData({
      tempSelectedStation: { id, name, address }
    });
  },

  // 确认选择
  confirmStation() {
    if (this.data.tempSelectedStation) {
      const { id, name, address } = this.data.tempSelectedStation;
      app.globalData.stationId = id;
      app.globalData.stationName = name;
      app.globalData.stationAddress = address;
      this.setData({
        selectedStationId: id,
        stationName: name,
        stationAddress: address,
        showStationPicker: false
      });
    } else {
      this.setData({ showStationPicker: false });
    }
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
