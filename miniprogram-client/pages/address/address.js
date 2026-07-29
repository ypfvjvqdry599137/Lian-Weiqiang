const app = getApp();

function emptyForm() {
  return {
    id: null,
    receiver_name: '',
    receiver_phone: '',
    address: '',
    full_address: '',
    detail_address: '',
    name: '',
    lng: null,
    lat: null,
    is_default: false
  };
}

function normalizeAddress(address) {
  const addressText = address.address || address.full_address || address.detail_address || '';
  return {
    ...address,
    address: addressText,
    full_address: address.full_address || addressText,
    detail_address: address.detail_address || addressText,
    lng: address.lng === 'None' ? null : address.lng,
    lat: address.lat === 'None' ? null : address.lat
  };
}

function buildAddressText(location) {
  const name = location.name || '';
  const address = location.address || '';
  if (address && name && address.indexOf(name) === -1) {
    return `${address}${name}`;
  }
  return address || name;
}

Page({
  data: {
    addresses: [],
    selectedAddressId: null,
    mode: 'list',
    editingAddress: null,
    form: emptyForm(),
    canSelect: false
  },

  onLoad(options) {
    this.setData({
      canSelect: options.canSelect === 'true',
      selectedAddressId: options.selectedId ? parseInt(options.selectedId) : null
    });
    this.loadAddresses();
  },

  loadAddresses() {
    app.request({
      url: '/client/addresses',
      success: (res) => {
        if (res.data && res.data.addresses) {
          const addresses = res.data.addresses.map(normalizeAddress);
          this.setData({ addresses });
          if (addresses.length > 0 && !this.data.selectedAddressId) {
            const defaultAddr = addresses.find(a => a.is_default) || addresses[0];
            this.setData({ selectedAddressId: defaultAddr.id });
            app.globalData.selectedAddress = defaultAddr;
          }
        }
      }
    });
  },

  goToAdd() {
    this.setData({
      mode: 'add',
      form: emptyForm()
    });
  },

  goToEdit(e) {
    const address = normalizeAddress(e.currentTarget.dataset.address);
    this.setData({
      mode: 'edit',
      form: {
        id: address.id,
        receiver_name: address.receiver_name,
        receiver_phone: address.receiver_phone,
        address: address.address,
        full_address: address.full_address || address.address,
        detail_address: address.detail_address || address.address,
        name: address.detail_address || '',
        lng: address.lng,
        lat: address.lat,
        is_default: address.is_default
      }
    });
  },

  selectAddress(e) {
    if (this.data.canSelect) {
      const address = normalizeAddress(e.currentTarget.dataset.address);
      app.globalData.selectedAddress = address;
      wx.navigateBack();
    }
  },

  deleteAddress(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '提示',
      content: '确定要删除这个地址吗？',
      success: (res) => {
        if (res.confirm) {
          app.request({
            url: `/client/addresses/${id}`,
            method: 'DELETE',
            success: () => {
              wx.showToast({ title: '删除成功', icon: 'success' });
              this.loadAddresses();
            }
          });
        }
      }
    });
  },

  setDefault(e) {
    const id = e.currentTarget.dataset.id;
    app.request({
      url: `/client/addresses/${id}/default`,
      method: 'POST',
      success: () => {
        wx.showToast({ title: '设置成功', icon: 'success' });
        this.loadAddresses();
      }
    });
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({
      [`form.${field}`]: e.detail.value
    });
  },

  chooseLocation() {
    wx.chooseLocation({
      success: (res) => {
        const addressText = buildAddressText(res);
        this.setData({
          'form.address': addressText,
          'form.full_address': addressText,
          'form.detail_address': res.name || addressText,
          'form.name': res.name || '',
          'form.lng': res.longitude,
          'form.lat': res.latitude
        });
      },
      fail: () => {
        wx.showToast({ title: '未选择位置', icon: 'none' });
      }
    });
  },

  toggleDefault() {
    this.setData({
      'form.is_default': !this.data.form.is_default
    });
  },

  saveAddress() {
    const form = this.data.form;
    if (!form.receiver_name) {
      wx.showToast({ title: '请输入收货人姓名', icon: 'none' });
      return;
    }
    if (!form.receiver_phone) {
      wx.showToast({ title: '请输入联系电话', icon: 'none' });
      return;
    }
    if (!form.address) {
      wx.showToast({ title: '请选择收货地址', icon: 'none' });
      return;
    }
    if (form.lng === null || form.lat === null) {
      wx.showToast({ title: '请选择带定位的收货地址', icon: 'none' });
      return;
    }

    const url = this.data.mode === 'add' ? '/client/addresses' : `/client/addresses/${form.id}`;
    const method = this.data.mode === 'add' ? 'POST' : 'PUT';

    app.request({
      url,
      method,
      data: form,
      success: () => {
        wx.showToast({ title: this.data.mode === 'add' ? '添加成功' : '修改成功', icon: 'success' });
        this.setData({ mode: 'list' });
        this.loadAddresses();
      }
    });
  },

  goBack() {
    this.setData({ mode: 'list' });
  }
});
