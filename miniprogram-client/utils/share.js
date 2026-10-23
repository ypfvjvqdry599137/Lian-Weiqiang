const HOME_TITLE = '鲜配居，新鲜食材送到家';
const SHARE_COVER = '/images/categories/cat-vegetable.jpg';

function showPublicShareMenu() {
  if (typeof wx.showShareMenu === 'function') {
    wx.showShareMenu({ menus: ['shareAppMessage', 'shareTimeline'] });
  }
}

function hidePrivateShareMenu() {
  if (typeof wx.hideShareMenu === 'function') {
    wx.hideShareMenu({ menus: ['shareAppMessage', 'shareTimeline'] });
  }
}

module.exports = { HOME_TITLE, SHARE_COVER, showPublicShareMenu, hidePrivateShareMenu };
