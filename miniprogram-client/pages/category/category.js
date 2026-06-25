const app = getApp();

Page({
  data: {
    categories: [],
    products: [],
    currentCategory: 0
  },

  onLoad() {
    this.loadCategories();
    this.loadProducts();
  },

  loadCategories() {
    app.request({
      url: '/admin/categories',
      success: (res) => {
        if (res.data && res.data.categories) {
          this.setData({
            categories: res.data.categories
          });
        }
      }
    });
  },

  loadProducts(categoryId) {
    let url = '/client/products';
    if (categoryId) {
      url += `?category_id=${categoryId}`;
    }
    app.request({
      url: url,
      success: (res) => {
        if (res.data && res.data.products) {
          this.setData({
            products: res.data.products
          });
        }
      }
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
  }
})
