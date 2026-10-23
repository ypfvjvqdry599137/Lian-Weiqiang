// 配置后端API基础URL
const BASE_URL = window.location.origin && window.location.origin !== 'null'
    ? window.location.origin
    : 'https://xianpeiju.site';
const ADMIN_TOKEN_KEY = 'freshProduceAdminToken';

function adminToken() {
    return sessionStorage.getItem(ADMIN_TOKEN_KEY);
}

function requireAdminLogin() {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    window.location.replace('/admin-panel/login.html');
}

// ==================== 腾讯地图选点 ====================
let map = null;
let markerLayer = null;
let circleLayer = null;
let selectedLng = null;
let selectedLat = null;
let tencentMapSdkPromise = null;
let mapSearchResults = [];

function getZoneRadiusValue() {
    const radius = parseInt(document.getElementById('zone-radius')?.value, 10);
    return Number.isFinite(radius) && radius > 0 ? radius : 3000;
}

function updateMapPickStatus(message, isError = false) {
    const status = document.getElementById('map-pick-status');
    if (!status) return;
    status.textContent = message || '';
    status.classList.toggle('error', !!isError);
}

async function loadTencentMapSdk() {
    if (window.TMap) {
        return true;
    }
    if (!tencentMapSdkPromise) {
        tencentMapSdkPromise = (async () => {
            const config = await fetchData('/admin/map/config');
            if (!config || !config.enabled || !config.key) {
                throw new Error('请先在服务器环境变量 TENCENT_MAP_JS_KEY 配置腾讯地图前端 Key');
            }
            await new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.charset = 'utf-8';
                script.src = `https://map.qq.com/api/gljs?v=1.exp&key=${encodeURIComponent(config.key)}`;
                script.onload = resolve;
                script.onerror = () => reject(new Error('腾讯地图 SDK 加载失败'));
                document.head.appendChild(script);
            });
            return true;
        })();
    }
    return tencentMapSdkPromise;
}

function setLayerGeometries(layer, geometries) {
    if (layer && typeof layer.setGeometries === 'function') {
        layer.setGeometries(geometries);
    }
}

function ensureMarkerLayer(position) {
    const geometries = [{
        id: 'zone-center',
        styleId: 'marker',
        position,
        properties: { title: '配送中心点' }
    }];

    if (!markerLayer) {
        markerLayer = new TMap.MultiMarker({
            id: 'zone-center-marker',
            map,
            styles: {
                marker: new TMap.MarkerStyle({
                    width: 25,
                    height: 35,
                    src: 'https://mapapi.qq.com/web/lbs/javascriptGL/demo/img/markerDefault.png'
                })
            },
            geometries
        });
    } else {
        setLayerGeometries(markerLayer, geometries);
    }
}

function ensureCircleLayer(position) {
    if (!window.TMap || !TMap.MultiCircle) {
        return;
    }

    const geometries = [{
        id: 'zone-radius',
        styleId: 'radius',
        center: position,
        radius: getZoneRadiusValue()
    }];

    try {
        if (!circleLayer) {
            circleLayer = new TMap.MultiCircle({
                id: 'zone-radius-circle',
                map,
                styles: {
                    radius: {
                        color: 'rgba(76, 175, 80, 0.16)',
                        showBorder: true,
                        borderColor: 'rgba(76, 175, 80, 0.9)',
                        borderWidth: 2
                    }
                },
                geometries
            });
        } else {
            setLayerGeometries(circleLayer, geometries);
        }
    } catch (error) {
        console.warn('配送半径圈绘制失败:', error);
    }
}

function setMapPoint(lat, lng, recenter = true) {
    selectedLat = Number(lat).toFixed(6);
    selectedLng = Number(lng).toFixed(6);
    const position = new TMap.LatLng(parseFloat(selectedLat), parseFloat(selectedLng));

    ensureMarkerLayer(position);
    ensureCircleLayer(position);

    const selectedText = document.getElementById('map-selected-point');
    if (selectedText) {
        selectedText.textContent = `已选择：${selectedLng}, ${selectedLat}，半径 ${getZoneRadiusValue()} 米`;
    }
    if (recenter && map) {
        map.setCenter(position);
    }
}

function initTencentMap() {
    if (map) return;

    const currentLng = parseFloat(document.getElementById('zone-center-lng').value);
    const currentLat = parseFloat(document.getElementById('zone-center-lat').value);
    const hasCurrentPoint = Number.isFinite(currentLng) && Number.isFinite(currentLat);
    const center = hasCurrentPoint
        ? new TMap.LatLng(currentLat, currentLng)
        : new TMap.LatLng(39.9042, 116.4074);

    map = new TMap.Map(document.getElementById('map-container'), {
        center,
        zoom: hasCurrentPoint ? 14 : 11,
        pitch: 0,
        rotation: 0
    });

    map.on('click', (evt) => {
        setMapPoint(evt.latLng.getLat(), evt.latLng.getLng());
        updateMapPickStatus('已更新配送中心点，确认后会写入表单。');
    });
}

async function showMapPicker() {
    try {
        await loadTencentMapSdk();
    } catch (error) {
        alert(`${error.message}\n\n现在仍可手动填写经纬度；配置好腾讯地图 Key 后可使用地图选点。`);
        return;
    }

    clearMapSearchResults();
    document.getElementById('map-modal').classList.add('show');
    setTimeout(() => {
        initTencentMap();
        if (map && typeof map.resize === 'function') {
            map.resize();
        }

        const currentLng = parseFloat(document.getElementById('zone-center-lng').value);
        const currentLat = parseFloat(document.getElementById('zone-center-lat').value);
        if (Number.isFinite(currentLng) && Number.isFinite(currentLat)) {
            setMapPoint(currentLat, currentLng);
            updateMapPickStatus('已加载当前配送中心点，可点击地图重新选择。');
        } else {
            updateMapPickStatus('搜索地址或直接点击地图选择配送中心点。');
        }
    }, 120);
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}

function clearMapSearchResults() {
    mapSearchResults = [];
    const container = document.getElementById('map-search-results');
    if (!container) return;
    container.classList.remove('show');
    container.innerHTML = '';
}

function formatMapResultAddress(result) {
    const parts = [result.province, result.city, result.district, result.address]
        .filter(Boolean)
        .map(part => String(part).trim())
        .filter(Boolean);
    return [...new Set(parts)].join(' ');
}

function renderMapSearchResults(results) {
    const container = document.getElementById('map-search-results');
    if (!container) return;
    container.innerHTML = '';
    if (!results || results.length <= 1) {
        container.classList.remove('show');
        return;
    }

    results.forEach((result, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `map-result-item${index === 0 ? ' active' : ''}`;
        button.onclick = () => selectMapSearchResult(index);
        button.innerHTML = `
            <span class="map-result-title">${index + 1}. ${escapeHtml(result.title || '未命名地址')}</span>
            <span class="map-result-address">${escapeHtml(formatMapResultAddress(result) || `${result.lng}, ${result.lat}`)}</span>
        `;
        container.appendChild(button);
    });
    container.classList.add('show');
}

function selectMapSearchResult(index) {
    const result = mapSearchResults[index];
    if (!result || result.lng == null || result.lat == null) return;
    document.querySelectorAll('.map-result-item').forEach((item, itemIndex) => {
        item.classList.toggle('active', itemIndex === index);
    });
    setMapPoint(result.lat, result.lng);
    updateMapPickStatus(`已选择：${result.title || result.address || '候选地址'}，确认后会写入表单。`);
}

async function searchMapAddress() {
    const input = document.getElementById('map-search-input');
    const keyword = input ? input.value.trim() : '';
    if (!keyword) {
        clearMapSearchResults();
        updateMapPickStatus('请输入要搜索的地址。', true);
        return;
    }

    clearMapSearchResults();
    updateMapPickStatus('正在通过腾讯地图搜索地址...');
    const result = await fetchData(`/admin/map/geocode?address=${encodeURIComponent(keyword)}`, 'GET', null, false);
    if (!result) {
        updateMapPickStatus(window.lastFetchError || '没有找到有效坐标，请输入城市 + 小区名，或直接点击地图选点。', true);
        return;
    }

    const results = Array.isArray(result.results) && result.results.length > 0
        ? result.results
        : (result.lng != null && result.lat != null ? [result] : []);
    if (results.length === 0) {
        updateMapPickStatus('没有解析到有效坐标，请换一个更完整的地址。', true);
        return;
    }

    mapSearchResults = results;
    renderMapSearchResults(results);
    selectMapSearchResult(0);
    if (results.length > 1) {
        updateMapPickStatus(`找到 ${results.length} 个候选地址，请从列表中选择正确地址。`);
    }
}
function handleMapSearchKeydown(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        searchMapAddress();
    }
}

function confirmMapPick() {
    if (!selectedLng || !selectedLat) {
        alert('请先搜索地址或点击地图选择配送中心点');
        return;
    }
    document.getElementById('zone-center-lng').value = selectedLng;
    document.getElementById('zone-center-lat').value = selectedLat;
    closeMapModal();
}

function closeMapModal() {
    document.getElementById('map-modal').classList.remove('show');
}

