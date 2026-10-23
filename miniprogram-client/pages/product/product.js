const app = getApp();
const { HOME_TITLE, SHARE_COVER, showPublicShareMenu } = require('../../utils/share');

Page({
  data: {
    productId: null,
    product: null,
    quantity: 1,
    loading: false,
    processingOptions: [],
    selectedProcessingOption: '',
    hasProcessingOptions: false
  },

  onLoad(options) {
    if (!options.id) {
      wx.showToast({ title: '商品不存在', icon: 'none' });
      return;
    }
    this.setData({ productId: options.id });
    this.loadProduct(options.id);
  },

  onShow() {
    showPublicShareMenu();
  },

  loadProduct(productId) {
    this.setData({ loading: true });
    app.request({
      url: '/client/products/' + productId,
      success: (res) => {
        if (res.data && res.data.id) {
          const processingOptions = Array.isArray(res.data.processing_options)
            ? res.data.processing_options
            : [];

          this.setData({
            product: res.data,
            processingOptions: processingOptions,
            hasProcessingOptions: processingOptions.length > 0,
            selectedProcessingOption: processingOptions[0] || ''
          });
          wx.setNavigationBarTitle({ title: res.data.name || '商品详情' });
        } else {
          wx.showToast({ title: '商品加载失败', icon: 'none' });
        }
        this.setData({ loading: false });
      },
      fail: () => {
        this.setData({ loading: false });
      }
    });
  },

  onProductImageError() {
    if (this.data.product) {
      this.setData({ product: { ...this.data.product, imageError: true } });
    }
  },

  selectProcessingOption(e) {
    const option = e.currentTarget.dataset.option || '';
    this.setData({ selectedProcessingOption: option });
  },

  decreaseQuantity() {
    if (this.data.quantity <= 1) return;
    this.setData({ quantity: this.data.quantity - 1 });
  },

  increaseQuantity() {
    const availableStock = this.data.product ? this.data.product.available_stock : 0;
    if (availableStock && this.data.quantity >= availableStock) {
      wx.showToast({ title: '库存不足', icon: 'none' });
      return;
    }
    this.setData({ quantity: this.data.quantity + 1 });
  },

  getProcessingOption() {
    if (!this.data.hasProcessingOptions) {
      return '';
    }
    return this.data.selectedProcessingOption || this.data.processingOptions[0] || '';
  },

  addToCart() {
    if (!this.data.product) return;

    const processingOption = this.getProcessingOption();
    if (this.data.hasProcessingOptions && !processingOption) {
      wx.showToast({ title: '请选择加工方式', icon: 'none' });
      return;
    }

    app.request({
      url: '/client/cart',
      method: 'POST',
      data: {
        product_id: this.data.product.id,
        quantity: this.data.quantity,
        processing_option: processingOption
      },
      success: () => {
        wx.showToast({ title: '已加入购物车', icon: 'success' });
        app.updateCartCount();
      }
    });
  },

  buyNow() {
    if (!this.data.product) return;

    const processingOption = this.getProcessingOption();
    if (this.data.hasProcessingOptions && !processingOption) {
      wx.showToast({ title: '请选择加工方式', icon: 'none' });
      return;
    }

    app.request({
      url: '/client/cart',
      method: 'POST',
      data: {
        product_id: this.data.product.id,
        quantity: this.data.quantity,
        processing_option: processingOption
      },
      success: () => {
        app.updateCartCount();
        wx.navigateTo({
          url: '/pages/confirm-order/confirm-order'
        });
      }
    });
  },

  getShareInfo() {
    const product = this.data.product || {};
    const productId = Number(product.id || this.data.productId);
    if (!Number.isSafeInteger(productId) || productId <= 0) {
      return { title: HOME_TITLE, path: '/pages/index/index', query: '', imageUrl: SHARE_COVER };
    }
    const imageUrl = typeof product.image_url === 'string' && product.image_url.startsWith('https://')
      ? product.image_url
      : SHARE_COVER;
    return {
      title: product.name ? `${product.name} - 鲜配居` : HOME_TITLE,
      path: `/pages/product/product?id=${productId}`,
      query: `id=${productId}`,
      imageUrl
    };
  },

  onShareAppMessage() {
    const { title, path, imageUrl } = this.getShareInfo();
    return { title, path, imageUrl };
  },

  onShareTimeline() {
    const { title, query, imageUrl } = this.getShareInfo();
    return { title, query, imageUrl };
  }
});
