from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flasgger import Swagger               # ← NEW
import os
from collections import defaultdict

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///analytics.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ───────────── Database ─────────────
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///analytics.db"
).replace("postgres://", "postgresql://")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# Analytics Model
# ─────────── Swagger config ──────────
swagger = Swagger(app, template={
    "swagger": "2.0",
    "info": {
        "title": "Parking Analytics API",
        "version": "1.0.0",
        "description": "Tracks parking-spot usage and exposes analytics"
    }
})

# ───────────── Models ────────────────
class ParkingEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    spot_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(20), nullable=False)  # 'occupied', 'freed'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    duration_hours = db.Column(db.Float)  # for 'freed' events

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.String(100), nullable=False)
    spot_id        = db.Column(db.Integer,       nullable=False)
    action         = db.Column(db.String(20),    nullable=False)  # occupied / freed
    timestamp      = db.Column(db.DateTime, default=datetime.utcnow)
    duration_hours = db.Column(db.Float)                         # for 'freed'

# Create tables
with app.app_context():
    db.create_all()


# ───────────── Routes ────────────────
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "parking-analytics"})
    """
    Health probe
    ---
    tags: [Utility]
    responses:
      200:
        description: Service is running
        schema: {type: object, properties: {status:{type:string}, service:{type:string}}}
    """
    return jsonify(status="healthy", service="parking-analytics")


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
    """
    Track a parking-spot event
    ---
    tags: [Events]
    parameters:
      - in: body
        name: payload
        required: true
        schema:
          type: object
          required: [user_id, spot_id, action]
          properties:
            user_id:        {type: string, example: "6fe860b7-…"}
            spot_id:        {type: integer, example: 9}
            action:         {type: string, enum: [occupied, freed]}
            duration_hours: {type: number, example: 1.5}
    responses:
      201: {description: Event stored}
      400: {description: Invalid payload}
    """
    data = request.get_json(force=True)
    if not all(k in data for k in ("user_id", "spot_id", "action")):
        return jsonify(error="user_id, spot_id, action required"), 400

    db.session.add(ParkingEvent(**data))
    db.session.commit()

    return jsonify({"message": "Event tracked successfully"}), 201
    return jsonify(message="Event tracked successfully"), 201


@app.route('/api/analytics/popular-spots', methods=['GET'])
def get_popular_spots():
    """Get most frequently used parking spots"""
    """
    Top 10 most frequently occupied spots
    ---
    tags: [Analytics]
    responses:
      200:
        description: List ordered by usage
        schema:
          type: object
          properties:
            popular_spots:
              type: array
              items:
                type: object
                properties:
                  spot_id:      {type: integer}
                  usage_count:  {type: integer}
    """
    events = db.session.query(
        ParkingEvent.spot_id,
        db.func.count(ParkingEvent.id).label('usage_count')
    ).filter(ParkingEvent.action == 'occupied').group_by(ParkingEvent.spot_id).order_by(
        db.func.count(ParkingEvent.id).desc()).limit(10).all()
    ).filter(ParkingEvent.action == 'occupied')\
     .group_by(ParkingEvent.spot_id)\
     .order_by(db.func.count(ParkingEvent.id).desc())\
     .limit(10).all()

    result = [{"spot_id": event.spot_id, "usage_count": event.usage_count} for event in events]
    return jsonify({"popular_spots": result})
    return jsonify(popular_spots=[
        {"spot_id": sid, "usage_count": cnt} for sid, cnt in events
    ])


@app.route('/api/analytics/frequent-users', methods=['GET'])
def get_frequent_users():
    """Get users who park most frequently"""
    """
    Top 10 users by parking sessions
    ---
    tags: [Analytics]
    responses:
      200:
        description: List ordered by number of sessions
    """
    events = db.session.query(
        ParkingEvent.user_id,
        db.func.count(ParkingEvent.id).label('parking_sessions')
    ).filter(ParkingEvent.action == 'occupied').group_by(ParkingEvent.user_id).order_by(
        db.func.count(ParkingEvent.id).desc()).limit(10).all()
    ).filter(ParkingEvent.action == 'occupied')\
     .group_by(ParkingEvent.user_id)\
     .order_by(db.func.count(ParkingEvent.id).desc())\
     .limit(10).all()

    result = [{"user_id": event.user_id, "parking_sessions": event.parking_sessions} for event in events]
    return jsonify({"frequent_users": result})
    return jsonify(frequent_users=[
        {"user_id": uid, "parking_sessions": cnt} for uid, cnt in events
    ])


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
    """
    Overall usage statistics
    ---
    tags: [Analytics]
    responses:
      200:
        description: Aggregated numbers
    """
    total  = ParkingEvent.query.filter_by(action='occupied').count()
    users  = db.session.query(ParkingEvent.user_id).distinct().count()
    spots  = db.session.query(ParkingEvent.spot_id).distinct().count()

    return jsonify(
        total_parking_sessions=total,
        unique_users=users,
        unique_spots_used=spots
    )


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
    """
    Convenience endpoint that bundles all analytics
    ---
    tags: [Analytics]
    responses:
      200:
        description: Combined payload for dashboards
    """
    return jsonify(dashboard={
        **get_popular_spots().get_json(),
        **get_frequent_users().get_json(),
        **get_usage_stats().get_json(),
        "last_updated": datetime.utcnow().isoformat()
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))