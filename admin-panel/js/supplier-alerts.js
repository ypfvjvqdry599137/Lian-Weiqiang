class SupplierAlertTracker {
    constructor() {
        this.previousIds = null;
    }

    update(orders) {
        const currentIds = new Set(orders.map(order => String(order.id)));
        const newOrders = this.previousIds === null ? [] : orders.filter(order => !this.previousIds.has(String(order.id)));
        this.previousIds = currentIds;
        return { pendingCount: orders.length, newOrders };
    }
}

if (typeof module !== 'undefined' && module.exports) module.exports = SupplierAlertTracker;
