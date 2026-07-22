// 配置后端API基础URL
const BASE_URL = 'http://xianpeiju.site';

// ==================== 地图相关变量 ====================
let map = null;
let marker = null;
let selectedLng = null;
let selectedLat = null;

// ==================== 地图相关函数 ====================
function showMapPicker() {
    // 检查是否加载了腾讯地图SDK
    if (typeof TMap === 'undefined') {
        alert('地图功能暂时不可用：需要先去腾讯地图申请 Key 并在 index.html 中配置！\n\n当前可手动输入经纬度，经纬度可从百度/高德地图查询。');
        return;
    }
    
    document.getElementById('map-modal').classList.add('show');
    setTimeout(() => {
        if (!map) {
            // 初始化地图，默认定位到北京天安门
            map = new TMap.Map('map-container', {
                center: new TMap.LatLng(39.9042, 116.4074),
                zoom: 12
            });
            // 监听地图点击事件
            map.on('click', (evt) => {
                const lat = evt.latLng.getLat().toFixed(6);
                const lng = evt.latLng.getLng().toFixed(6);
                selectedLat = lat;
                selectedLng = lng;
                // 更新或添加标记
                if (!marker) {
                    marker = new TMap.Marker({
                        position: new TMap.LatLng(lat, lng),
                        map: map
                    });
                } else {
                    marker.setPosition(new TMap.LatLng(lat, lng));
                }
                // 移动地图中心到点击位置
                map.setCenter(new TMap.LatLng(lat, lng));
            });
        }
        // 如果已有经度纬度，先定位到那里
        const currentLng = parseFloat(document.getElementById('zone-center-lng').value);
        const currentLat = parseFloat(document.getElementById('zone-center-lat').value);
        if (currentLng && currentLat) {
            selectedLng = currentLng.toFixed(6);
            selectedLat = currentLat.toFixed(6);
            if (!marker) {
                marker = new TMap.Marker({
                    position: new TMap.LatLng(currentLat, currentLng),
                    map: map
                });
            } else {
                marker.setPosition(new TMap.LatLng(currentLat, currentLng));
            }
            map.setCenter(new TMap.LatLng(currentLat, currentLng));
        }
    }, 100);
}

function confirmMapPick() {
    if (selectedLng && selectedLat) {
        document.getElementById('zone-center-lng').value = selectedLng;
        document.getElementById('zone-center-lat').value = selectedLat;
    }
    closeMapModal();
}

function closeMapModal() {
    document.getElementById('map-modal').classList.remove('show');
}

// ==================== 辅助函数 ====================

async function fetchData(url, method = 'GET', data = null, showAlert = false) {
    const fullUrl = BASE_URL + url;
    console.log('正在请求:', fullUrl, method, data);
    
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
    };
    if (data) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(fullUrl, options);
        console.log('响应状态:', response.status);
        
        if (!response.ok) {
            let errorMsg = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorMsg = errorData.message || errorMsg;
            } catch (e) {
            }
            throw new Error(errorMsg);
        }
        
        const result = await response.json();
        console.log('请求成功:', result);
        return result;
    } catch (error) {
        console.error('请求失败:', error);
        if (showAlert) {
            alert('操作失败: ' + error.message);
        }
        return null;
    }
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

function formatCurrency(value) {
    return `¥${(parseFloat(value) || 0).toFixed(2)}`;
}

function getOrderStatusText(status) {
    const statusMap = {
        10: '待付款',
        20: '待配货',
        30: '配送中',
        40: '已送达',
        50: '已完成',
        60: '已关闭'
    };
    return statusMap[status] || '未知';
}

function showModal(id) {
    document.getElementById(id).classList.add('show');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('show');
}

// ==================== 页面导航 ====================

let currentPage = 'dashboard';

document.querySelectorAll('.menu-item').forEach(item => {
    item.addEventListener('click', function() {
        document.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
        this.classList.add('active');
        currentPage = this.dataset.page;
        renderPage();
    });
});

async function renderPage() {
    document.querySelectorAll('.page').forEach(page => page.classList.remove('active'));
    document.getElementById(`page-${currentPage}`).classList.add('active');

    switch (currentPage) {
        case 'dashboard':
            await loadDashboardStats();
            break;
        case 'suppliers':
            await loadSuppliers();
            break;
        case 'ingredients':
            await loadIngredients();
            break;
        case 'products':
            await loadProducts();
            break;
        case 'categories':
            await loadCategories();
            break;
        case 'delivery-zones':
            await loadDeliveryZones();
            break;
        case 'supplier-orders':
            await loadSupplierOrders();
            break;
        case 'orders':
            await loadOrders();
            break;
    }
}

// ==================== 仪表盘 (Dashboard) ====================

