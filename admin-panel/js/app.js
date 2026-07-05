// 配置后端API基础URL
const BASE_URL = 'http://xianpeiju.site';

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
        case 'products':
            await loadProducts();
            break;
        case 'categories':
            await loadCategories();
            break;
        case 'delivery-zones':
            await loadDeliveryZones();
            break;
        case 'orders':
            await loadOrders();
            break;
    }
}

// ==================== 仪表盘 (Dashboard) ====================

async function loadDashboardStats() {
    try {
        const products = await fetchData('/admin/products');
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
    const productsData = await fetchData('/admin/products');
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
                    <button class="btn btn-sm btn-success" onclick="editProduct(${product.id})">编辑</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteProduct(${product.id})">删除</button>
                </div>
            `;
            productsList.appendChild(card);
        });
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
    }
});

async function deleteProduct(productId) {
    if (confirm('确定要删除此商品吗？')) {
        const result = await fetchData(`/admin/products/${productId}`, 'DELETE');
        if (result) {
            alert('商品删除成功！');
            await loadProducts();
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
                    <button class="btn btn-sm btn-success" onclick="editCategory(${category.id})">编辑</button>
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
                    <button class="btn btn-sm btn-success" onclick="editDeliveryZone(${zone.id})">编辑</button>
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

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', () => {
    renderPage();
});
