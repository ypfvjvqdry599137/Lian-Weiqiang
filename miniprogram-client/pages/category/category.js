const app = getApp();

Page({
  data: {
    categories: [],
    products: [],
    currentCategory: 0,
    hasMore: true,
    loadingProducts: false,
    productsError: false
  },

  onLoad() {
    this.loadCategories();
    this.loadProducts();
  },

  loadCategories() {
    app.request({
      url: '/client/categories',
      success: (res) => {
        if (res.data && res.data.categories) {
          this.setData({
            categories: [{ id: 0, name: '全部' }, ...res.data.categories]
          });
        }
      }
    });
  },

  loadProducts(categoryId) {
    this._productRequestVersion = (this._productRequestVersion || 0) + 1;
    this._activeCategoryId = categoryId || null;
    this._nextPage = 1;
    this.setData({ products: [], hasMore: true, loadingProducts: false, productsError: false });
    this.loadNextProducts();
  },

  loadNextProducts() {
    if (this.data.loadingProducts || !this.data.hasMore) return;

    const version = this._productRequestVersion;
    const page = this._nextPage;
    const categoryId = this._activeCategoryId;
    const url = `/client/products?page=${page}&page_size=20` +
      (categoryId ? `&category_id=${categoryId}` : '');
    this.setData({ loadingProducts: true, productsError: false });
    app.request({
      url,
      success: (res) => {
        if (version !== this._productRequestVersion) return;
        const batch = res.data && res.data.products;
        if (!Array.isArray(batch)) {
          this.setData({ loadingProducts: false, productsError: true });
          return;
        }
        this._nextPage = page + 1;
        const seen = new Set(this.data.products.map(product => product.id));
        const newProducts = batch.filter(product => !seen.has(product.id));
        this.setData({
          products: this.data.products.concat(newProducts),
          hasMore: res.data.has_more === true,
          loadingProducts: false
        });
      },
      fail: () => {
        if (version === this._productRequestVersion) {
          this.setData({ loadingProducts: false, productsError: true });
        }
      }
    });
  },

  onProductsScrollToLower() {
    this.loadNextProducts();
  },

  retryLoadProducts() {
    this.loadNextProducts();
  },

  onProductImageError(e) {
    const id = Number(e.currentTarget.dataset.id);
    const failedUrl = e.currentTarget.dataset.imageUrl;
    this.setData({
      products: this.data.products.map(product =>
        product.id === id ? {
          ...product,
          imageError: true,
          imageUnavailable: failedUrl === product.image_url
        } : product)
    });
  },

  selectCategory(e) {
    const index = e.currentTarget.dataset.index;
    const category = this.data.categories[index];
    this.setData({
      currentCategory: index
    });
    this.loadProducts(category ? category.id : null);
  },

  addToCart(e) {
    const productId = e.currentTarget.dataset.id;
    const hasProcessing = e.currentTarget.dataset.hasProcessing === true || e.currentTarget.dataset.hasProcessing === 'true';

    if (hasProcessing) {
      wx.navigateTo({
        url: '/pages/product/product?id=' + productId
      });
      return;
    }

    app.request({
      url: '/client/cart',
      method: 'POST',
      data: {
        product_id: productId,
        quantity: 1
      },
      success: () => {
        wx.showToast({ title: '已加入购物车', icon: 'success' });
        app.updateCartCount();
      }
    });
  },
  goToDetail(e) {
    const productId = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/product/product?id=${productId}`
    });
  },

  goToIndex(e) {
    wx.redirectTo({
      url: '/pages/index/index'
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
  }
})