async function loadDashboardStats() {
    try {
        const products = await fetchData('/admin/products?is_active=true');
        if(products) {
            document.getElementById('stat-products').textContent = products.products.length;
        }
        
        const zones = await fetchData('/admin/delivery-zones');
        if(zones) {
            document.getElementById('stat-stations').textContent = zones.zones.length;
        }
        
        const orders = await fetchData('/admin/orders');
        if(orders) {
            const today = new Date().toDateString();
            const todayOrders = orders.orders.filter(o => new Date(o.created_at).toDateString() === today);
            document.getElementById('stat-today-orders').textContent = todayOrders.length;
            
            let todayRevenue = 0;
            todayOrders.filter(o => o.order_status === 40 || o.order_status === 50).forEach(o => {
                todayRevenue += parseFloat(o.total_amount) || 0;
            });
            document.getElementById('stat-today-revenue').textContent = `¥${todayRevenue.toFixed(2)}`;
        }
    } catch (e) {
        console.error('Dashboard加载失败', e);
    }
}

// ==================== 商品管理 (Products) ====================

async function loadProducts() {
    const productsData = await fetchData('/admin/products?is_active=true');
    const productsList = document.getElementById('products-list');
    productsList.innerHTML = '';

    if (productsData && productsData.products) {
        productsData.products.forEach(product => {
            const card = document.createElement('div');
            card.classList.add('data-card');
            card.innerHTML = `
                <div class="data-card-content">
                    <h4>${product.name}</h4>
                    <p>${product.description || '无描述'}</p>
                    <p class="price">¥${product.price} / ${product.unit}</p>
                    <p>库存: ${product.available_stock}</p>
                </div>
                <div class="data-card-actions">
                    <button class="btn btn-sm btn-primary" onclick="showProductIngredientsModal(${product.id})">配置原料</button>
                    <button class="btn btn-sm btn-success" onclick="showProductModal(${product.id})">编辑</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteProduct(${product.id})">删除</button>
                </div>
            `;
            productsList.appendChild(card);
        });
    }
}

function updateProductImagePreview(url) {
    const preview = document.getElementById('product-image-preview');
    if (!preview) return;

    if (url) {
        preview.src = url;
        preview.style.display = 'block';
    } else {
        preview.removeAttribute('src');
        preview.style.display = 'none';
    }
}

function compressProductImageFile(file) {
    return new Promise((resolve, reject) => {
        if (!file || !file.type.startsWith('image/')) {
            reject(new Error('请选择图片文件'));
            return;
        }

        const image = new Image();
        const objectUrl = URL.createObjectURL(file);

        image.onload = () => {
            URL.revokeObjectURL(objectUrl);

            const maxSide = 1600;
            const scale = Math.min(1, maxSide / Math.max(image.width, image.height));
            const canvas = document.createElement('canvas');
            canvas.width = Math.max(1, Math.round(image.width * scale));
            canvas.height = Math.max(1, Math.round(image.height * scale));

            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#fff';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

            canvas.toBlob((blob) => {
                if (!blob) {
                    reject(new Error('图片压缩失败'));
                    return;
                }
                const filename = file.name.replace(/\.[^.]+$/, '') + '.jpg';
                resolve(new File([blob], filename, { type: 'image/jpeg' }));
            }, 'image/jpeg', 0.82);
        };

        image.onerror = () => {
            URL.revokeObjectURL(objectUrl);
            reject(new Error('图片文件无法读取'));
        };

        image.src = objectUrl;
    });
}

async function uploadProductImage() {
    const fileInput = document.getElementById('product-image-file');
    const status = document.getElementById('product-image-upload-status');
    const file = fileInput.files && fileInput.files[0];

    if (!file) {
        alert('请先选择图片');
        return;
    }

    try {
        status.textContent = '正在压缩上传...';
        const compressedFile = await compressProductImageFile(file);
        const formData = new FormData();
        formData.append('image', compressedFile, compressedFile.name);

        const response = await fetch(`${BASE_URL}/admin/uploads/product-image`, {
            method: 'POST',
            body: formData
        });
        const result = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(result.message || `上传失败: ${response.status}`);
        }

        document.getElementById('product-image').value = result.image_url;
        updateProductImagePreview(result.image_url);
        status.textContent = '上传成功，已自动填入图片URL';
    } catch (error) {
        console.error('图片上传失败:', error);
        status.textContent = '';
        alert('图片上传失败: ' + error.message);
    }
}

async function showProductModal(productId = null) {
    const modal = document.getElementById('product-modal');
    const title = document.getElementById('product-modal-title');
    const form = document.getElementById('product-form');
    form.reset();
    document.getElementById('product-id').value = '';
    document.getElementById('product-recommend').checked = false;
    document.getElementById('product-active').checked = true;
    document.getElementById('product-warning-stock').value = 10;
    document.getElementById('product-image-file').value = '';
    document.getElementById('product-image-upload-status').textContent = '';
    updateProductImagePreview('');

    if (productId) {
        title.textContent = '编辑商品';
        const product = await fetchData(`/admin/products/${productId}`);
        if (product) {
            document.getElementById('product-id').value = product.id;
            document.getElementById('product-name').value = product.name;
            document.getElementById('product-desc').value = product.description;
            document.getElementById('product-category-id').value = product.category_id;
            document.getElementById('product-price').value = product.price;
            document.getElementById('product-original-price').value = product.original_price;
            document.getElementById('product-image').value = product.image_url;
            updateProductImagePreview(product.image_url);
            document.getElementById('product-unit').value = product.unit;
            document.getElementById('product-stock').value = product.total_stock;
            document.getElementById('product-warning-stock').value = product.warning_stock;
            document.getElementById('product-recommend').checked = product.is_recommend;
            document.getElementById('product-active').checked = product.is_active;
        }
    } else {
        title.textContent = '添加商品';
    }
    showModal('product-modal');
}

