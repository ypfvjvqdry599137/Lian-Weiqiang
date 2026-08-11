/**
 * 加载小程序页面的辅助工具
 * 解决两个问题：
 * 1. index.js 顶部 const app = getApp() 依赖 app.js 先执行 App()
 * 2. jest 会缓存 require，每个测试需要干净的页面实例
 */
const path = require('path');

/**
 * 加载 app.js，返回 app 实例
 */
function loadApp() {
  jest.isolateModules(() => {
    require(path.resolve(__dirname, '../../app.js'));
  });
  return global.__appInstance;
}

/**
 * 加载指定页面，返回一个可调用的页面实例
 * @param {string} pagePath - 相对项目根的页面路径，如 'pages/index/index'
 */
function loadPage(pagePath) {
  // 先确保 app 已加载（index.js 顶部会 getApp()）
  loadApp();

  let pageOptions;
  jest.isolateModules(() => {
    require(path.resolve(__dirname, '../../', pagePath + '.js'));
    pageOptions = global.__lastPageOptions;
  });

  if (!pageOptions) {
    throw new Error('Page options 未捕获，请检查 ' + pagePath + ' 是否调用了 Page()');
  }

  // 构造可调用的页面实例
  const instance = Object.create(pageOptions);
  instance.data = JSON.parse(JSON.stringify(pageOptions.data || {}));

  // mock setData：合并到 data 并记录调用
  instance.setData = jest.fn((newData, cb) => {
    if (newData && typeof newData === 'object') {
      Object.assign(instance.data, newData);
    }
    if (typeof cb === 'function') cb();
  });

  // 提供 getData 方便测试读取
  instance.getData = () => instance.data;

  return instance;
}

module.exports = { loadApp, loadPage };
