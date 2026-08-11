/**
 * 测试环境 setup
 * Mock 微信小程序的全局对象：wx / Page / App / getApp
 * 让 index.js / app.js 能在 Node 环境被 require 并执行
 */

// ===== app 实例（getApp() 的返回值）=====
// require app.js 时会执行 App(options)，把 options 合并到 appInstance
const appInstance = {
  globalData: {
    userInfo: null,
    cartCount: 0,
    cartTotalPrice: '0.00',
    selectedAddress: null,
    baseUrl: 'https://xianpeiju.site'
  },
  request: jest.fn(),
  updateCartCount: jest.fn()
};

global.getApp = () => appInstance;

// App(options) 把生命周期和方法挂到 appInstance
global.App = (options) => {
  Object.assign(appInstance, options);
};

// Page(options) 把 options 暴露到全局，供测试用例取用
global.__lastPageOptions = null;
global.Page = (options) => {
  global.__lastPageOptions = options;
};

// getCurrentPages mock（部分页面会用）
global.getCurrentPages = () => [];

// ===== wx API mock =====
const wx = {
  navigateTo: jest.fn(),
  redirectTo: jest.fn(),
  navigateBack: jest.fn(),
  switchTab: jest.fn(),
  showToast: jest.fn(),
  showLoading: jest.fn(),
  hideLoading: jest.fn(),
  showModal: jest.fn(),
  showActionSheet: jest.fn(),
  setStorageSync: jest.fn(),
  getStorageSync: jest.fn(() => ''),
  removeStorageSync: jest.fn(),
  setNavigationBarTitle: jest.fn(),
  request: jest.fn(),
  chooseLocation: jest.fn()
};

global.wx = wx;

// 暴露给测试用例的工具
global.__appInstance = appInstance;
global.__wx = wx;

// mock 调用记录的清理通过 jest.config.js 的 clearMocks: true 自动完成