document.getElementById('product-image').addEventListener('input', function() {
    updateProductImagePreview(this.value);
});

document.getElementById('product-form').addEventListener('submit', async function(event) {
    event.preventDefault();
    const productId = document.getElementById('product-id').value;
    const method = productId ? 'PUT' : 'POST';
    const url = productId ? `/admin/products/${productId}` : '/admin/products';
    const data = {
        name: document.getElementById('product-name').value,
        description: document.getElementById('product-desc').value,
        category_id: document.getElementById('product-category-id').value || null,
        price: parseFloat(document.getElementById('product-price').value),
        original_price: parseFloat(document.getElementById('product-original-price').value) || null,
        image_url: document.getElementById('product-image').value || null,
        unit: document.getElementById('product-unit').value,
        total_stock: parseInt(document.getElementById('product-stock').value),
        warning_stock: parseInt(document.getElementById('product-warning-stock').value),
        is_recommend: document.getElementById('product-recommend').checked,
        is_active: document.getElementById('product-active').checked,
    };

    const result = await fetchData(url, method, data);
    if (result) {
        alert('商品保存成功！');
        closeModal('product-modal');
        await loadProducts();
        await loadDashboardStats();
    }
});

async function deleteProduct(productId) {
    if (confirm('确定要删除此商品吗？')) {
        const result = await fetchData(`/admin/products/${productId}`, 'DELETE', null, true);
        if (result) {
            alert('商品删除成功！');
            await loadProducts();
            await loadDashboardStats();
        }
    }
}

// ==================== 分类管理 (Categories) ====================

async function loadCategories() {
    const categoriesData = await fetchData('/admin/categories');
    const categoriesList = document.getElementById('categories-list');
    categoriesList.innerHTML = '';

    if (categoriesData && categoriesData.categories) {
        categoriesData.categories.forEach(category => {
            const card = document.createElement('div');
            card.classList.add('data-card');
            card.innerHTML = `
                <div class="data-card-content">
                    <h4>${category.icon} ${category.name}</h4>
                    <p>排序: ${category.sort_order} | ${category.is_active ? '已启用' : '已禁用'}</p>
                </div>
                <div class="data-card-actions">
                    <button class="btn btn-sm btn-success" onclick="showCategoryModal(${category.id})">编辑</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteCategory(${category.id})">删除</button>
                </div>
            `;
            categoriesList.appendChild(card);
        });
    }
}

async function showCategoryModal(categoryId = null) {
    const modal = document.getElementById('category-modal');
    const title = document.getElementById('category-modal-title');
    const form = document.getElementById('category-form');
    form.reset();
    document.getElementById('category-id').value = '';
    document.getElementById('category-active').checked = true;

    if (categoryId) {
        title.textContent = '编辑分类';
        const category = await fetchData(`/admin/categories/${categoryId}`);
        if (category) {
            document.getElementById('category-id').value = category.id;
            document.getElementById('category-name').value = category.name;
            document.getElementById('category-icon').value = category.icon;
            document.getElementById('category-sort').value = category.sort_order;
            document.getElementById('category-active').checked = category.is_active;
        }
    } else {
        title.textContent = '添加分类';
    }
    showModal('category-modal');
}

document.getElementById('category-form').addEventListener('submit', async function(event) {
    event.preventDefault();
    const categoryId = document.getElementById('category-id').value;
    const method = categoryId ? 'PUT' : 'POST';
    const url = categoryId ? `/admin/categories/${categoryId}` : '/admin/categories';
    const data = {
        name: document.getElementById('category-name').value,
        icon: document.getElementById('category-icon').value || null,
        sort_order: parseInt(document.getElementById('category-sort').value) || 0,
        is_active: document.getElementById('category-active').checked,
    };

    const result = await fetchData(url, method, data);
    if (result) {
        alert('分类保存成功！');
        closeModal('category-modal');
        await loadCategories();
    }
});

async function deleteCategory(categoryId) {
    if (confirm('确定要删除此分类吗？')) {
        const result = await fetchData(`/admin/categories/${categoryId}`, 'DELETE');
        if (result) {
            alert('分类删除成功！');
            await loadCategories();
        }
    }
}

// ==================== 配送区域管理 (Delivery Zones) ====================