document.addEventListener('input', (event) => {
    if (event.target && event.target.id === 'zone-radius' && map && selectedLat && selectedLng) {
        setMapPoint(selectedLat, selectedLng, false);
    }
});
// ==================== 辅助函数 ====================

async function fetchData(url, method = 'GET', data = null, showAlert = false) {
    const fullUrl = BASE_URL + url;
    
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${adminToken() || ''}`,
        },
    };
    if (data) {
        options.body = JSON.stringify(data);
    }

    window.lastFetchError = '';
    try {
        const response = await fetch(fullUrl, options);
        if (response.status === 401) {
            requireAdminLogin();
            return null;
        }
        
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
        return result;
    } catch (error) {
        console.error('请求失败:', error);
        window.lastFetchError = error.message;
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

function getCurrentMonthValue() {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    return `${now.getFullYear()}-${month}`;
}

function getMonthInputValue(inputId) {
    const input = document.getElementById(inputId);
    if (!input.value) {
        input.value = getCurrentMonthValue();
    }
    return input.value;
}
function formatZoneName(zoneName) {
    return zoneName || '通用区域';
}

function formatSupplierServiceZones(zoneNames) {
    return zoneNames && zoneNames.length > 0 ? zoneNames.join('、') : '未配置';
}

function getSelectedNumberValues(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return [];
    return Array.from(container.querySelectorAll('input[type="checkbox"]:checked'))
        .map(input => parseInt(input.value, 10))
        .filter(value => !Number.isNaN(value));
}

function renderSupplierCheckboxOptions(container, options, selectedIds, emptyMessage) {
    const selectedSet = new Set((selectedIds || []).map(Number));
    container.replaceChildren();
    if (!options.length) {
        const empty = document.createElement('span');
        empty.className = 'supplier-option-empty';
        empty.textContent = emptyMessage;
        container.appendChild(empty);
        return;
    }

    options.forEach(option => {
        const label = document.createElement('label');
        label.className = 'supplier-option';
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = option.id;
        checkbox.checked = selectedSet.has(Number(option.id));
        const text = document.createElement('span');
        text.textContent = option.label;
        label.append(checkbox, text);
        container.appendChild(label);
    });
}

const ORDER_STATUS_OPTIONS = [
    { value: 10, label: '待付款' },
    { value: 20, label: '待配货' },
    { value: 30, label: '配送中' },
    { value: 40, label: '已送达' },
    { value: 50, label: '已完成' },
    { value: 60, label: '已取消' }
];

const SUPPLIER_ORDER_STATUS_OPTIONS = [
    { value: 10, label: '待备货' },
    { value: 20, label: '备货中' },
    { value: 30, label: '已完成' },
    { value: 40, label: '已取消' }
];

function renderStatusOptions(options, currentValue) {
    const value = Number(currentValue);
    return options.map(option => `
        <option value="${option.value}" ${option.value === value ? 'selected' : ''}>${option.label}</option>
    `).join('');
}

function renderOrderStatusSelect(order) {
    if (order.display_status === 70) {
        return `
            <div class="status-control">
                <span>订单状态</span>
                <strong class="status-readonly">${escapeHtml(order.status_text)}</strong>
            </div>
        `;
    }
    const orderSnArg = escapeHtml(JSON.stringify(order.order_sn));
    return `
        <label class="status-control">
            <span>订单状态</span>
            <select class="status-select" data-current="${Number(order.order_status)}" onchange="updateOrderStatusFromSelect(${orderSnArg}, this)">
                ${renderStatusOptions(ORDER_STATUS_OPTIONS, order.order_status)}
            </select>
        </label>
    `;
}

function renderSupplierOrderStatusSelect(order) {
    return `
        <label class="status-control">
            <span>备货状态</span>
            <select class="status-select" data-current="${order.status}" onchange="updateSupplierOrderStatusFromSelect(${order.id}, this)">
                ${renderStatusOptions(SUPPLIER_ORDER_STATUS_OPTIONS, order.status)}
            </select>
        </label>
    `;
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
        case 'price-reviews':
            await loadPriceReviews();
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
        case 'stations':
            await loadStations();
            break;
        case 'zone-supply-rules':
            await loadZoneSupplyRules();
            break;
        case 'fulfillment-issues':
            await loadFulfillmentIssues();
            break;
        case 'zone-statistics':
            await loadZoneStatistics();
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

function getSelectedProductIds() {
    return Array.from(document.querySelectorAll('.product-select:checked'))
        .map(input => Number(input.value));
}

function syncProductSelection() {
    const checkboxes = Array.from(document.querySelectorAll('.product-select'));
    const selectedCount = checkboxes.filter(input => input.checked).length;
    const selectAll = document.getElementById('products-select-all');
    selectAll.checked = checkboxes.length > 0 && selectedCount === checkboxes.length;
    selectAll.indeterminate = selectedCount > 0 && selectedCount < checkboxes.length;
    selectAll.disabled = checkboxes.length === 0;
    document.getElementById('products-selected-count').textContent = `已选 ${selectedCount} 个`;
    document.getElementById('products-batch-delete').disabled = selectedCount === 0;
}

function toggleProductSelection(checked) {
    document.querySelectorAll('.product-select').forEach(input => {
        input.checked = checked;
    });
    syncProductSelection();
}

async function loadProducts() {
    const productsData = await fetchData('/admin/products?is_active=true');
    const productsList = document.getElementById('products-list');
    productsList.innerHTML = '';

    if (productsData && productsData.products) {
        productsData.products.forEach(product => {
            const card = document.createElement('div');
            card.classList.add('data-card');
            card.innerHTML =
                '<div class="data-card-content">' +
                    '<h4>' + escapeHtml(product.name) + '</h4>' +
                    '<p>' + escapeHtml(product.description || '无描述') + '</p>' +
                    '<p class="price">¥' + escapeHtml(product.price) + ' / ' + escapeHtml(product.unit) + '</p>' +
                    ((product.is_preorder || product.has_processing_options)
                        ? '<p>' +
                            (product.is_preorder ? '预定商品' : '') +
                            (product.is_preorder && product.has_processing_options ? ' · ' : '') +
                            (product.has_processing_options ? ('加工 ' + product.processing_options.length + ' 项') : '') +
                          '</p>'
                        : '') +
                    '<p>库存: ' + escapeHtml(product.available_stock) + '</p>' +
                '</div>' +
                '<div class="data-card-actions">' +
                    '<input type="checkbox" class="product-select" value="' + product.id + '" onchange="syncProductSelection()" aria-label="选择' + escapeHtml(product.name) + '">' +
                    '<button class="btn btn-sm btn-primary" onclick="showProductIngredientsModal(' + product.id + ')">配置原料</button>' +
                    '<button class="btn btn-sm btn-success" onclick="showProductModal(' + product.id + ')">编辑</button>' +
                    '<button class="btn btn-sm btn-danger" onclick="deleteProduct(' + product.id + ')">删除</button>' +
                '</div>';
            productsList.appendChild(card);
        });
    }
    syncProductSelection();
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

function formatProcessingOptionsText(value) {
    if (!value) {
        return '';
    }

    if (Array.isArray(value)) {
        return value.map(item => String(item || '').trim()).filter(Boolean).join('\n');
    }

    if (typeof value === 'string') {
        try {
            const parsed = JSON.parse(value);
            if (Array.isArray(parsed)) {
                return parsed.map(item => String(item || '').trim()).filter(Boolean).join('\n');
            }
        } catch (error) {
            return value;
        }
    }

    return '';
}

function parseProcessingOptionsText(value) {
    return String(value || '')
        .split(/\r?\n/)
        .map(item => item.trim())
        .filter(Boolean);
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
        if (compressedFile.size > 7 * 1024 * 1024) {
            throw new Error('图片压缩后仍超过 7MB，请选择较小的图片');
        }
        const formData = new FormData();
        formData.append('image', compressedFile, compressedFile.name);

        const response = await fetch(`${BASE_URL}/admin/uploads/product-image`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${adminToken() || ''}` },
            body: formData
        });
        if (response.status === 401) {
            requireAdminLogin();
            return;
        }
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
    document.getElementById('product-preorder').checked = false;
    document.getElementById('product-preorder-note').value = '';
    document.getElementById('product-processing-options').value = '';
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
            document.getElementById('product-preorder').checked = !!product.is_preorder;
            document.getElementById('product-preorder-note').value = product.preorder_note || '';
            document.getElementById('product-processing-options').value = formatProcessingOptionsText(product.processing_options);
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
        is_preorder: document.getElementById('product-preorder').checked,
        preorder_note: document.getElementById('product-preorder-note').value.trim(),
        processing_options: parseProcessingOptionsText(document.getElementById('product-processing-options').value),
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

