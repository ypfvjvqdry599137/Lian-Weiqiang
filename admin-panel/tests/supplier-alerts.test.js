const test = require('node:test');
const assert = require('node:assert/strict');
const SupplierAlertTracker = require('../js/supplier-alerts');

test('first load shows pending count without replaying old orders', () => {
    const tracker = new SupplierAlertTracker();
    const result = tracker.update([{ id: 11 }, { id: 12 }]);
    assert.equal(result.pendingCount, 2);
    assert.deepEqual(result.newOrders, []);
});

test('newly payable orders alert once and refunded orders disappear', () => {
    const tracker = new SupplierAlertTracker();
    tracker.update([{ id: 11 }]);
    assert.deepEqual(tracker.update([{ id: 11 }, { id: 12 }]).newOrders.map(order => order.id), [12]);
    assert.deepEqual(tracker.update([{ id: 11 }, { id: 12 }]).newOrders, []);
    assert.equal(tracker.update([{ id: 12 }]).pendingCount, 1);
    assert.deepEqual(tracker.update([{ id: 12 }, { id: 13 }]).newOrders.map(order => order.id), [13]);
});