async function loadDeliveryZones() {
    const zonesData = await fetchData('/admin/delivery-zones');
    const zonesList = document.getElementById('delivery-zones-list');
    zonesList.innerHTML = '';

    if (zonesData && zonesData.zones) {
        zonesData.zones.forEach(zone => {
            const card = document.createElement('div');
            card.classList.add('data-card');
            card.innerHTML = `
                <div class="data-card-content">
                    <h4>${zone.zone_name}</h4>
                    <p>中心: ${zone.center_lng}, ${zone.center_lat}</p>
                    <p>配送半径: ${zone.radius}米 | 配送费: ¥${zone.delivery_fee}</p>
                    <p>预计送达: ${zone.delivery_time}</p>
                    <p>合作商: ${zone.merchant_username || '无'}</p>
                    <p>状态: ${zone.is_active ? '启用' : '禁用'}</p>
                </div>
                <div class="data-card-actions">
                    <button class="btn btn-sm btn-success" onclick="showDeliveryZoneModal(${zone.id})">编辑</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteDeliveryZone(${zone.id})">删除</button>
                </div>
            `;
            zonesList.appendChild(card);
        });
    }
}

async function showDeliveryZoneModal(zoneId = null) {
    const modal = document.getElementById('delivery-zone-modal');
    const title = document.getElementById('delivery-zone-modal-title');
    const form = document.getElementById('delivery-zone-form');
    form.reset();
    document.getElementById('delivery-zone-id').value = '';
    document.getElementById('zone-active').checked = true;

    if (zoneId) {
        title.textContent = '编辑配送区域';
        const zone = await fetchData(`/admin/delivery-zones/${zoneId}`);
        if (zone) {
            document.getElementById('delivery-zone-id').value = zone.id;
            document.getElementById('zone-name').value = zone.zone_name;
            document.getElementById('zone-center-lng').value = zone.center_lng;
            document.getElementById('zone-center-lat').value = zone.center_lat;
            document.getElementById('zone-radius').value = zone.radius;
            document.getElementById('zone-delivery-fee').value = zone.delivery_fee;
            document.getElementById('zone-delivery-time').value = zone.delivery_time;
            document.getElementById('zone-merchant-user').value = zone.merchant_username || '';
            document.getElementById('zone-active').checked = zone.is_active;
        }
    } else {
        title.textContent = '添加配送区域';
    }
    showModal('delivery-zone-modal');
}

document.getElementById('delivery-zone-form').addEventListener('submit', async function(event) {
    event.preventDefault();
    const zoneId = document.getElementById('delivery-zone-id').value;
    const method = zoneId ? 'PUT' : 'POST';
    const url = zoneId ? `/admin/delivery-zones/${zoneId}` : '/admin/delivery-zones';
    const data = {
        zone_name: document.getElementById('zone-name').value,
        center_lng: parseFloat(document.getElementById('zone-center-lng').value),
        center_lat: parseFloat(document.getElementById('zone-center-lat').value),
        radius: parseInt(document.getElementById('zone-radius').value),
        delivery_fee: parseFloat(document.getElementById('zone-delivery-fee').value),
        delivery_time: document.getElementById('zone-delivery-time').value,
        merchant_username: document.getElementById('zone-merchant-user').value || null,
        merchant_password: document.getElementById('zone-merchant-pwd').value || null,
        is_active: document.getElementById('zone-active').checked,
    };
    
    if (method === 'PUT' && !data.merchant_password) {
        delete data.merchant_password;
    }

    const result = await fetchData(url, method, data);
    if (result) {
        alert('配送区域保存成功！');
        closeModal('delivery-zone-modal');
        await loadDeliveryZones();
        await loadDashboardStats();
    }
});

async function deleteDeliveryZone(zoneId) {
    if (confirm('确定要删除此配送区域吗？')) {
        const result = await fetchData(`/admin/delivery-zones/${zoneId}`, 'DELETE');
        if (result) {
            alert('配送区域删除成功！');
            await loadDeliveryZones();
            await loadDashboardStats();
        }
    }
}

// ==================== 订单管理 (Orders) ====================

let currentOrderStatusFilter = 'all';

document.querySelectorAll('.tabs .tab').forEach(tab => {
    tab.addEventListener('click', function() {
        document.querySelectorAll('.tabs .tab').forEach(t => t.classList.remove('active'));
        this.classList.add('active');
        currentOrderStatusFilter = this.dataset.status;
        loadOrders();
    });
});

async function loadOrders() {
    let url = '/admin/orders';
    if (currentOrderStatusFilter !== 'all') {
        url += `?status=${currentOrderStatusFilter}`;
    }
    const ordersData = await fetchData(url);
    const ordersList = document.getElementById('orders-list');
    ordersList.innerHTML = '';

    if (ordersData && ordersData.orders) {
        ordersData.orders.forEach(order => {
            const card = document.createElement('div');
            card.classList.add('data-card', `status-${order.order_status}`);
            const itemsHtml = order.items ? order.items.map(item => `
                <p>${item.product_name} x ${item.quantity}</p>
            `).join('') : '';
            card.innerHTML = `
                <div class="data-card-content">
                    <h4>订单号: ${order.order_sn} <span style="float:right;color:#666;">${getOrderStatusText(order.order_status)}</span></h4>
                    <p>配送区域: ${order.zone_id} | 总金额: ¥${order.total_amount} | 配送费: ¥${order.delivery_fee}</p>
                    <p>收货人: ${order.receiver_name} | 电话: ${order.receiver_phone}</p>
                    <p>收货地址: ${order.receiver_address}</p>
                    <div style="margin-top:10px;padding-top:10px;border-top:1px solid #eee;">
                        ${itemsHtml}
                    </div>
                    <p style="font-size:12px;color:#999;margin-top:10px;">下单时间: ${formatDate(order.created_at)}</p>
                </div>
                <div class="data-card-actions">
                    <button class="btn btn-sm btn-success" onclick="editOrderStatus('${order.order_sn}')">修改状态</button>
                </div>
            `;
            ordersList.appendChild(card);
        });
    }
}

