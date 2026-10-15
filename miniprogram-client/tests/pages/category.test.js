const { loadPage } = require('../helpers/loadPage');

describe('Category page', () => {
  test('loads categories from the public client endpoint', () => {
    const page = loadPage('pages/category/category');
    const app = getApp();
    app.request = jest.fn();

    page.loadCategories();

    expect(app.request).toHaveBeenCalledWith(expect.objectContaining({
      url: '/client/categories'
    }));
  });
});
