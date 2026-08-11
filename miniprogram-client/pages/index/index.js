const app = getApp();


Page({
  data: {
    products: [],
    flashProducts: [],
    loading: false,
    cartCount: 0,
    cartTotalPrice: '0.00',
    selectedAddress: null,
    searchKeyword: '',
    searchFocused: false,
    displayProducts: [],
    quickNavItems: [
      { id: 1, name: '新鲜蔬菜', icon: '/images/icons/cat-vegetable.svg', bg: '#ffffff', isPhoto: false },
      { id: 2, name: '时令水果', icon: '/images/icons/cat-fruit.svg', bg: '#ffffff', isPhoto: false },
      { id: 3, name: '肉禽蛋奶', icon: '/images/icons/cat-meat.svg', bg: '#ffffff', isPhoto: false },
      { id: 4, name: '海鲜水产', icon: '/images/icons/cat-seafood.svg', bg: '#ffffff', isPhoto: false },
      { id: 5, name: '粮油调味', icon: '/images/icons/cat-grain.svg', bg: '#ffffff', isPhoto: false },
      { id: 6, name: '更多分类', icon: '/images/icons/cat-more.svg', bg: '#ffffff', isPhoto: false }
    ]
  },

  onLoad() {
    this.loadCategories();
    this.loadProducts();
    // 从全局状态中读取保存的地址
    if (app.globalData.selectedAddress) {
      this.setData({ selectedAddress: app.globalData.selectedAddress });
    }
    // 尝试加载地址列表
    this.loadAddresses();
  },

  onShow() {
    // 页面显示时刷新购物车数据
    app.updateCartCount((info) => {
      this.setData({ cartCount: info.count, cartTotalPrice: info.totalPrice });
    });
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

  // 加载分类列表（用后端分类名覆盖 fallback，图标保留本地图片）
  loadCategories() {
    app.request({
      url: '/client/categories',
      success: (res) => {
        const categories = res.data && Array.isArray(res.data.categories)
          ? res.data.categories
          : [];

        if (categories.length === 0) {
          return;
        }

        const fallbackItems = this.data.quickNavItems.slice(0, 5);
        const quickNavItems = fallbackItems.map((fallbackItem, index) => {
          const category = categories[index];
          if (!category) {
            return fallbackItem;
          }

          return {
            id: category.id || fallbackItem.id,
            name: category.name || fallbackItem.name,
            icon: fallbackItem.icon,
            bg: fallbackItem.bg,
            isPhoto: fallbackItem.isPhoto
          };
        });

        quickNavItems.push({ ...this.data.quickNavItems[5] });

        this.setData({ quickNavItems });
      }
    });
  },
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
          const flashProducts = products.slice(0, 4);
          const displayProducts = this.filterProducts(products, this.data.searchKeyword);
          this.setData({
            products: products,
            flashProducts: flashProducts,
            displayProducts: displayProducts
          });
        }
        this.setData({ loading: false });
      },
      fail: () => {
        this.setData({ loading: false });
      }
    });
  },

  filterProducts(products, keyword) {
    const sourceProducts = Array.isArray(products) ? products : [];
    const normalizedKeyword = (keyword || '').trim().toLowerCase();

    if (!normalizedKeyword) {
      return sourceProducts.slice();
    }

    return sourceProducts.filter((product) => {
      const fields = [product.name, product.description, product.category_name];
      return fields.some((field) => String(field || '').toLowerCase().includes(normalizedKeyword));
    });
  },

  updateSearchResults(keyword) {
    const searchKeyword = (keyword || '').trim();
    const displayProducts = this.filterProducts(this.data.products, searchKeyword);
    this.setData({
      searchKeyword,
      displayProducts
    });
  },

  focusSearch() {
    this.setData({ searchFocused: true });
  },

  onSearchInput(e) {
    this.updateSearchResults(e.detail.value);
  },

  onSearchConfirm(e) {
    const keyword = e.detail && e.detail.value ? e.detail.value : '';
    if (!keyword.trim()) {
      wx.showToast({
        title: '请输入搜索关键词',
        icon: 'none'
      });
      return;
    }

    this.updateSearchResults(keyword);
    this.setData({ searchFocused: false });
  },

  onSearchBlur() {
    this.setData({ searchFocused: false });
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
      success: (res) => {
        wx.showToast({
          title: '已加入购物车',
          icon: 'success'
        });
        app.updateCartCount((info) => {
          this.setData({ cartCount: info.count, cartTotalPrice: info.totalPrice });
        });
      }
    });
  },

  goToCheckout() {
    wx.navigateTo({
      url: '/pages/confirm-order/confirm-order'
    });
  }
})