async function editOrderStatus(orderSn) {
    const newStatus = prompt('请输入新的订单状态 (10=待付款, 20=待配货, 30=配送中, 40=已送达, 50=已完成, 60=已关闭):');
    if (newStatus && !isNaN(newStatus)) {
        const result = await fetchData(`/admin/orders/${orderSn}/status`, 'PUT', { status: parseInt(newStatus) });
        if (result) {
            alert('订单状态更新成功！');
            await loadOrders();
            await loadDashboardStats();
        }
    }
}

// ==================== 供应商管理 (Suppliers) ====================

async function loadSuppliers() {
    const suppliersData = await fetchData('/admin/suppliers');
    const suppliersList = document.getElementById('suppliers-list');
    suppliersList.innerHTML = '';

    if (suppliersData && suppliersData.suppliers) {
        suppliersData.suppliers.forEach(supplier => {
            const card = document.createElement('div');
            card.classList.add('data-card');
            card.innerHTML = `
                <div class="data-card-content">
                    <h4>${supplier.name}</h4>
                    <p>联系人: ${supplier.contact_person || '无'} | 电话: ${supplier.phone || '无'}</p>
                    <p>登录账号: ${supplier.username}</p>
                    <p>状态: ${supplier.is_active ? '已启用' : '已禁用'}</p>
                    <p style="font-size:12px;color:#999;">创建时间: ${formatDate(supplier.created_at)}</p>
                </div>
                <div class="data-card-actions">
                    <button class="btn btn-sm btn-success" onclick="showSupplierModal(${supplier.id})">编辑</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteSupplier(${supplier.id})">删除</button>
                </div>
            `;
            suppliersList.appendChild(card);
        });
    }
}

async function showSupplierModal(supplierId = null) {
    const modal = document.getElementById('supplier-modal');
    const title = document.getElementById('supplier-modal-title');
    const form = document.getElementById('supplier-form');
    form.reset();
    document.getElementById('supplier-id').value = '';
    document.getElementById('supplier-active').checked = true;

    if (supplierId) {
        title.textContent = '编辑供应商';
        const supplier = await fetchData(`/admin/suppliers/${supplierId}`);
        if (supplier) {
            document.getElementById('supplier-id').value = supplier.id;
            document.getElementById('supplier-name').value = supplier.name;
            document.getElementById('supplier-contact').value = supplier.contact_person || '';
            document.getElementById('supplier-phone').value = supplier.phone || '';
            document.getElementById('supplier-username').value = supplier.username;
            document.getElementById('supplier-active').checked = supplier.is_active;
        }
    } else {
        title.textContent = '添加供应商';
    }
    showModal('supplier-modal');
}

document.getElementById('supplier-form').addEventListener('submit', async function(event) {
    event.preventDefault();
    const supplierId = document.getElementById('supplier-id').value;
    const method = supplierId ? 'PUT' : 'POST';
    const url = supplierId ? `/admin/suppliers/${supplierId}` : '/admin/suppliers';
    const data = {
        name: document.getElementById('supplier-name').value,
        contact_person: document.getElementById('supplier-contact').value || null,
        phone: document.getElementById('supplier-phone').value || null,
        username: document.getElementById('supplier-username').value,
        is_active: document.getElementById('supplier-active').checked,
    };
    const password = document.getElementById('supplier-password').value;
    if (password) {
        data.password = password;
    }

    const result = await fetchData(url, method, data);
    if (result) {
        alert('供应商保存成功！');
        closeModal('supplier-modal');
        await loadSuppliers();
    }
});

async function deleteSupplier(supplierId) {
    if (confirm('确定要删除此供应商吗？')) {
        const result = await fetchData(`/admin/suppliers/${supplierId}`, 'DELETE');
        if (result) {
            alert('供应商删除成功！');
            await loadSuppliers();
        }
    }
}

// ==================== 原料管理 (Ingredients) ====================

let currentIngredients = [];

function getIngredientsListUrl() {
    const params = new URLSearchParams();
    const search = document.getElementById('ingredient-search')?.value.trim();
    const status = document.getElementById('ingredient-status-filter')?.value || 'active';

    if (search) {
        params.set('q', search);
    }
    if (status === 'active') {
        params.set('is_active', 'true');
    } else if (status === 'inactive') {
        params.set('is_active', 'false');
    }

    const query = params.toString();
    return query ? `/admin/ingredients?${query}` : '/admin/ingredients';
}

function getSelectedIngredientIds() {
    return Array.from(document.querySelectorAll('.ingredient-select:checked'))
        .map(input => parseInt(input.value))
        .filter(id => !Number.isNaN(id));
}

function toggleIngredientSelection(checked) {
    document.querySelectorAll('.ingredient-select').forEach(input => {
        input.checked = checked;
    });
}

