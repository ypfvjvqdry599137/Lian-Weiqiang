// 配置后端 API 基础 URL
const BASE_URL = 'http://xianpeiju.site'; // 替换为您的后端域名

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
                // 忽略JSON解析错误
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
        40: '待自提',
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
        case 'stations':
            await loadStations();
            break;
        case 'orders':
            await loadOrders();
            break;
    }
}

// ==================== 仪表盘 (Dashboard) ====================

async function loadDashboardStats() {
    try {
        // 先加载产品和站点数量
        const products = await fetchData('/admin/products');
        if(products) {
            document.getElementById('stat-products').textContent = products.products.length;
        }
        
        const stations = await fetchData('/admin/stations');
        if(stations) {
            document.getElementById('stat-stations').textContent = stations.stations.length;
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
        console.error('Dashboard 加载失败', e);
        // 不弹窗，保持界面显示
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
    form.reset(); // 重置表单
    document.getElementById('product-id').value = '';
    document.getElementById('product-recommend').checked = false;
    document.getElementById('product-active').checked = true; // 默认上架
    document.getElementById('product-warning-stock').value = 10; // 默认预警值

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
    document.getElementById('category-active').checked = true; // 默认启用

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

// ==================== 自提点管理 (Stations) ====================

async function loadStations() {
    const stationsData = await fetchData('/admin/stations');
    const stationsList = document.getElementById('stations-list');
    stationsList.innerHTML = '';

    if (stationsData && stationsData.stations) {
        stationsData.stations.forEach(station => {
            const card = document.createElement('div');
            card.classList.add('data-card');
            card.innerHTML = `
                <div class="data-card-content">
                    <h4>${station.station_name}</h4>
                    <p>${station.address}</p>
                    <p>合作商: ${station.merchant_username} | 佣金: ${station.commission_rate}%</p>
                </div>
                <div class="data-card-actions">
                    <button class="btn btn-sm btn-success" onclick="editStation(${station.id})">编辑</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteStation(${station.id})">删除</button>
                </div>
            `;
            stationsList.appendChild(card);
        });
    }
}

async function showStationModal(stationId = null) {
    const modal = document.getElementById('station-modal');
    const title = document.getElementById('station-modal-title');
    const form = document.getElementById('station-form');
    form.reset();
    document.getElementById('station-id').value = '';

    if (stationId) {
        title.textContent = '编辑自提点';
        const station = await fetchData(`/admin/stations/${stationId}`);
        if (station) {
            document.getElementById('station-id').value = station.id;
            document.getElementById('station-name').value = station.station_name;
            document.getElementById('station-address').value = station.address;
            document.getElementById('station-merchant-user').value = station.merchant_username;
            // document.getElementById('station-merchant-pwd').value = station.merchant_password; // 密码不回显
            document.getElementById('station-commission').value = station.commission_rate;
        }
    } else {
        title.textContent = '添加自提点';
    }
    showModal('station-modal');
}

document.getElementById('station-form').addEventListener('submit', async function(event) {
    event.preventDefault();
    const stationId = document.getElementById('station-id').value;
    const method = stationId ? 'PUT' : 'POST';
    const url = stationId ? `/admin/stations/${stationId}` : '/admin/stations';
    const data = {
        station_name: document.getElementById('station-name').value,
        address: document.getElementById('station-address').value,
        merchant_username: document.getElementById('station-merchant-user').value,
        merchant_password: document.getElementById('station-merchant-pwd').value, // 新增或修改密码
        commission_rate: parseFloat(document.getElementById('station-commission').value) || 0,
    };
    
    // 编辑时如果密码为空，则不发送密码字段
    if (method === 'PUT' && !data.merchant_password) {
        delete data.merchant_password;
    }

    const result = await fetchData(url, method, data);
    if (result) {
        alert('自提点保存成功！');
        closeModal('station-modal');
        await loadStations();
    }
});

async function deleteStation(stationId) {
    if (confirm('确定要删除此自提点吗？')) {
        const result = await fetchData(`/admin/stations/${stationId}`, 'DELETE');
        if (result) {
            alert('自提点删除成功！');
            await loadStations();
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
                    <p>自提点ID: ${order.station_id} | 总金额: ¥${order.total_amount}</p>
                    <p>收货人: ${order.receiver_name} | 电话: ${order.receiver_phone}</p>
                    <p>自提时间: ${order.pickup_time}</p>
                    <div style="margin-top:10px;padding-top:10px;border-top:1px solid #eee;">
                        ${itemsHtml}
                    </div>
                    <p style="font-size:12px;color:#999;margin-top:10px;">下单时间: ${formatDate(order.created_at)}</p>
                </div>
                <div class="data-card-actions">
                    <button class="btn btn-sm btn-success" onclick="editOrderStatus('${order.order_sn}')">修改状态</button>
                    <!-- <button class="btn btn-sm btn-danger" onclick="deleteOrder('${order.order_sn}')">删除</button> -->
                </div>
            `;
            ordersList.appendChild(card);
        });
    }
}

async function editOrderStatus(orderSn) {
    const newStatus = prompt('请输入新的订单状态 (10=待付款, 20=待配货, 30=配送中, 40=待自提, 50=已完成, 60=已关闭):');
    if (newStatus && !isNaN(newStatus)) {
        const result = await fetchData(`/admin/orders/${orderSn}/status`, 'PUT', { status: parseInt(newStatus) });
        if (result) {
            alert('订单状态更新成功！');
            await loadOrders();
            await loadDashboardStats(); // 刷新仪表盘
        }
    }
}

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', () => {
    renderPage();
});
