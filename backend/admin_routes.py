from flask import Blueprint, request, jsonify
from app import db
from models import CommunityStation

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/stations', methods=['POST'])
def create_station():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request body"}), 400

    station_name = data.get('station_name')
    address = data.get('address')
    merchant_username = data.get('merchant_username')
    merchant_password = data.get('merchant_password')
    commission_rate = data.get('commission_rate', 0.00)

    if not all([station_name, address, merchant_username, merchant_password]):
        return jsonify({"message": "Missing required fields"}), 400

    if CommunityStation.query.filter_by(merchant_username=merchant_username).first():
        return jsonify({"message": "Merchant username already exists"}), 409

    new_station = CommunityStation(
        station_name=station_name,
        address=address,
        merchant_username=merchant_username,
        merchant_password=merchant_password, # In a real app, hash this password
        commission_rate=commission_rate
    )
    db.session.add(new_station)
    db.session.commit()
    return jsonify({"message": "Community station created successfully", "id": new_station.id}), 201

@admin_bp.route('/stations', methods=['GET'])
def get_stations():
    stations = CommunityStation.query.all()
    output = []
    for station in stations:
        output.append({
            'id': station.id,
            'station_name': station.station_name,
            'address': station.address,
            'merchant_username': station.merchant_username,
            'commission_rate': str(station.commission_rate)
        })
    return jsonify({"stations": output}), 200

@admin_bp.route('/stations/<int:station_id>', methods=['GET'])
def get_station(station_id):
    station = CommunityStation.query.get_or_404(station_id)
    return jsonify({
        'id': station.id,
        'station_name': station.station_name,
        'address': station.address,
        'merchant_username': station.merchant_username,
        'commission_rate': str(station.commission_rate)
    }), 200

@admin_bp.route('/stations/<int:station_id>', methods=['PUT'])
def update_station(station_id):
    station = CommunityStation.query.get_or_404(station_id)
    data = request.get_json()

    station.station_name = data.get('station_name', station.station_name)
    station.address = data.get('address', station.address)
    station.commission_rate = data.get('commission_rate', station.commission_rate)
    # Password update would typically be a separate endpoint for security
    db.session.commit()
    return jsonify({"message": "Community station updated successfully"}), 200

@admin_bp.route('/stations/<int:station_id>', methods=['DELETE'])
def delete_station(station_id):
    station = CommunityStation.query.get_or_404(station_id)
    db.session.delete(station)
    db.session.commit()
    return jsonify({"message": "Community station deleted successfully"}), 200