function syncIngredientsSelectAll() {
    const selectAll = document.getElementById('ingredients-select-all');
    if (!selectAll) return;

    const checkboxes = Array.from(document.querySelectorAll('.ingredient-select'));
    selectAll.checked = checkboxes.length > 0 && checkboxes.every(input => input.checked);
}

async function loadIngredients() {
    const ingredientsData = await fetchData(getIngredientsListUrl());
    const ingredientsList = document.getElementById('ingredients-list');
    ingredientsList.innerHTML = '';
    const selectAll = document.getElementById('ingredients-select-all');
    if (selectAll) {
        selectAll.checked = false;
    }

    if (ingredientsData && ingredientsData.ingredients) {
        currentIngredients = ingredientsData.ingredients;
        if (currentIngredients.length === 0) {
            ingredientsList.innerHTML = '<p style="color:#888;">没有找到原料</p>';
            return;
        }
        currentIngredients.forEach(ingredient => {
            const card = document.createElement('div');
            card.classList.add('data-card');
            card.innerHTML = `
                <div class="data-card-content">
                    <h4>${ingredient.name}</h4>
                    <p>单位: ${ingredient.unit} | 分类: ${ingredient.category_name || '无'}</p>
                    <p>供应商: ${ingredient.supplier_name || '未知'}</p>
                    <p>价格: ${ingredient.price ? '¥' + ingredient.price : '未设置'} | 库存: ${ingredient.stock}</p>
                    <p>状态: ${ingredient.is_active ? '已启用' : '已禁用'}</p>
                </div>
                <div class="data-card-actions">
                    <input type="checkbox" class="ingredient-select" value="${ingredient.id}" onchange="syncIngredientsSelectAll()" title="选择">
                    <button class="btn btn-sm btn-success" onclick="showIngredientModal(${ingredient.id})">编辑</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteIngredient(${ingredient.id})">删除</button>
                </div>
            `;
            ingredientsList.appendChild(card);
        });
    } else {
        currentIngredients = [];
    }
}

async function showIngredientModal(ingredientId = null) {
    const modal = document.getElementById('ingredient-modal');
    const title = document.getElementById('ingredient-modal-title');
    const form = document.getElementById('ingredient-form');
    form.reset();
    document.getElementById('ingredient-id').value = '';
    document.getElementById('ingredient-active').checked = true;
    document.getElementById('ingredient-unit').value = '斤';
    document.getElementById('ingredient-stock').value = '0';

    // 加载供应商和分类选项
    await loadSuppliersForSelect();
    await loadCategoriesForSelect();

    if (ingredientId) {
        title.textContent = '编辑原料';
        const ingredient = await fetchData(`/admin/ingredients/${ingredientId}`);
        if (ingredient) {
            document.getElementById('ingredient-id').value = ingredient.id;
            document.getElementById('ingredient-name').value = ingredient.name;
            document.getElementById('ingredient-unit').value = ingredient.unit;
            document.getElementById('ingredient-supplier-id').value = ingredient.supplier_id;
            document.getElementById('ingredient-category-id').value = ingredient.category_id || '';
            document.getElementById('ingredient-price').value = ingredient.price || '';
            document.getElementById('ingredient-stock').value = ingredient.stock;
            document.getElementById('ingredient-active').checked = ingredient.is_active;
        }
    } else {
        title.textContent = '添加原料';
    }
    showModal('ingredient-modal');
}

async function loadSuppliersForSelect() {
    const suppliersData = await fetchData('/admin/suppliers');
    const select = document.getElementById('ingredient-supplier-id');
    select.innerHTML = '<option value="">请选择供应商</option>';
    if (suppliersData && suppliersData.suppliers) {
        suppliersData.suppliers.forEach(s => {
            const option = document.createElement('option');
            option.value = s.id;
            option.textContent = s.name;
            select.appendChild(option);
        });
    }
}

async function loadCategoriesForSelect() {
    const categoriesData = await fetchData('/admin/categories');
    const select1 = document.getElementById('ingredient-category-id');
    select1.innerHTML = '<option value="">请选择分类</option>';
    if (categoriesData && categoriesData.categories) {
        categoriesData.categories.forEach(c => {
            const option1 = document.createElement('option');
            option1.value = c.id;
            option1.textContent = c.name;
            select1.appendChild(option1);
        });
    }
}

document.getElementById('ingredient-form').addEventListener('submit', async function(event) {
    event.preventDefault();
    const ingredientId = document.getElementById('ingredient-id').value;
    const method = ingredientId ? 'PUT' : 'POST';
    const url = ingredientId ? `/admin/ingredients/${ingredientId}` : '/admin/ingredients';
    const data = {
        name: document.getElementById('ingredient-name').value,
        unit: document.getElementById('ingredient-unit').value,
        supplier_id: parseInt(document.getElementById('ingredient-supplier-id').value),
        category_id: document.getElementById('ingredient-category-id').value ? parseInt(document.getElementById('ingredient-category-id').value) : null,
        price: document.getElementById('ingredient-price').value ? parseFloat(document.getElementById('ingredient-price').value) : null,
        stock: parseInt(document.getElementById('ingredient-stock').value) || 0,
        is_active: document.getElementById('ingredient-active').checked,
    };

    const result = await fetchData(url, method, data);
    if (result) {
        alert('原料保存成功！');
        closeModal('ingredient-modal');
        await loadIngredients();
    }
});

