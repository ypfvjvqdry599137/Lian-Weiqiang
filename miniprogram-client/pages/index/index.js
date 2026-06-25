const app = getApp();

Page({
  data: {
    products: [],
    recommendProducts: [],
    loading: false,
    stationName: '阳光小区自提点',
    stationAddress: '阳光路123号'
  },

  onLoad() {
    this.loadProducts();
    this.loadStations();
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
          const station = res.data.stations[0];
          this.setData({
            stationName: station.station_name,
            stationAddress: station.address
          });
        }
      }
    });
  },

  loadProducts() {
    this.setData({ loading: true });
    app.request({
      url: '/client/products',
      success: (res) => {
        if (res.data && res.data.products) {
          const products = res.data.products;
          const recommendProducts = products.filter(p => p.is_recommend);
          this.setData({
            products: products,
            recommendProducts: recommendProducts
          });
        }
        this.setData({ loading: false });
      },
      fail: () => {
        this.setData({ loading: false });
      }
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