async function batchDeleteProducts() {
    const ids = getSelectedProductIds();
    if (!ids.length) return;
    if (!confirm(`确定要批量删除选中的 ${ids.length} 个商品吗？\n此操作只会下架商品，不删除历史订单或已上传图片。`)) return;

    const button = document.getElementById('products-batch-delete');
    button.disabled = true;
    const result = await fetchData('/admin/products/batch', 'DELETE', { ids }, true);
    if (result) {
        alert(`已下架 ${result.count} 个商品`);
        await loadProducts();
        await loadDashboardStats();
    } else {
        button.disabled = false;
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

async function loadDeliveryZonesForFilter(selectId, options = {}) {
    const zonesData = await fetchData('/admin/delivery-zones');
    const select = document.getElementById(selectId);
    if (!select) return;

    const currentValue = select.value;
    const includeUnassigned = options.includeUnassigned !== false;
    select.innerHTML = '<option value="all">全部区域</option>';
    if (includeUnassigned) {
        select.innerHTML += '<option value="unassigned">未分配区域</option>';
    }

    if (zonesData && zonesData.zones) {
        zonesData.zones.forEach(zone => {
            const option = document.createElement('option');
            option.value = zone.id;
            option.textContent = zone.zone_name;
            select.appendChild(option);
        });
    }

    if (currentValue && Array.from(select.options).some(option => option.value === currentValue)) {
        select.value = currentValue;
    }
}
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
                    <p>配送站: ${zone.station_name || '未配置'}${zone.station_address ? ` | ${zone.station_address}` : ''}</p>
                    <p>区域后台: <a href="/admin-panel/merchant_login.html" target="_blank">打开登录入口</a></p>
                    <p>状态: ${zone.is_active ? '启用' : '禁用'}</p>
                </div>
                <div class="data-card-actions">
                    <button class="btn btn-sm btn-success" onclick="showDeliveryZoneModal(${zone.id})">编辑区域</button>
                    <button class="btn btn-sm btn-primary" onclick="${zone.station_id ? `showStationModal(${zone.station_id}, ${zone.id})` : `showStationModal(null, ${zone.id})`}">${zone.station_id ? '编辑配送站' : '配置配送站'}</button>
                    <button class="btn btn-sm btn-success" onclick="openZoneSupplyRulesForZone(${zone.id})">查看配送站规则</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteDeliveryZone(${zone.id})">删除区域</button>
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

document.querySelectorAll('#page-orders .tabs .tab').forEach(tab => {
    tab.addEventListener('click', function() {
        document.querySelectorAll('#page-orders .tabs .tab').forEach(t => t.classList.remove('active'));
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
            card.classList.add('data-card', `status-${order.display_status}`);
            const orderSnArg = escapeHtml(JSON.stringify(order.order_sn));
            const amountArg = escapeHtml(JSON.stringify(String(order.final_amount)));
            const refund = order.refund_summary;
            const refundLabels = {
                REQUESTED: '待人工退款，配送已暂停',
                APPLYING: '退款申请待确认，配送已暂停',
                PROCESSING: '退款处理中',
                SUCCESS: '退款成功',
                CLOSED: '退款已关闭',
                ABNORMAL: '退款异常，需人工处理'
            };
            const itemsHtml = order.items ? order.items.map(item => `
                <p>${escapeHtml(item.product_name)} x ${escapeHtml(item.quantity)}</p>
            `).join('') : '';
            card.innerHTML = `
                <div class="data-card-content">
                    <h4>订单号: ${escapeHtml(order.order_sn)} <span style="float:right;color:#666;">${escapeHtml(order.status_text)}</span></h4>
                    <p>配送区域: ${escapeHtml(order.zone_name || order.zone_id || '未分配')} | 总金额: ¥${escapeHtml(order.total_amount)} | 配送费: ¥${escapeHtml(order.delivery_fee)} | 实付: ${formatCurrency(order.final_amount)}</p>
                    <p>收货人: ${escapeHtml(order.receiver_name)} | 电话: ${escapeHtml(order.receiver_phone)}</p>
                    <p>收货地址: ${escapeHtml(order.receiver_address)}</p>
                    ${refund ? `<p>退款：${refundLabels[refund.status] || '状态未知'}${refund.out_refund_no ? `，商户退款单号：${escapeHtml(refund.out_refund_no)}` : ''}${refund.refund_channel ? `，微信返回渠道：${{ ORIGINAL: '原路', BALANCE: '余额', OTHER_BALANCE: '其他余额账户', OTHER_BANKCARD: '其他银行卡' }[refund.refund_channel] || '待核对'}` : ''}</p>` : ''}
                    <div style="margin-top:10px;padding-top:10px;border-top:1px solid #eee;">
                        ${itemsHtml}
                    </div>
                    <p style="font-size:12px;color:#999;margin-top:10px;">下单时间: ${escapeHtml(formatDate(order.created_at))}</p>
                </div>
                <div class="data-card-actions">
                    ${renderOrderStatusSelect(order)}
                    ${order.can_request_refund ? `<button class="btn btn-sm btn-danger" onclick="openWechatRefundModal(${orderSnArg}, ${amountArg}, false)">向微信申请整单退款</button>` : ''}
                    ${order.can_retry_wechat_refund ? `<button class="btn btn-sm btn-danger" onclick="openWechatRefundModal(${orderSnArg}, ${amountArg}, true)">沿用原退款单号重试</button>` : ''}
                    ${order.can_request_refund ? `<button class="btn btn-sm" onclick="requestManualRefund(${orderSnArg})">创建人工退款待办</button>` : ''}
                    ${order.can_verify_refund ? (refund.out_refund_no && refund.out_refund_no.startsWith('AR') ? `<button class="btn btn-sm" onclick="refreshWechatRefund(${orderSnArg}, ${escapeHtml(JSON.stringify(refund.out_refund_no))})">查询微信退款结果</button>` : `<button class="btn btn-sm" onclick="verifyManualRefund(${orderSnArg}, ${escapeHtml(JSON.stringify(refund.out_refund_no || ''))}, ${refund.status === 'REQUESTED'})">${refund.status === 'REQUESTED' ? '填写退款单号并核验' : '刷新退款核验'}</button>`) : ''}
                    ${order.can_delete ? `<button class="btn btn-sm btn-danger" onclick="deleteOrder(${orderSnArg})">删除已取消订单</button>` : ''}
                </div>
            `;
            ordersList.appendChild(card);
        });
    }
}

let pendingWechatRefund = null;

function openWechatRefundModal(orderSn, amount, retry) {
    pendingWechatRefund = { orderSn, amount, retry };
    document.getElementById('wechat-refund-title').textContent = retry ? '重试原微信退款申请' : '微信原路退款';
    document.getElementById('wechat-refund-summary').textContent = `订单 ${orderSn}，整单实付 ${formatCurrency(amount)}。${retry ? '只会沿用原商户退款单号，不会生成新的退款单。' : ''}`;
    document.getElementById('wechat-refund-form').reset();
    document.getElementById('wechat-refund-reason-group').style.display = retry ? 'none' : '';
    document.getElementById('wechat-refund-reason').required = !retry;
    document.getElementById('wechat-refund-modal').classList.add('show');
}

function closeWechatRefundModal() {
    document.getElementById('wechat-refund-modal').classList.remove('show');
    document.getElementById('wechat-refund-form').reset();
    pendingWechatRefund = null;
}

async function submitWechatRefund(event) {
    event.preventDefault();
    if (!pendingWechatRefund) return;
    const { orderSn, amount, retry } = pendingWechatRefund;
    const enteredOrder = document.getElementById('wechat-refund-confirm-order').value.trim();
    if (enteredOrder !== orderSn) {
        alert('订单号不一致，未发起退款');
        return;
    }
    const button = document.getElementById('wechat-refund-submit');
    button.disabled = true;
    const payload = {
        confirm_order_sn: enteredOrder,
        confirm_amount_fen: Math.round(Number(amount) * 100),
        admin_password: document.getElementById('wechat-refund-password').value,
    };
    if (!retry) payload.reason = document.getElementById('wechat-refund-reason').value.trim();
    try {
        const result = await fetchData(`/admin/orders/${orderSn}/wechat-refunds`, 'POST', payload, true);
        if (result) {
            closeWechatRefundModal();
            alert(`${result.message}\n商户退款单号：${result.refund.out_refund_no}\n微信状态：${result.refund.status}`);
        }
        await loadOrders();
    } finally {
        document.getElementById('wechat-refund-password').value = '';
        button.disabled = false;
    }
}

async function refreshWechatRefund(orderSn, refundNo) {
    const result = await fetchData(`/admin/orders/${orderSn}/manual-refunds`, 'POST', { out_refund_no: refundNo }, true);
    if (result) {
        alert(`微信退款状态：${result.refund.status}。只有 SUCCESS 才表示退款成功。`);
        await loadOrders();
    }
}

async function requestManualRefund(orderSn) {
    const note = prompt('填写退款原因和操作人员（不要填写密码或密钥）。创建后立即暂停备货和配送，但不会向微信发起退款。');
    if (note === null || !note.trim()) return;
    if (!confirm('确认先暂停这笔订单的履约？创建待办本身不会转钱，随后仍须去微信商户平台人工退款。')) return;

    const result = await fetchData(`/admin/orders/${orderSn}/manual-refund-requests`, 'POST', {
        operator_note: note.trim()
    }, true);
    if (result) {
        alert(result.message);
        await loadOrders();
    }
}

async function verifyManualRefund(orderSn, currentRefundNo, hasRequest) {
    const refundNo = prompt('请先确认已在微信商户平台人工操作退款，再输入商户退款单号。此按钮只查询核验，不会发起退款。', currentRefundNo || '');
    if (refundNo === null || !refundNo.trim()) return;

    let note = null;
    if (!hasRequest && refundNo.trim() !== currentRefundNo) {
        note = prompt('首次登记请填写操作备注（例如退款原因和操作人员），不要填写密码或密钥。');
        if (note === null) return;
    }

    const result = await fetchData(`/admin/orders/${orderSn}/manual-refunds`, 'POST', {
        out_refund_no: refundNo.trim(),
        operator_note: note
    }, true);
    if (result) {
        alert(`${result.message}\n微信退款状态：${result.refund.status}`);
        await loadOrders();
    }
}

async function updateOrderStatusFromSelect(orderSn, selectEl) {
    const previousStatus = parseInt(selectEl.dataset.current, 10);
    const nextStatus = parseInt(selectEl.value, 10);
    if (nextStatus === previousStatus) return;

    selectEl.disabled = true;
    const result = await fetchData(`/admin/orders/${orderSn}/status`, 'PUT', { status: nextStatus }, true);
    if (result) {
        alert(result.message || '订单状态更新成功');
        await loadOrders();
        await loadDashboardStats();
    } else {
        selectEl.value = String(previousStatus);
        selectEl.disabled = false;
    }
}

async function deleteOrder(orderSn) {
    if (!confirm('确定要删除这笔已取消且未付款的订单吗？删除后会同步移除关联的供应商备货记录。')) {
        return;
    }

    const result = await fetchData(`/admin/orders/${orderSn}`, 'DELETE', null, true);
    if (result) {
        alert([result.message, result.inventory_note].filter(Boolean).join('\n'));
        await loadOrders();
        await loadDashboardStats();
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
                    <p>服务区域: ${formatSupplierServiceZones(supplier.service_zone_names)}</p>
                    <p>供货品类: ${(supplier.supply_category_names && supplier.supply_category_names.length > 0) ? supplier.supply_category_names.join('、') : '全部品类（未限制）'}</p>
                    <p>供应商后台: <a href="/admin-panel/supplier_login.html" target="_blank">打开登录入口</a></p>
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

async function loadSupplierServiceZoneOptions(selectedIds = []) {
    const zonesData = await fetchData('/admin/delivery-zones', 'GET', null, true);
    const container = document.getElementById('supplier-service-zone-ids');
    if (!container) return;
    const options = (zonesData?.zones || []).map(zone => ({ id: zone.id, label: zone.zone_name }));
    renderSupplierCheckboxOptions(container, options, selectedIds, '请先到配送区域添加区域');
}

async function showSupplierModal(supplierId = null) {
    const modal = document.getElementById('supplier-modal');
    const title = document.getElementById('supplier-modal-title');
    const form = document.getElementById('supplier-form');
    form.reset();
    document.getElementById('supplier-id').value = '';
    document.getElementById('supplier-active').checked = true;
    document.getElementById('supplier-password').required = !supplierId;

    let selectedServiceZoneIds = [];
    let selectedSupplyCategoryIds = [];
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
            selectedServiceZoneIds = supplier.service_zone_ids || [];
            selectedSupplyCategoryIds = supplier.supply_category_ids || [];
        }
    } else {
        title.textContent = '添加供应商';
    }
    await loadSupplierServiceZoneOptions(selectedServiceZoneIds);
    await loadSupplierCategoryOptions(selectedSupplyCategoryIds);
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
        service_zone_ids: getSelectedNumberValues('supplier-service-zone-ids'),
        supply_category_ids: getSelectedNumberValues('supplier-supply-category-ids'),
    };
    const password = document.getElementById('supplier-password').value;
    if (password) {
        data.password = password;
    }
    if (!data.supply_category_ids.length && !confirm('未勾选供货品类，该供应商将可承接所有原料品类。确定继续保存吗？')) {
        return;
    }

    const result = await fetchData(url, method, data, true);
    if (result) {
        alert('供应商保存成功！');
        closeModal('supplier-modal');
        await loadSuppliers();
    }
});