async function deleteIngredient(ingredientId) {
    if (confirm('确定要删除此原料吗？')) {
        const result = await fetchData(`/admin/ingredients/${ingredientId}`, 'DELETE', null, true);
        if (result) {
            alert('原料删除成功！');
            await loadIngredients();
        }
    }
}

async function batchDeleteIngredients() {
    const ids = getSelectedIngredientIds();
    if (ids.length === 0) {
        alert('请先选择要删除的原料');
        return;
    }

    if (confirm(`确定要删除选中的 ${ids.length} 个原料吗？`)) {
        const result = await fetchData('/admin/ingredients/batch', 'DELETE', { ids }, true);
        if (result) {
            alert(`已删除 ${result.count || ids.length} 个原料！`);
            await loadIngredients();
        }
    }
}

// ==================== 商品原料配置 (Product Ingredients) ====================

let currentProductIdForIngredients = null;
let currentProductIngredientOptions = [];

async function showProductIngredientsModal(productId) {
    currentProductIdForIngredients = productId;
    document.getElementById('pi-product-id').value = productId;
    document.getElementById('pi-ingredient-id').value = '';
    document.getElementById('pi-ingredient-meta').textContent = '';
    document.getElementById('pi-quantity').value = '';
    
    // 加载原料选项
    await loadIngredientsForPiSelect();

    // 加载已配置的原料
    await loadProductIngredients();
    
    showModal('product-ingredients-modal');
}

async function loadIngredientsForPiSelect() {
    const ingredientsData = await fetchData('/admin/ingredients?is_active=true');
    const select = document.getElementById('pi-ingredient-id');
    select.innerHTML = '<option value="">请选择原料</option>';
    currentProductIngredientOptions = ingredientsData && ingredientsData.ingredients ? ingredientsData.ingredients : [];

    if (currentProductIngredientOptions.length === 0) {
        select.innerHTML = '<option value="">暂无可用原料</option>';
        updateProductIngredientMeta();
        return;
    }

    currentProductIngredientOptions.forEach(ingredient => {
        const option = document.createElement('option');
        const priceText = ingredient.price ? `¥${ingredient.price}` : '未设置单价';
        option.value = ingredient.id;
        option.textContent = `${ingredient.name} / ${ingredient.supplier_name || '未知供应商'} / ${ingredient.unit} / ${priceText}`;
        select.appendChild(option);
    });
    updateProductIngredientMeta();
}

function updateProductIngredientMeta() {
    const select = document.getElementById('pi-ingredient-id');
    const meta = document.getElementById('pi-ingredient-meta');
    if (!select || !meta) return;

    const selectedId = parseInt(select.value);
    const ingredient = currentProductIngredientOptions.find(item => item.id === selectedId);
    meta.textContent = ingredient
        ? `供应商: ${ingredient.supplier_name || '未知'} | 单位: ${ingredient.unit} | 单价: ${ingredient.price ? formatCurrency(ingredient.price) : '未设置'}`
        : '';
}

async function loadProductIngredients() {
    if (!currentProductIdForIngredients) return;
    
    const data = await fetchData(`/admin/products/${currentProductIdForIngredients}/ingredients`);
    const list = document.getElementById('product-ingredients-list');
    list.innerHTML = '';
    
    if (data && data.ingredients) {
        data.ingredients.forEach(pi => {
            const item = document.createElement('div');
            item.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:10px;border:1px solid #eee;border-radius:4px;margin-bottom:10px;';
            item.innerHTML = `
                <div>
                    <strong>${pi.ingredient_name}</strong>
                    <span style="color:#666;margin-left:10px;">${pi.quantity_needed} ${pi.ingredient_unit} / 份成品</span>
                    <span style="color:#999;margin-left:10px;">供应商: ${pi.supplier_name || '未知'}</span>
                    <span style="color:#999;margin-left:10px;">单价: ${pi.ingredient_price ? formatCurrency(pi.ingredient_price) : '未设置'}</span>
                </div>
                <button class="btn btn-sm btn-danger" onclick="deleteProductIngredient(${pi.id})">删除</button>
            `;
            list.appendChild(item);
        });
    }
}

async function addProductIngredient() {
    const ingredientId = document.getElementById('pi-ingredient-id').value;
    const quantity = document.getElementById('pi-quantity').value;
    
    if (!ingredientId || !quantity) {
        alert('请选择原料并填写数量！');
        return;
    }
    
    const result = await fetchData(`/admin/products/${currentProductIdForIngredients}/ingredients`, 'POST', {
        ingredient_id: parseInt(ingredientId),
        quantity_needed: parseFloat(quantity)
    }, true);
    
    if (result) {
        alert('原料添加成功！');
        document.getElementById('pi-ingredient-id').value = '';
        document.getElementById('pi-ingredient-meta').textContent = '';
        document.getElementById('pi-quantity').value = '';
        await loadProductIngredients();
    }
}

