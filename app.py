from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from collections import defaultdict

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///analytics.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# Analytics Model
class ParkingEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    spot_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(20), nullable=False)  # 'occupied', 'freed'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    duration_hours = db.Column(db.Float)  # for 'freed' events


# Create tables
with app.app_context():
    db.create_all()


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "parking-analytics"})


@app.route('/api/track-parking', methods=['POST'])
def track_parking_event():
    """Track when users occupy or free parking spots"""
    data = request.get_json()

    event = ParkingEvent(
        user_id=data.get('user_id'),
        spot_id=data.get('spot_id'),
        action=data.get('action'),  # 'occupied' or 'freed'
        duration_hours=data.get('duration_hours')
    )

    db.session.add(event)
    db.session.commit()

    return jsonify({"message": "Event tracked successfully"}), 201


@app.route('/api/analytics/popular-spots', methods=['GET'])
def get_popular_spots():
    """Get most frequently used parking spots"""
    events = db.session.query(
        ParkingEvent.spot_id,
        db.func.count(ParkingEvent.id).label('usage_count')
    ).filter(ParkingEvent.action == 'occupied').group_by(ParkingEvent.spot_id).order_by(
        db.func.count(ParkingEvent.id).desc()).limit(10).all()

    result = [{"spot_id": event.spot_id, "usage_count": event.usage_count} for event in events]
    return jsonify({"popular_spots": result})


@app.route('/api/analytics/frequent-users', methods=['GET'])
def get_frequent_users():
    """Get users who park most frequently"""
    events = db.session.query(
        ParkingEvent.user_id,
        db.func.count(ParkingEvent.id).label('parking_sessions')
    ).filter(ParkingEvent.action == 'occupied').group_by(ParkingEvent.user_id).order_by(
        db.func.count(ParkingEvent.id).desc()).limit(10).all()

    result = [{"user_id": event.user_id, "parking_sessions": event.parking_sessions} for event in events]
    return jsonify({"frequent_users": result})


@app.route('/api/analytics/usage-stats', methods=['GET'])
def get_usage_stats():
    """Get overall usage statistics"""
    total_events = ParkingEvent.query.filter(ParkingEvent.action == 'occupied').count()
    unique_users = db.session.query(ParkingEvent.user_id).distinct().count()
    unique_spots = db.session.query(ParkingEvent.spot_id).distinct().count()

    return jsonify({
        "total_parking_sessions": total_events,
        "unique_users": unique_users,
        "unique_spots_used": unique_spots
    })


@app.route('/api/analytics/dashboard', methods=['GET'])
def get_dashboard_data():
    """Combined endpoint for frontend dashboard"""
    popular_spots = get_popular_spots().get_json()
    frequent_users = get_frequent_users().get_json()
    stats = get_usage_stats().get_json()

    return jsonify({
        "dashboard": {
            **popular_spots,
            **frequent_users,
            **stats,
            "last_updated": datetime.utcnow().isoformat()
        }
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)