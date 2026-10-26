const fs = require('fs');
const path = require('path');
const { loadPage } = require('../helpers/loadPage');

test('address picker starts near the current location and saves only the confirmed place', () => {
  const wxml = fs.readFileSync(path.resolve(__dirname, '../../pages/address/address.wxml'), 'utf8');
  expect(wxml).toContain('优先显示当前位置');

  const page = loadPage('pages/address/address');
  page.chooseLocation();
  expect(wx.getLocation).toHaveBeenCalledWith(expect.objectContaining({ type: 'gcj02' }));
  expect(wx.chooseLocation).not.toHaveBeenCalled();

  wx.getLocation.mock.calls[0][0].success({ longitude: 118.5, latitude: 24.9 });
  expect(wx.hideLoading).toHaveBeenCalled();
  expect(wx.chooseLocation).toHaveBeenCalledTimes(1);
  expect(wx.chooseLocation.mock.calls[0][0]).toEqual(expect.objectContaining({
    longitude: 118.5,
    latitude: 24.9
  }));
  expect(page.data.form.address).toBe('');

  page.chooseLocation();
  expect(wx.getLocation).toHaveBeenCalledTimes(1);
  wx.chooseLocation.mock.calls[0][0].success({
    name: '收货点',
    address: '测试路1号',
    longitude: 118.5,
    latitude: 24.9
  });
  expect(page.data['form.address']).toBe('测试路1号收货点');
  expect(page.data['form.lng']).toBe(118.5);
  expect(page.data['form.lat']).toBe(24.9);
});

test('address picker falls back to ordinary map selection when positioning fails', () => {
  const page = loadPage('pages/address/address');
  page.chooseLocation();
  wx.getLocation.mock.calls[0][0].fail({ errMsg: 'getLocation:fail auth deny' });

  expect(wx.chooseLocation).toHaveBeenCalledTimes(1);
  expect(wx.chooseLocation.mock.calls[0][0]).not.toHaveProperty('latitude');
  expect(wx.chooseLocation.mock.calls[0][0]).not.toHaveProperty('longitude');
  wx.chooseLocation.mock.calls[0][0].fail({ errMsg: 'chooseLocation:fail auth deny' });
  expect(wx.showToast).toHaveBeenCalledWith({ title: '地图打开失败，请检查定位权限', icon: 'none' });
  page.chooseLocation();
  expect(wx.getLocation).toHaveBeenCalledTimes(2);
});

test('address picker ignores invalid positioning coordinates', () => {
  const page = loadPage('pages/address/address');
  page.chooseLocation();
  wx.getLocation.mock.calls[0][0].success({ longitude: null, latitude: null });

  expect(wx.chooseLocation.mock.calls[0][0]).not.toHaveProperty('latitude');
  expect(wx.chooseLocation.mock.calls[0][0]).not.toHaveProperty('longitude');
});
