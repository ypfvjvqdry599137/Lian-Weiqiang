const app = getApp();

Page({
  data: {
    addresses: [],
    selectedAddressId: null,
    mode: 'list', // list, add, edit
    editingAddress: null,
    form: {
      id: null,
      receiver_name: '',
      receiver_phone: '',
      address: '',
      lng: null,
      lat: null,
      is_default: false
    },
    canSelect: false // 是否可以选择地址（用于确认订单页跳转过来的情况）
  },

  onLoad(options) {
    this.setData({
      canSelect: options.canSelect === 'true',
      selectedAddressId: options.selectedId ? parseInt(options.selectedId) : null
    });
    this.loadAddresses();
  },

  // 加载地址列表
  loadAddresses() {
    app.request({
      url: '/client/addresses',
      success: (res) => {
        if (res.data && res.data.addresses) {
          this.setData({ addresses: res.data.addresses });
          // 如果没有选中的地址，默认选中第一个
          if (res.data.addresses.length > 0 && !this.data.selectedAddressId) {
            const defaultAddr = res.data.addresses.find(a => a.is_default) || res.data.addresses[0];
            this.setData({ selectedAddressId: defaultAddr.id });
            // 更新全局数据
            app.globalData.selectedAddress = defaultAddr;
          }
        }
      }
    });
  },

  // 添加地址
  goToAdd() {
    this.setData({
      mode: 'add',
      form: {
        id: null,
        receiver_name: '',
        receiver_phone: '',
        address: '',
        lng: null,
        lat: null,
        is_default: false
      }
    });
  },

  // 编辑地址
  goToEdit(e) {
    const address = e.currentTarget.dataset.address;
    this.setData({
      mode: 'edit',
      form: {
        id: address.id,
        receiver_name: address.receiver_name,
        receiver_phone: address.receiver_phone,
        address: address.address,
        lng: address.lng,
        lat: address.lat,
        is_default: address.is_default
      }
    });
  },

  // 选择地址（用于确认订单页）
  selectAddress(e) {
    if (this.data.canSelect) {
      const address = e.currentTarget.dataset.address;
      app.globalData.selectedAddress = address;
      wx.navigateBack();
    }
  },

  // 删除地址
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

  // 设置默认地址
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

  // 表单输入
  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({
      [`form.${field}`]: e.detail.value
    });
  },

  // 选择位置（地图）
  chooseLocation() {
    wx.chooseLocation({
      success: (res) => {
        this.setData({
          'form.address': res.address,
          'form.lng': res.longitude,
          'form.lat': res.latitude
        });
      }
    });
  },

  // 切换默认地址
  toggleDefault() {
    this.setData({
      'form.is_default': !this.data.form.is_default
    });
  },

  // 保存地址
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

    const url = this.data.mode === 'add' ? '/client/addresses' : `/client/addresses/${form.id}`;
    const method = this.data.mode === 'add' ? 'POST' : 'PUT';

    app.request({
      url: url,
      method: method,
      data: form,
      success: () => {
        wx.showToast({ title: this.data.mode === 'add' ? '添加成功' : '修改成功', icon: 'success' });
        this.setData({ mode: 'list' });
        this.loadAddresses();
      }
    });
  },

  // 返回列表
  goBack() {
    this.setData({ mode: 'list' });
  }
})