async function deleteSupplier(supplierId) {
    if (confirm('确定要删除此供应商吗？没有待备货/备货中的备货单才允许删除；历史订单会保留供应商名称。')) {
        const result = await fetchData(`/admin/suppliers/${supplierId}`, 'DELETE', null, true);
        if (result) {
            alert(result.message || '供应商处理成功');
            await loadSuppliers();
        }
    }
}

// ==================== 原料管理 (Ingredients) ====================

let currentIngredients = [];
let currentSupplierOptions = [];

function getIngredientsListUrl() {
    const params = new URLSearchParams();
    const search = document.getElementById('ingredient-search')?.value.trim();
    const status = document.getElementById('ingredient-status-filter')?.value || 'active';
    const zoneId = document.getElementById('ingredient-zone-filter')?.value || 'all';

    if (search) {
        params.set('q', search);
    }
    if (zoneId && zoneId !== 'all') {
        params.set('zone_id', zoneId);
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
                    <p>供应商: ${ingredient.supplier_name || '未知'} | 区域: ${formatZoneName(ingredient.zone_name)}</p>
                    <p>价格: ${ingredient.price ? '¥' + ingredient.price : '未设置'} | 库存: ${ingredient.stock}</p>
                    ${ingredient.pending_price_request ? `<p style="color:#b26a00;">待审核新价: ${formatCurrency(ingredient.pending_price_request.requested_price)}（供应商申请）</p>` : ''}
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

    await loadCategoriesForSelect();
    await loadDeliveryZonesForIngredientSelect('ingredient-zone-id');
    const zoneSelect = document.getElementById('ingredient-zone-id');
    if (zoneSelect) {
        zoneSelect.onchange = () => renderSuppliersForIngredientSelect();
    }
    const categorySelect = document.getElementById('ingredient-category-id');
    if (categorySelect) {
        categorySelect.onchange = () => renderSuppliersForIngredientSelect();
    }

    if (ingredientId) {
        title.textContent = '编辑原料';
        const ingredient = await fetchData(`/admin/ingredients/${ingredientId}`);
        if (ingredient) {
            document.getElementById('ingredient-id').value = ingredient.id;
            document.getElementById('ingredient-name').value = ingredient.name;
            document.getElementById('ingredient-unit').value = ingredient.unit;
            document.getElementById('ingredient-category-id').value = ingredient.category_id || '';
            document.getElementById('ingredient-zone-id').value = ingredient.zone_id || '';
            document.getElementById('ingredient-price').value = ingredient.price || '';
            document.getElementById('ingredient-stock').value = ingredient.stock;
            document.getElementById('ingredient-active').checked = ingredient.is_active;
            await loadSuppliersForSelect(ingredient.supplier_id);
        }
    } else {
        title.textContent = '添加原料';
        await loadSuppliersForSelect();
    }
    showModal('ingredient-modal');
}

function renderSuppliersForIngredientSelect(selectedSupplierId = null) {
    const select = document.getElementById('ingredient-supplier-id');
    if (!select) return;

    const currentValue = selectedSupplierId || select.value;
    const zoneValue = document.getElementById('ingredient-zone-id')?.value || '';
    const categoryValue = document.getElementById('ingredient-category-id')?.value || '';
    const availableSuppliers = currentSupplierOptions.filter(supplier => (
        supplier.is_active && supplierServesZone(supplier, zoneValue) && supplierSupportsCategory(supplier, categoryValue)
    ));

    select.innerHTML = '<option value="">请选择供应商</option>';
    availableSuppliers.forEach(supplier => {
        const option = document.createElement('option');
        option.value = supplier.id;
        const categoryNames = (supplier.supply_category_names || []).join('、') || '全部品类';
        option.textContent = `${supplier.name} / 服务区域: ${formatSupplierServiceZones(supplier.service_zone_names)} / 供货品类: ${categoryNames}`;
        select.appendChild(option);
    });

    if (currentValue && availableSuppliers.some(supplier => Number(supplier.id) === Number(currentValue))) {
        select.value = String(currentValue);
    }
}

async function loadSuppliersForSelect(selectedSupplierId = null) {
    const suppliersData = await fetchData('/admin/suppliers');
    currentSupplierOptions = suppliersData && suppliersData.suppliers ? suppliersData.suppliers : [];
    renderSuppliersForIngredientSelect(selectedSupplierId);
}
async function loadDeliveryZonesForIngredientSelect(selectId, includeAll = false) {
    const zonesData = await fetchData('/admin/delivery-zones');
    const select = document.getElementById(selectId);
    if (!select) return;

    select.innerHTML = includeAll
        ? '<option value="all">全部区域</option><option value="global">通用区域</option>'
        : '<option value="">通用区域</option>';

    if (zonesData && zonesData.zones) {
        zonesData.zones.forEach(zone => {
            const option = document.createElement('option');
            option.value = zone.id;
            option.textContent = zone.zone_name;
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
        zone_id: document.getElementById('ingredient-zone-id').value ? parseInt(document.getElementById('ingredient-zone-id').value) : null,
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

// ==================== 原料价格审核 (Price Reviews) ====================

function getPriceReviewsUrl() {
    const params = new URLSearchParams();
    const status = document.getElementById('price-review-status-filter')?.value || 'pending';
    const keyword = document.getElementById('price-review-search')?.value.trim();
    params.set('status', status);
    if (keyword) {
        params.set('q', keyword);
    }
    return `/admin/ingredient-price-requests?${params.toString()}`;
}

function renderPriceReviewSummary(summary) {
    const summaryEl = document.getElementById('price-review-summary');
    if (!summaryEl || !summary) return;
    summaryEl.innerHTML = `
        <div class="stat-card"><h3>待审核</h3><p class="number">${summary.pending_count || 0}</p></div>
        <div class="stat-card"><h3>已通过</h3><p class="number">${summary.approved_count || 0}</p></div>
        <div class="stat-card"><h3>已驳回</h3><p class="number">${summary.rejected_count || 0}</p></div>
    `;
}

async function loadPriceReviews() {
    const data = await fetchData(getPriceReviewsUrl());
    const list = document.getElementById('price-reviews-list');
    list.innerHTML = '';
    renderPriceReviewSummary(data ? data.summary : null);

    if (!data || !data.requests || data.requests.length === 0) {
        list.innerHTML = '<div class="empty-state">暂无价格审核记录</div>';
        return;
    }

    data.requests.forEach(item => {
        const card = document.createElement('div');
        card.classList.add('data-card', `status-${item.status}`);
        const actionHtml = item.status === 10
            ? `<button class="btn btn-sm btn-primary" onclick="reviewIngredientPriceRequest(${item.id}, 'approve')">通过</button>
               <button class="btn btn-sm btn-danger" onclick="reviewIngredientPriceRequest(${item.id}, 'reject')">驳回</button>`
            : '';
        card.innerHTML = `
            <div class="data-card-content">
                <h4>${escapeHtml(item.ingredient_name || '未知原料')} <span style="float:right;color:#666;">${escapeHtml(item.status_text)}</span></h4>
                <p>供应商: ${escapeHtml(item.supplier_name || '未知供应商')}</p>
                <p>当前价格: ${item.old_price ? formatCurrency(item.old_price) : '未设置'} | 申请价格: ${item.requested_price ? formatCurrency(item.requested_price) : '未设置'}</p>
                <p>申请时间: ${escapeHtml(formatDate(item.created_at))}${item.reviewed_at ? ` | 审核时间: ${escapeHtml(formatDate(item.reviewed_at))}` : ''}</p>
                ${item.remark ? `<p>备注: ${escapeHtml(item.remark)}</p>` : ''}
            </div>
            <div class="data-card-actions">${actionHtml}</div>
        `;
        list.appendChild(card);
    });
}

async function reviewIngredientPriceRequest(requestId, action) {
    const actionText = action === 'approve' ? '通过' : '驳回';
    const remark = action === 'reject' ? prompt('请输入驳回原因（可留空）:') : '';
    if (!confirm(`确认${actionText}这条价格申请吗？`)) return;

    const result = await fetchData(`/admin/ingredient-price-requests/${requestId}/review`, 'PUT', {
        action,
        remark: remark || null
    }, true);
    if (result) {
        alert(result.message || '审核完成');
        await loadPriceReviews();
        if (currentPage === 'ingredients') {
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
    await loadDeliveryZonesForIngredientSelect('pi-zone-filter', true);
    document.getElementById('pi-quantity').value = '';
    
    // 加载原料选项
    await loadIngredientsForPiSelect();

    // 加载已配置的原料
    await loadProductIngredients();
    
    showModal('product-ingredients-modal');
}

async function loadIngredientsForPiSelect() {
    const zoneFilter = document.getElementById('pi-zone-filter')?.value || 'all';
    const zoneQuery = zoneFilter && zoneFilter !== 'all' ? `&zone_id=${encodeURIComponent(zoneFilter)}` : '';
    const ingredientsData = await fetchData(`/admin/ingredients?is_active=true${zoneQuery}`);
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
        option.textContent = `${ingredient.name} / ${formatZoneName(ingredient.zone_name)} / ${ingredient.supplier_name || '未知供应商'} / ${ingredient.unit} / ${priceText}`;
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
        ? `区域: ${formatZoneName(ingredient.zone_name)} | 供应商: ${ingredient.supplier_name || '未知'} | 单位: ${ingredient.unit} | 单价: ${ingredient.price ? formatCurrency(ingredient.price) : '未设置'}`
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
                    <span style="color:#999;margin-left:10px;">区域: ${formatZoneName(pi.ingredient_zone_name)}</span>
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
    
    const zoneFilter = document.getElementById('pi-zone-filter')?.value || 'all';
    const payload = {
        ingredient_id: parseInt(ingredientId),
        quantity_needed: parseFloat(quantity)
    };
    if (zoneFilter !== 'all') {
        payload.zone_id = zoneFilter;
    }

    const result = await fetchData(`/admin/products/${currentProductIdForIngredients}/ingredients`, 'POST', payload, true);
    
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

// ==================== 区域统计 (Zone Statistics) ====================

function renderZoneStatisticsSummary(summary) {
    const summaryEl = document.getElementById('zone-statistics-summary');
    if (!summaryEl || !summary) return;

    summaryEl.innerHTML = `
        <div class="stat-card"><h3>${summary.month} 已送达金额</h3><p class="number">${formatCurrency(summary.settled_sales)}</p></div>
        <div class="stat-card"><h3>配送费合计</h3><p class="number">${formatCurrency(summary.delivery_fee_total)}</p></div>
        <div class="stat-card"><h3>已送达材料成本</h3><p class="number">${formatCurrency(summary.settled_supplier_cost)}</p></div>
        <div class="stat-card"><h3>预估毛利</h3><p class="number">${formatCurrency(summary.estimated_gross_profit)}</p></div>
    `;
}

function renderZoneStatisticsList(zones) {
    const list = document.getElementById('zone-statistics-list');
    list.innerHTML = '';
    if (!zones || zones.length === 0) {
        list.innerHTML = '<div class="empty-state">暂无区域统计</div>';
        return;
    }

    zones.forEach(zone => {
        const card = document.createElement('div');
        const zoneFilterValue = zone.zone_id ? zone.zone_id : 'unassigned';
        card.className = 'data-card';
        card.innerHTML = `
            <div class="data-card-content">
                <h4>${zone.zone_name || '未分配区域'}</h4>
                <p>订单: ${zone.order_count || 0} | 有效订单: ${zone.active_order_count || 0} | 已送达: ${zone.completed_count || 0} | 待处理: ${zone.pending_count || 0}</p>
                <p>有效销售额: ${formatCurrency(zone.total_sales)} | 已送达金额: ${formatCurrency(zone.settled_sales)} | 配送费: ${formatCurrency(zone.delivery_fee_total)}</p>
                <p>材料成本: ${formatCurrency(zone.supplier_cost_total)} | 已送达材料成本: ${formatCurrency(zone.settled_supplier_cost)} | 预估毛利: ${formatCurrency(zone.estimated_gross_profit)}</p>
                <p>区域账号: ${zone.merchant_username || '未设置'}</p>
            </div>
            <div class="data-card-actions">
                <button class="btn btn-sm btn-primary" onclick="openSupplierOrdersForZone('${zoneFilterValue}')">查看备货单</button>
            </div>
        `;
        list.appendChild(card);
    });
}

async function loadZoneStatistics() {
    const month = getMonthInputValue('zone-statistics-month');
    const zoneFilter = document.getElementById('zone-statistics-zone-filter')?.value || 'all';
    const params = new URLSearchParams({ month });
    if (zoneFilter !== 'all') {
        params.set('zone_id', zoneFilter);
    }
    const data = await fetchData(`/admin/zone-statistics?${params.toString()}`);
    renderZoneStatisticsSummary(data ? data.summary : null);
    renderZoneStatisticsList(data ? data.zones : []);
}

function showZoneSupplyRuleFromCurrentZone() {
    const zoneValue = document.getElementById('zone-supply-rule-zone-filter')?.value || '';
    showZoneSupplyRuleModal(null, zoneValue && zoneValue !== 'all' ? zoneValue : null);
}

function openZoneSupplyRulesForZone(zoneId) {
    const filter = document.getElementById('zone-supply-rule-zone-filter');
    if (filter) {
        filter.value = String(zoneId || 'all');
    }

    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    const menuItem = document.querySelector('.menu-item[data-page="zone-supply-rules"]');
    if (menuItem) {
        menuItem.classList.add('active');
    }
    currentPage = 'zone-supply-rules';
    renderPage();
}

function openSupplierOrdersForZone(zoneFilterValue) {
    currentSupplierOrderZoneFilter = String(zoneFilterValue || 'all');
    const filter = document.getElementById('supplier-order-zone-filter');
    if (filter) {
        filter.value = currentSupplierOrderZoneFilter;
    }

    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    const menuItem = document.querySelector('.menu-item[data-page="supplier-orders"]');
    if (menuItem) {
        menuItem.classList.add('active');
    }
    currentPage = 'supplier-orders';
    renderPage();
}
// ==================== 供应商备货单管理 (Supplier Orders) ====================

let currentSupplierOrderStatusFilter = 'all';
let currentSupplierOrderZoneFilter = 'all';

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
            <h3>${escapeHtml(item.supplier_name)}</h3>
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
    const zoneFilter = document.getElementById('supplier-order-zone-filter')?.value || currentSupplierOrderZoneFilter || 'all';
    currentSupplierOrderZoneFilter = zoneFilter;
    const params = new URLSearchParams();
    if (currentSupplierOrderStatusFilter !== 'all') {
        params.set('status', currentSupplierOrderStatusFilter);
    }
    if (zoneFilter !== 'all') {
        params.set('zone_id', zoneFilter);
    }
    const query = params.toString();
    const ordersData = await fetchData(`/admin/supplier-orders${query ? '?' + query : ''}`);
    const ordersList = document.getElementById('supplier-orders-list');
    ordersList.innerHTML = '';
    renderAdminSupplierOrdersSummary(ordersData ? ordersData.summary : null);

    if (ordersData && ordersData.supplier_orders) {
        ordersData.supplier_orders.forEach(order => {
            const card = document.createElement('div');
            card.classList.add('data-card', `status-${order.status}`);
            const itemsHtml = order.items ? order.items.map(item => `
                <p>${escapeHtml(item.ingredient_name)} x ${escapeHtml(item.quantity)} ${escapeHtml(item.unit)} | 单价 ${formatCurrency(item.unit_price)} | 小计 ${formatCurrency(item.total_price)}</p>
            `).join('') : '';
            card.innerHTML = `
                <div class="data-card-content">
                    <h4>备货单 #${order.id} <span style="float:right;color:#666;">${getSupplierOrderStatusText(order.status)}</span></h4>
                    <p>关联订单号: ${escapeHtml(order.order_sn)}</p>
                    <p>供应商: ${escapeHtml(order.supplier_name || '未知')} | 备货区域: ${escapeHtml(formatZoneName(order.zone_name))}</p>
                    <p>材料费用: ${formatCurrency(order.total_cost)}</p>
                    <p>备注: ${escapeHtml(order.notes || '无')}</p>
                    <div style="margin-top:10px;padding-top:10px;border-top:1px solid #eee;">
                        ${itemsHtml}
                    </div>
                    <p style="font-size:12px;color:#999;margin-top:10px;">创建时间: ${escapeHtml(formatDate(order.created_at))}</p>
                </div>
                <div class="data-card-actions">
                    ${renderSupplierOrderStatusSelect(order)}
                </div>
            `;
            ordersList.appendChild(card);
        });
    }
}

async function updateSupplierOrderStatusFromSelect(orderId, selectEl) {
    const previousStatus = parseInt(selectEl.dataset.current, 10);
    const nextStatus = parseInt(selectEl.value, 10);
    if (nextStatus === previousStatus) return;

    selectEl.disabled = true;
    const result = await fetchData(`/admin/supplier-orders/${orderId}/status`, 'PUT', { status: nextStatus }, true);
    if (result) {
        alert(result.message || '备货单状态更新成功');
        await loadSupplierOrders();
        await loadOrders();
        await loadDashboardStats();
    } else {
        selectEl.value = String(previousStatus);
        selectEl.disabled = false;
    }
}


function supplierSupportsCategory(supplier, categoryValue) {
    if (!categoryValue) return true;
    const categoryId = Number(categoryValue);
    const categoryIds = (supplier.supply_category_ids || []).map(Number);
    return categoryIds.length === 0 || categoryIds.includes(categoryId);
}

function supplierServesZone(supplier, zoneValue) {
    if (!zoneValue) return true;
    const zoneId = Number(zoneValue);
    return (supplier.service_zone_ids || []).map(Number).includes(zoneId);
}

async function loadSupplierCategoryOptions(selectedIds = []) {
    const container = document.getElementById('supplier-supply-category-ids');
    if (!container) return;
    const categoriesData = await fetchData('/admin/categories', 'GET', null, true);
    const options = (categoriesData?.categories || []).map(category => ({
        id: category.id,
        label: `${category.icon || ''} ${category.name}`.trim(),
    }));
    renderSupplierCheckboxOptions(container, options, selectedIds, '请先到分类管理添加原料品类');
}

async function loadZoneOptionsForStationModal(selectId, selectedZoneId = null) {
    const select = document.getElementById(selectId);
    if (!select) return;

    const zonesData = await fetchData('/admin/delivery-zones');
    const zones = zonesData && zonesData.zones ? zonesData.zones : [];
    const currentValue = selectedZoneId ? String(selectedZoneId) : select.value;
    select.innerHTML = '<option value="">请选择配送区域</option>';

    zones.forEach(zone => {
        const zoneId = String(zone.id);
        if (zone.station_id && zoneId !== String(currentValue)) {
            return;
        }
        const option = document.createElement('option');
        option.value = zone.id;
        option.textContent = zone.station_name ? `${zone.zone_name}（已配置配送站：${zone.station_name}）` : zone.zone_name;
        select.appendChild(option);
    });

    if (currentValue) {
        select.value = String(currentValue);
    }
}

async function loadZoneOptionsForRuleModal(selectId, selectedZoneId = null) {
    const select = document.getElementById(selectId);
    if (!select) return;

    const zonesData = await fetchData('/admin/delivery-zones');
    const zones = zonesData && zonesData.zones ? zonesData.zones : [];
    const currentValue = selectedZoneId ? String(selectedZoneId) : select.value;
    select.innerHTML = '<option value="">请选择配送区域</option>';

    zones.forEach(zone => {
        const option = document.createElement('option');
        option.value = zone.id;
        option.textContent = zone.station_name
            ? `${zone.zone_name}（${zone.station_name}）`
            : `${zone.zone_name}（未配置配送站）`;
        select.appendChild(option);
    });

    if (currentValue) {
        select.value = String(currentValue);
    }
}

async function loadRuleCategoryOptions(selectId, selectedCategoryId = null) {
    const select = document.getElementById(selectId);
    if (!select) return;

    const categoriesData = await fetchData('/admin/categories');
    const currentValue = selectedCategoryId ? String(selectedCategoryId) : select.value;
    select.innerHTML = '<option value="">请选择品类</option>';

    if (categoriesData && categoriesData.categories) {
        categoriesData.categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category.id;
            option.textContent = `${category.icon || ''} ${category.name}`.trim();
            select.appendChild(option);
        });
    }

    if (currentValue) {
        select.value = String(currentValue);
    }
}

async function loadRuleSupplierOptions(selectId, selectedSupplierId = null, zoneId = null, categoryId = null) {
    const select = document.getElementById(selectId);
    if (!select) return;

    const suppliersData = await fetchData('/admin/suppliers');
    const suppliers = suppliersData && suppliersData.suppliers ? suppliersData.suppliers : [];
    const currentValue = selectedSupplierId ? String(selectedSupplierId) : select.value;
    const zoneValue = zoneId || document.getElementById('zone-supply-rule-zone-id')?.value || '';
    const categoryValue = categoryId || document.getElementById('zone-supply-rule-category-id')?.value || '';

    select.innerHTML = '<option value="">请选择供应商</option>';
    suppliers
        .filter(supplier => supplier.is_active)
        .filter(supplier => supplierServesZone(supplier, zoneValue))
        .filter(supplier => supplierSupportsCategory(supplier, categoryValue))
        .forEach(supplier => {
            const option = document.createElement('option');
            option.value = supplier.id;
            const zoneNames = (supplier.service_zone_names || []).join('、') || '通用';
            const categoryNames = (supplier.supply_category_names || []).join('、') || '全部品类';
            option.textContent = `${supplier.name} / 区域: ${zoneNames} / 品类: ${categoryNames}`;
            select.appendChild(option);
        });

    if (currentValue) {
        select.value = String(currentValue);
    }
}

async function loadRuleStationOptions(selectId, zoneId = null, selectedStationId = null) {
    const select = document.getElementById(selectId);
    if (!select) return;

    const stationsData = await fetchData('/admin/stations');
    const stations = stationsData && stationsData.stations ? stationsData.stations : [];
    const currentValue = selectedStationId ? String(selectedStationId) : select.value;
    const zoneValue = zoneId || document.getElementById('zone-supply-rule-zone-id')?.value || '';

    select.innerHTML = '<option value="">请选择配送站</option>';
    const matchedStations = stations.filter(station => !zoneValue || String(station.zone_id) === String(zoneValue));
    if (zoneValue && matchedStations.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = '该区域暂无配送站，请先去配送站管理配置';
        option.disabled = true;
        option.selected = true;
        select.appendChild(option);
        return;
    }

    matchedStations.forEach(station => {
        const option = document.createElement('option');
        option.value = station.id;
        option.textContent = `${station.station_name}${station.zone_name ? ` / ${station.zone_name}` : ''}`;
        select.appendChild(option);
    });

    if (currentValue) {
        select.value = String(currentValue);
    }
}

function getFulfillmentIssueStatusText(status) {
    return ({
        10: '待处理',
        20: '已处理',
        30: '已忽略'
    })[status] || '未知';
}

async function loadStations() {
    const data = await fetchData('/admin/stations');
    const list = document.getElementById('stations-list');
    if (!list) return;
    list.innerHTML = '';

    const stations = data && data.stations ? data.stations : [];
    if (stations.length === 0) {
        list.innerHTML = '<div class="empty-state">暂无配送站配置</div>';
        return;
    }

    stations.forEach(station => {
        const card = document.createElement('div');
        card.classList.add('data-card');
        card.innerHTML = `
            <div class="data-card-content">
                <h4>${station.station_name}</h4>
                <p>区域: ${station.zone_name || '未绑定区域'}</p>
                <p>地址: ${station.address || '未填写'}</p>
                <p>联系人: ${station.contact_person || '无'} | 电话: ${station.phone || '无'}</p>
                <p>备注: ${station.notes || '无'}</p>
                <p>状态: ${station.is_active ? '启用' : '禁用'}</p>
                <p>登录账号: ${station.has_login ? escapeHtml(station.username) : '未配置'}</p>
                <p style="font-size:12px;color:#999;">创建时间: ${formatDate(station.created_at)}</p>
            </div>
            <div class="data-card-actions">
                <button class="btn btn-sm btn-success" onclick="showStationModal(${station.id})">编辑配送站</button>
                <a class="btn btn-sm btn-primary" href="/admin-panel/station_login.html" target="_blank" rel="noopener">配送站登录页</a>
                ${station.has_login ? `<button class="btn btn-sm btn-danger" onclick="deleteStationAccount(${station.id})">删除登录账号</button>` : ''}
                <button class="btn btn-sm btn-primary" onclick="openZoneSupplyRulesForZone(${station.zone_id})">查看配送站规则</button>
                <button class="btn btn-sm btn-danger" onclick="deleteStation(${station.id})">删除配送站</button>
            </div>
        `;
        list.appendChild(card);
    });
}

async function showStationModal(stationId = null, zoneIdHint = null) {
    const modal = document.getElementById('station-modal');
    const title = document.getElementById('station-modal-title');
    const form = document.getElementById('station-form');
    if (!modal || !title || !form) return;

    form.reset();
    document.getElementById('station-id').value = '';
    document.getElementById('station-active').checked = true;

    let selectedZoneId = zoneIdHint || '';
    if (stationId) {
        title.textContent = '编辑配送站';
        const station = await fetchData(`/admin/stations/${stationId}`);
        if (station) {
            document.getElementById('station-id').value = station.id;
            document.getElementById('station-name').value = station.station_name || '';
            document.getElementById('station-address').value = station.address || '';
            document.getElementById('station-contact-person').value = station.contact_person || '';
            document.getElementById('station-phone').value = station.phone || '';
            document.getElementById('station-username').value = station.username || '';
            document.getElementById('station-notes').value = station.notes || '';
            document.getElementById('station-active').checked = station.is_active;
            selectedZoneId = station.zone_id;
        }
    } else {
        title.textContent = '新建配送站';
    }

    await loadZoneOptionsForStationModal('station-zone-id', selectedZoneId);
    showModal('station-modal');
}

const stationForm = document.getElementById('station-form');
if (stationForm) {
    stationForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        const stationId = document.getElementById('station-id').value;
        const method = stationId ? 'PUT' : 'POST';
        const url = stationId ? `/admin/stations/${stationId}` : '/admin/stations';
        const data = {
            zone_id: parseInt(document.getElementById('station-zone-id').value, 10),
            station_name: document.getElementById('station-name').value,
            address: document.getElementById('station-address').value || null,
            contact_person: document.getElementById('station-contact-person').value || null,
            phone: document.getElementById('station-phone').value || null,
            username: document.getElementById('station-username').value.trim(),
            notes: document.getElementById('station-notes').value || null,
            is_active: document.getElementById('station-active').checked,
        };
        const password = document.getElementById('station-password').value;
        if (password) data.password = password;

        const result = await fetchData(url, method, data);
        if (result) {
            alert(result.message || '配送站保存成功！');
            closeModal('station-modal');
            await loadStations();
            await loadDeliveryZones();
            await loadDashboardStats();
        }
    });
}

async function deleteStation(stationId) {
    if (!confirm('确定要删除此配送站吗？已有配送站供货规则关联时将无法删除。')) {
        return;
    }
    const result = await fetchData(`/admin/stations/${stationId}`, 'DELETE', null, true);
    if (result) {
        alert(result.message || '配送站删除成功！');
        await loadStations();
        await loadDeliveryZones();
        await loadDashboardStats();
    }
}

async function deleteStationAccount(stationId) {
    if (!confirm('确定删除此配送站的登录账号吗？站点和订单会保留，但该账号会立即无法登录。')) {
        return;
    }
    const result = await fetchData(`/admin/stations/${stationId}/account`, 'DELETE', null, true);
    if (result) {
        await loadStations();
    }
}

async function loadZoneSupplyRules() {
    const list = document.getElementById('zone-supply-rules-list');
    if (!list) return;
    const params = new URLSearchParams();
    const zoneFilter = document.getElementById('zone-supply-rule-zone-filter')?.value || 'all';
    const statusFilter = document.getElementById('zone-supply-rule-status-filter')?.value || 'all';
    if (zoneFilter !== 'all') params.set('zone_id', zoneFilter);
    if (statusFilter !== 'all') params.set('is_active', statusFilter);

    const data = await fetchData(`/admin/zone-supply-rules${params.toString() ? `?${params.toString()}` : ''}`);
    list.innerHTML = '';

    const rules = data && data.rules ? data.rules : [];
    if (rules.length === 0) {
        list.innerHTML = '<div class="empty-state">暂无配送站供货规则，先按配送站和品类新建一条试试。</div>';
        return;
    }

    rules.forEach(rule => {
        const card = document.createElement('div');
        card.classList.add('data-card', `status-${rule.is_active ? 'active' : 'inactive'}`);
        card.innerHTML = `
            <div class="data-card-content">
                <h4>${rule.zone_name || '未知区域'} / ${rule.category_name || '未知品类'}</h4>
                <p>配送站: ${rule.station_name || '无'} | 供应商: ${rule.supplier_name || '无'}</p>
                <p>优先级: ${rule.priority} | 主供: ${rule.is_primary ? '是' : '否'} | 状态: ${rule.is_active ? '启用' : '停用'}</p>
                <p>备注: ${rule.notes || '无'}</p>
                <p style="font-size:12px;color:#999;">创建时间: ${formatDate(rule.created_at)}</p>
            </div>
            <div class="data-card-actions">
                <button class="btn btn-sm btn-success" onclick="showZoneSupplyRuleModal(${rule.id})">编辑</button>
                <button class="btn btn-sm btn-danger" onclick="deleteZoneSupplyRule(${rule.id})">删除</button>
            </div>
        `;
        list.appendChild(card);
    });
}

async function showZoneSupplyRuleModal(ruleId = null, zoneIdHint = null) {
    const modal = document.getElementById('zone-supply-rule-modal');
    const title = document.getElementById('zone-supply-rule-modal-title');
    const form = document.getElementById('zone-supply-rule-form');
    if (!modal || !title || !form) return;

    form.reset();
    document.getElementById('zone-supply-rule-id').value = '';
    document.getElementById('zone-supply-rule-primary').checked = false;
    document.getElementById('zone-supply-rule-active').checked = true;

    let ruleData = null;
    if (ruleId) {
        title.textContent = '编辑配送站供货规则';
        ruleData = await fetchData(`/admin/zone-supply-rules/${ruleId}`);
        if (ruleData) {
            document.getElementById('zone-supply-rule-id').value = ruleData.id;
            document.getElementById('zone-supply-rule-priority').value = ruleData.priority ?? 0;
            document.getElementById('zone-supply-rule-primary').checked = !!ruleData.is_primary;
            document.getElementById('zone-supply-rule-active').checked = !!ruleData.is_active;
            document.getElementById('zone-supply-rule-notes').value = ruleData.notes || '';
            zoneIdHint = ruleData.zone_id;
        }
    } else {
        title.textContent = '新建配送站供货规则';
    }

    await loadZoneOptionsForRuleModal('zone-supply-rule-zone-id', zoneIdHint || (ruleData ? ruleData.zone_id : null));
    await loadRuleCategoryOptions('zone-supply-rule-category-id', ruleData ? ruleData.category_id : null);
    const zoneValue = document.getElementById('zone-supply-rule-zone-id')?.value || zoneIdHint || '';
    const categoryValue = document.getElementById('zone-supply-rule-category-id')?.value || (ruleData ? ruleData.category_id : null);
    await loadRuleStationOptions('zone-supply-rule-station-id', zoneValue, ruleData ? ruleData.station_id : null);
    await loadRuleSupplierOptions('zone-supply-rule-supplier-id', ruleData ? ruleData.supplier_id : null, zoneValue, categoryValue);

    const zoneSelect = document.getElementById('zone-supply-rule-zone-id');
    if (zoneSelect) {
        zoneSelect.onchange = async () => {
            const nextZoneId = zoneSelect.value;
            await loadRuleStationOptions('zone-supply-rule-station-id', nextZoneId, null);
            await loadRuleSupplierOptions('zone-supply-rule-supplier-id', null, nextZoneId, document.getElementById('zone-supply-rule-category-id')?.value || '');
        };
    }
    const categorySelect = document.getElementById('zone-supply-rule-category-id');
    if (categorySelect) {
        categorySelect.onchange = async () => {
            await loadRuleSupplierOptions('zone-supply-rule-supplier-id', null, document.getElementById('zone-supply-rule-zone-id')?.value || '', categorySelect.value);
        };
    }

    showModal('zone-supply-rule-modal');
}

const zoneSupplyRuleForm = document.getElementById('zone-supply-rule-form');
if (zoneSupplyRuleForm) {
    zoneSupplyRuleForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        const ruleId = document.getElementById('zone-supply-rule-id').value;
        const method = ruleId ? 'PUT' : 'POST';
        const url = ruleId ? `/admin/zone-supply-rules/${ruleId}` : '/admin/zone-supply-rules';
        const data = {
            zone_id: parseInt(document.getElementById('zone-supply-rule-zone-id').value, 10),
            station_id: parseInt(document.getElementById('zone-supply-rule-station-id').value, 10),
            category_id: parseInt(document.getElementById('zone-supply-rule-category-id').value, 10),
            supplier_id: parseInt(document.getElementById('zone-supply-rule-supplier-id').value, 10),
            priority: parseInt(document.getElementById('zone-supply-rule-priority').value, 10) || 0,
            is_primary: document.getElementById('zone-supply-rule-primary').checked,
            is_active: document.getElementById('zone-supply-rule-active').checked,
            notes: document.getElementById('zone-supply-rule-notes').value || null,
        };

        const result = await fetchData(url, method, data);
        if (result) {
            alert(result.message || '配送站供货规则保存成功！');
            closeModal('zone-supply-rule-modal');
            await loadZoneSupplyRules();
        }
    });
}

async function deleteZoneSupplyRule(ruleId) {
    if (!confirm('确定要删除此配送站供货规则吗？')) {
        return;
    }
    const result = await fetchData(`/admin/zone-supply-rules/${ruleId}`, 'DELETE', null, true);
    if (result) {
        alert(result.message || '配送站供货规则删除成功！');
        await loadZoneSupplyRules();
    }
}

async function loadFulfillmentIssues() {
    const list = document.getElementById('fulfillment-issues-list');
    if (!list) return;

    const params = new URLSearchParams();
    const statusFilter = document.getElementById('fulfillment-issue-status-filter')?.value || 'all';
    const zoneFilter = document.getElementById('fulfillment-issue-zone-filter')?.value || 'all';
    const orderSn = document.getElementById('fulfillment-issue-order-sn')?.value.trim() || '';
    const issueType = document.getElementById('fulfillment-issue-type')?.value.trim() || '';
    if (statusFilter !== 'all') params.set('status', statusFilter);
    if (zoneFilter !== 'all') params.set('zone_id', zoneFilter);
    if (orderSn) params.set('order_sn', orderSn);
    if (issueType) params.set('issue_type', issueType);

    const data = await fetchData(`/admin/fulfillment-issues${params.toString() ? `?${params.toString()}` : ''}`);
    list.innerHTML = '';

    const issues = data && data.issues ? data.issues : [];
    if (issues.length === 0) {
        list.innerHTML = '<div class="empty-state">暂无履约异常，系统正常时这里会保持空。<\/div>';
        return;
    }

    issues.forEach(issue => {
        const card = document.createElement('div');
        card.classList.add('data-card', `status-${issue.status}`);
        card.innerHTML = `
            <div class="data-card-content">
                <h4>#${escapeHtml(issue.id)} ${escapeHtml(issue.issue_type)} <span style="float:right;color:#666;">${getFulfillmentIssueStatusText(issue.status)}</span></h4>
                <p>订单号: ${escapeHtml(issue.order_sn)}</p>
                <p>区域: ${escapeHtml(issue.zone_name || '无')} | 配送站: ${escapeHtml(issue.station_name || '无')}</p>
                <p>描述: ${escapeHtml(issue.message)}</p>
                <p style="font-size:12px;color:#999;">创建时间: ${escapeHtml(formatDate(issue.created_at))}${issue.resolved_at ? ` | 处理时间: ${escapeHtml(formatDate(issue.resolved_at))}` : ''}</p>
            </div>
            <div class="data-card-actions">
                <button class="btn btn-sm btn-success" onclick="updateFulfillmentIssueStatus(${issue.id}, 20)">设为已处理</button>
                <button class="btn btn-sm btn-primary" onclick="updateFulfillmentIssueStatus(${issue.id}, 10)">恢复待处理</button>
                <button class="btn btn-sm btn-danger" onclick="updateFulfillmentIssueStatus(${issue.id}, 30)">设为忽略</button>
            </div>
        `;
        list.appendChild(card);
    });
}

async function updateFulfillmentIssueStatus(issueId, status) {
    const result = await fetchData(`/admin/fulfillment-issues/${issueId}`, 'PUT', { status }, true);
    if (result) {
        alert(result.message || '履约异常已更新');
        await loadFulfillmentIssues();
    }
}

function setupFulfillmentControls() {
    const zoneRuleZoneFilter = document.getElementById('zone-supply-rule-zone-filter');
    const zoneRuleStatusFilter = document.getElementById('zone-supply-rule-status-filter');
    const issueStatusFilter = document.getElementById('fulfillment-issue-status-filter');
    const issueZoneFilter = document.getElementById('fulfillment-issue-zone-filter');
    const issueOrderSn = document.getElementById('fulfillment-issue-order-sn');
    const issueType = document.getElementById('fulfillment-issue-type');

    if (zoneRuleZoneFilter) {
        loadDeliveryZonesForFilter('zone-supply-rule-zone-filter', { includeUnassigned: false });
        zoneRuleZoneFilter.addEventListener('change', loadZoneSupplyRules);
    }
    if (zoneRuleStatusFilter) {
        zoneRuleStatusFilter.addEventListener('change', loadZoneSupplyRules);
    }
    if (issueStatusFilter) {
        issueStatusFilter.addEventListener('change', loadFulfillmentIssues);
    }
    if (issueZoneFilter) {
        loadDeliveryZonesForFilter('fulfillment-issue-zone-filter', { includeUnassigned: false });
        issueZoneFilter.addEventListener('change', loadFulfillmentIssues);
    }
    if (issueOrderSn) {
        issueOrderSn.addEventListener('keydown', event => {
            if (event.key === 'Enter') {
                event.preventDefault();
                loadFulfillmentIssues();
            }
        });
    }
    if (issueType) {
        issueType.addEventListener('keydown', event => {
            if (event.key === 'Enter') {
                event.preventDefault();
                loadFulfillmentIssues();
            }
        });
    }
}
// ==================== 初始化 ====================

function setupIngredientControls() {
    const search = document.getElementById('ingredient-search');
    const statusFilter = document.getElementById('ingredient-status-filter');
    const ingredientZoneFilter = document.getElementById('ingredient-zone-filter');
    const productIngredientSelect = document.getElementById('pi-ingredient-id');
    const productIngredientZoneFilter = document.getElementById('pi-zone-filter');
    const zoneStatisticsZoneFilter = document.getElementById('zone-statistics-zone-filter');
    const supplierOrderZoneFilter = document.getElementById('supplier-order-zone-filter');
    const priceReviewSearch = document.getElementById('price-review-search');
    const priceReviewStatusFilter = document.getElementById('price-review-status-filter');

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
    if (ingredientZoneFilter) {
        loadDeliveryZonesForIngredientSelect('ingredient-zone-filter', true);
        ingredientZoneFilter.addEventListener('change', loadIngredients);
    }
    if (productIngredientSelect) {
        productIngredientSelect.addEventListener('change', updateProductIngredientMeta);
    }
    if (productIngredientZoneFilter) {
        productIngredientZoneFilter.addEventListener('change', loadIngredientsForPiSelect);
    }
    if (zoneStatisticsZoneFilter) {
        loadDeliveryZonesForFilter('zone-statistics-zone-filter', { includeUnassigned: true });
        zoneStatisticsZoneFilter.addEventListener('change', loadZoneStatistics);
    }
    if (supplierOrderZoneFilter) {
        loadDeliveryZonesForFilter('supplier-order-zone-filter', { includeUnassigned: true });
        supplierOrderZoneFilter.addEventListener('change', loadSupplierOrders);
    }
    if (priceReviewSearch) {
        priceReviewSearch.addEventListener('keydown', event => {
            if (event.key === 'Enter') {
                event.preventDefault();
                loadPriceReviews();
            }
        });
    }
    if (priceReviewStatusFilter) {
        priceReviewStatusFilter.addEventListener('change', loadPriceReviews);
    }
}
document.addEventListener('DOMContentLoaded', () => {
    if (!adminToken()) {
        requireAdminLogin();
        return;
    }
    const zoneStatsMonth = document.getElementById('zone-statistics-month');
    if (zoneStatsMonth) {
        zoneStatsMonth.value = getCurrentMonthValue();
    }
    setupIngredientControls();
    setupFulfillmentControls();
    renderPage();
});
