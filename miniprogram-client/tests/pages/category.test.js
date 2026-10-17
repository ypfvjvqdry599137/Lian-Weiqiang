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

  test('loads products in pages and keeps the old list while loading more', () => {
    const page = loadPage('pages/category/category');
    const app = getApp();
    app.request = jest.fn();

    page.loadProducts();
    expect(app.request.mock.calls[0][0].url).toBe('/client/products?page=1&page_size=20');
    app.request.mock.calls[0][0].success({ data: { products: [{ id: 1 }], has_more: true } });
    page.onProductsScrollToLower();
    expect(app.request.mock.calls[1][0].url).toBe('/client/products?page=2&page_size=20');
    expect(page.data.products).toEqual([{ id: 1 }]);
    app.request.mock.calls[1][0].success({ data: { products: [{ id: 2 }], has_more: false } });
    expect(page.data.products).toEqual([{ id: 1 }, { id: 2 }]);
    page.onProductsScrollToLower();
    expect(app.request).toHaveBeenCalledTimes(2);
  });

  test('ignores a stale response after switching category', () => {
    const page = loadPage('pages/category/category');
    const app = getApp();
    app.request = jest.fn();

    page.loadProducts(1);
    page.loadProducts(2);
    app.request.mock.calls[1][0].success({ data: { products: [{ id: 2 }], has_more: false } });
    app.request.mock.calls[0][0].success({ data: { products: [{ id: 1 }], has_more: false } });
    expect(page.data.products).toEqual([{ id: 2 }]);
  });

  test('retries a failed page and shows a placeholder for a broken image', () => {
    const page = loadPage('pages/category/category');
    const app = getApp();
    app.request = jest.fn();

    page.loadProducts();
    app.request.mock.calls[0][0].fail();
    expect(page.data.productsError).toBe(true);
    page.retryLoadProducts();
    expect(app.request.mock.calls[1][0].url).toContain('page=1');
    app.request.mock.calls[1][0].success({ data: { products: [{ id: 7, image_url: '/detail', thumbnail_url: '/thumb' }], has_more: false } });
    page.onProductImageError({ currentTarget: { dataset: { id: 7, imageUrl: '/thumb' } } });
    expect(page.data.products[0].imageError).toBe(true);
    expect(page.data.products[0].imageUnavailable).toBe(false);
    page.onProductImageError({ currentTarget: { dataset: { id: 7, imageUrl: '/detail' } } });
    expect(page.data.products[0].imageUnavailable).toBe(true);
  });
});
