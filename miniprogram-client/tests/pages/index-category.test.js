/**
 * 首页 - 分类区域交互逻辑测试
 * 覆盖：quickNavItems 数据完整性、icon 文件存在性、goToCategory 跳转、搜索过滤
 */
const fs = require('fs');
const path = require('path');
const { loadPage } = require('../helpers/loadPage');

const PROJECT_ROOT = path.resolve(__dirname, '../..');

describe('首页 - 分类区域', () => {
  let page;

  beforeEach(() => {
    page = loadPage('pages/index/index');
  });

  describe('category icons', () => {
    test('每个分类项含有完整的图片图标元数据', () => {
      expect(page.data.quickNavItems).toHaveLength(6);
      page.data.quickNavItems.forEach((item) => {
        expect(item).toHaveProperty('id');
        expect(item).toHaveProperty('name');
        expect(item).toHaveProperty('icon');
        expect(item).toHaveProperty('bg');
        expect(item).toHaveProperty('isPhoto');
        expect(typeof item.id).toBe('number');
        expect(typeof item.name).toBe('string');
        expect(typeof item.icon).toBe('string');
        expect(item.icon.length).toBeGreaterThan(0);
        expect(typeof item.isPhoto).toBe('boolean');
      });
    });

    test('分类名称为可读中文，不存在乱码', () => {
      // 中文字符 Unicode 范围：\u4e00-\u9fff
      const chineseRe = /[\u4e00-\u9fff]/;
      page.data.quickNavItems.forEach((item) => {
        expect(chineseRe.test(item.name)).toBe(true);
        // 乱码特征：包含替换字符 \uFFFD 或常见乱码片段
        expect(item.name).not.toMatch(/\uFFFD|鏂|鏃|鑲|娴|绮|鏇/);
      });
    });

    test('图标文件实际存在且格式有效（JPEG 文件头或 SVG 标签）', () => {
      page.data.quickNavItems.forEach((item) => {
        const relPath = item.icon.replace(/^\/+/, '');
        const absPath = path.join(PROJECT_ROOT, relPath);
        expect(fs.existsSync(absPath)).toBe(true);

        if (item.icon.endsWith('.svg')) {
          const content = fs.readFileSync(absPath, 'utf-8');
          expect(content.trim().startsWith('<svg')).toBe(true);
          expect(content.includes('</svg>')).toBe(true);
        } else if (item.icon.endsWith('.jpg') || item.icon.endsWith('.jpeg')) {
          // JPEG 文件头检查：FF D8 FF
          const fd = fs.openSync(absPath, 'r');
          const buf = Buffer.alloc(3);
          fs.readSync(fd, buf, 0, 3, 0);
          fs.closeSync(fd);
          expect(buf[0]).toBe(0xff);
          expect(buf[1]).toBe(0xd8);
          expect(buf[2]).toBe(0xff);
        }
      });
    });

    test('前 5 项为图标(isPhoto=false)，第 6 项为更多分类图标(isPhoto=false)', () => {
      page.data.quickNavItems.slice(0, 5).forEach((item) => {
        expect(item.isPhoto).toBe(false);
        expect(item.icon).toMatch(/\.svg$/i);
      });
      const moreItem = page.data.quickNavItems[5];
      expect(moreItem.isPhoto).toBe(false);
      expect(moreItem.icon).toMatch(/\.svg$/i);
      expect(moreItem.name).toBe('更多分类');
    });
  });

  describe('搜索功能', () => {
    test('输入关键词应过滤商品列表', () => {
      page.setData({
        products: [
          { id: 1, name: '海鲜水产礼包', description: '鲜活鱼虾', category_name: '海鲜水产' },
          { id: 2, name: '时令水果套餐', description: '苹果香蕉', category_name: '时令水果' }
        ]
      });

      page.onSearchInput({ detail: { value: '水产' } });

      expect(page.data.searchKeyword).toBe('水产');
      expect(page.data.displayProducts).toHaveLength(1);
      expect(page.data.displayProducts[0].id).toBe(1);
    });

    test('清空关键词会恢复全部商品', () => {
      page.setData({
        products: [
          { id: 1, name: '海鲜水产礼包', description: '鲜活鱼虾', category_name: '海鲜水产' },
          { id: 2, name: '时令水果套餐', description: '苹果香蕉', category_name: '时令水果' }
        ],
        searchKeyword: '水产'
      });

      page.onSearchInput({ detail: { value: '' } });

      expect(page.data.searchKeyword).toBe('');
      expect(page.data.displayProducts).toHaveLength(2);
    });

    test('空关键词确认会给出提示', () => {
      page.onSearchConfirm({ detail: { value: '   ' } });

      expect(wx.showToast).toHaveBeenCalledWith(expect.objectContaining({
        title: '请输入搜索关键词',
        icon: 'none'
      }));
    });
  });

  describe('goToCategory 跳转行为', () => {
    test('点击分类项应 redirectTo 到分类页', () => {
      page.goToCategory({});
      expect(wx.redirectTo).toHaveBeenCalledTimes(1);
      expect(wx.redirectTo).toHaveBeenCalledWith({
        url: '/pages/category/category'
      });
    });

    test('点击不应触发 navigateTo（避免页面栈堆积）', () => {
      page.goToCategory({});
      expect(wx.navigateTo).not.toHaveBeenCalled();
    });

    test('多次点击分类项都能正常跳转', () => {
      page.goToCategory({});
      page.goToCategory({});
      page.goToCategory({});
      expect(wx.redirectTo).toHaveBeenCalledTimes(3);
    });
  });

  describe('goToIndex 当前页停留', () => {
    test('在首页点击首页 tab 不应发生跳转', () => {
      page.goToIndex({});
      expect(wx.navigateTo).not.toHaveBeenCalled();
      expect(wx.redirectTo).not.toHaveBeenCalled();
    });
  });
});