async function deleteProductIngredient(relationId) {
    if (confirm('确定要删除此原料配置吗？')) {
        const result = await fetchData(`/admin/products/${currentProductIdForIngredients}/ingredients/${relationId}`, 'DELETE');
        if (result) {
            alert('原料删除成功！');
            await loadProductIngredients();
        }
    }
}

// ==================== 供应商备货单管理 (Supplier Orders) ====================

let currentSupplierOrderStatusFilter = 'all';

document.querySelectorAll('#page-supplier-orders .tabs .tab').forEach(tab => {
    tab.addEventListener('click', function() {
        document.querySelectorAll('#page-supplier-orders .tabs .tab').forEach(t => t.classList.remove('active'));
        this.classList.add('active');
        currentSupplierOrderStatusFilter = this.dataset.status;
        loadSupplierOrders();
    });
});

function getSupplierOrderStatusText(status) {
    const statusMap = {
        10: '待备货',
        20: '备货中',
        30: '已完成',
        40: '已取消'
    };
    return statusMap[status] || '未知';
}

function renderAdminSupplierOrdersSummary(summary) {
    const summaryEl = document.getElementById('supplier-orders-summary');
    if (!summaryEl || !summary) return;

    const supplierTotals = (summary.supplier_totals || []).map(item => `
        <div class="stat-card">
            <h3>${item.supplier_name}</h3>
            <p class="number">${formatCurrency(item.today_total_cost)}</p>
        </div>
    `).join('');

    summaryEl.innerHTML = `
        <div class="stat-card">
            <h3>今日材料费用</h3>
            <p class="number">${formatCurrency(summary.today_total_cost)}</p>
        </div>
        <div class="stat-card">
            <h3>当前列表费用</h3>
            <p class="number">${formatCurrency(summary.filtered_total_cost)}</p>
        </div>
        <div class="stat-card">
            <h3>今日备货单</h3>
            <p class="number">${summary.today_order_count || 0}</p>
        </div>
        ${supplierTotals}
    `;
}

async function loadSupplierOrders() {
    let url = '/admin/supplier-orders';
    if (currentSupplierOrderStatusFilter !== 'all') {
        url += `?status=${currentSupplierOrderStatusFilter}`;
    }
    const ordersData = await fetchData(url);
    const ordersList = document.getElementById('supplier-orders-list');
    ordersList.innerHTML = '';
    renderAdminSupplierOrdersSummary(ordersData ? ordersData.summary : null);

    if (ordersData && ordersData.supplier_orders) {
        ordersData.supplier_orders.forEach(order => {
            const card = document.createElement('div');
            card.classList.add('data-card', `status-${order.status}`);
            const itemsHtml = order.items ? order.items.map(item => `
                <p>${item.ingredient_name} x ${item.quantity} ${item.unit} | 单价 ${formatCurrency(item.unit_price)} | 小计 ${formatCurrency(item.total_price)}</p>
            `).join('') : '';
            card.innerHTML = `
                <div class="data-card-content">
                    <h4>备货单 #${order.id} <span style="float:right;color:#666;">${getSupplierOrderStatusText(order.status)}</span></h4>
                    <p>关联订单号: ${order.order_sn}</p>
                    <p>供应商: ${order.supplier_name || '未知'}</p>
                    <p>材料费用: ${formatCurrency(order.total_cost)}</p>
                    <p>备注: ${order.notes || '无'}</p>
                    <div style="margin-top:10px;padding-top:10px;border-top:1px solid #eee;">
                        ${itemsHtml}
                    </div>
                    <p style="font-size:12px;color:#999;margin-top:10px;">创建时间: ${formatDate(order.created_at)}</p>
                </div>
                <div class="data-card-actions">
                    <button class="btn btn-sm btn-success" onclick="editSupplierOrderStatus(${order.id})">修改状态</button>
                </div>
            `;
            ordersList.appendChild(card);
        });
    }
}

async function editSupplierOrderStatus(orderId) {
    const newStatus = prompt('请输入新的备货单状态 (10=待备货, 20=备货中, 30=已完成, 40=已取消):');
    if (newStatus && !isNaN(newStatus)) {
        const result = await fetchData(`/admin/supplier-orders/${orderId}/status`, 'PUT', { status: parseInt(newStatus) });
        if (result) {
            alert('备货单状态更新成功！');
            await loadSupplierOrders();
        }
    }
}

// ==================== 初始化 ====================

function setupIngredientControls() {
    const search = document.getElementById('ingredient-search');
    const statusFilter = document.getElementById('ingredient-status-filter');
    const productIngredientSelect = document.getElementById('pi-ingredient-id');

    if (search) {
        search.addEventListener('keydown', event => {
            if (event.key === 'Enter') {
                event.preventDefault();
                loadIngredients();
            }
        });
    }
    if (statusFilter) {
        statusFilter.addEventListener('change', loadIngredients);
    }
    if (productIngredientSelect) {
        productIngredientSelect.addEventListener('change', updateProductIngredientMeta);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    setupIngredientControls();
    renderPage();
});
