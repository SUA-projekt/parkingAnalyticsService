from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flasgger import Swagger
import os
#za graphql
import strawberry
from strawberry.flask.views import GraphQLView
from typing import Optional, List
from flask_cors import CORS

app = Flask(__name__)

# --- CORS ---
CORS(
    app,
    resources={r"/*": {"origins": [
        "http://localhost:8080",         # dev frontend
        "https://parkinganalyticsservice.onrender.com/api/analytics/dashboard",  
    ]}},
    supports_credentials=False,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    max_age=86400,
)
# ───────────── Database ─────────────
#app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
#    "DATABASE_URL", "sqlite:///analytics.db"
#).replace("postgres://", "postgresql://")
#app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
#db = SQLAlchemy(app)

# ─────────── Swagger config ──────────
swagger = Swagger(app, template={
    "swagger": "2.0",
    "info": {
        "title": "Parking Analytics API",
        "version": "1.0.0",
        "description": "Tracks parking-spot usage and exposes analytics"
    }
})

# ───────────── Database ─────────────
raw_db_url = os.getenv("DATABASE_URL", "sqlite:///analytics.db")
sqlalchemy_db_uri = raw_db_url.replace("postgres://", "postgresql://")

app.config["SQLALCHEMY_DATABASE_URI"] = sqlalchemy_db_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)



# ───────────── Models ────────────────
class ParkingEvent(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.String(100), nullable=False)
    spot_id        = db.Column(db.Integer,       nullable=False)
    action         = db.Column(db.String(20),    nullable=False)  # occupied / freed
    timestamp      = db.Column(db.DateTime, default=datetime.utcnow)
    duration_hours = db.Column(db.Float)                         # for 'freed'

with app.app_context():
    db.create_all()

# ───────────── Routes ────────────────
@app.route('/health', methods=['GET'])
def health_check():
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
    return jsonify(message="Event tracked successfully"), 201


@app.route('/api/analytics/popular-spots', methods=['GET'])
def get_popular_spots():
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
    ).filter(ParkingEvent.action == 'occupied')\
     .group_by(ParkingEvent.spot_id)\
     .order_by(db.func.count(ParkingEvent.id).desc())\
     .limit(10).all()

    return jsonify(popular_spots=[
        {"spot_id": sid, "usage_count": cnt} for sid, cnt in events
    ])


@app.route('/api/analytics/frequent-users', methods=['GET'])
def get_frequent_users():
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
    ).filter(ParkingEvent.action == 'occupied')\
     .group_by(ParkingEvent.user_id)\
     .order_by(db.func.count(ParkingEvent.id).desc())\
     .limit(10).all()

    return jsonify(frequent_users=[
        {"user_id": uid, "parking_sessions": cnt} for uid, cnt in events
    ])


@app.route('/api/analytics/usage-stats', methods=['GET'])
def get_usage_stats():
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
# GRAPH QL ___________________________________________
@strawberry.type
class ParkingEventType:
    id: int
    user_id: str
    spot_id: int
    action: str
    timestamp: datetime
    duration_hours: Optional[float]

@strawberry.type
class UserType:
    user_id: str

    @strawberry.field
    def events(self) -> List[ParkingEventType]:
        db_events = ParkingEvent.query.filter_by(user_id=self.user_id).all()
        return [
            ParkingEventType(
                id=e.id,
                user_id=e.user_id,
                spot_id=e.spot_id,
                action=e.action,
                timestamp=e.timestamp,
                duration_hours=e.duration_hours
            ) for e in db_events
        ]

@strawberry.type
class SpotType:
    spot_id: int

    @strawberry.field
    def events(self) -> List[ParkingEventType]:
        db_events = ParkingEvent.query.filter_by(spot_id=self.spot_id).all()
        return [
            ParkingEventType(
                id=e.id,
                user_id=e.user_id,
                spot_id=e.spot_id,
                action=e.action,
                timestamp=e.timestamp,
                duration_hours=e.duration_hours
            ) for e in db_events
        ]

@strawberry.type
class Query:
    @strawberry.field
    def all_events(self) -> List[ParkingEventType]:
        events = ParkingEvent.query.all()
        return [
            ParkingEventType(
                id=e.id,
                user_id=e.user_id,
                spot_id=e.spot_id,
                action=e.action,
                timestamp=e.timestamp,
                duration_hours=e.duration_hours
            )
            for e in events
        ]

    @strawberry.field
    def user(self, user_id: str) -> Optional[UserType]:
        user_exists = ParkingEvent.query.filter_by(user_id=user_id).first()
        if user_exists:
            return UserType(user_id=user_id)
        return None

    @strawberry.field
    def spot(self, spot_id: int) -> Optional[SpotType]:
        spot_exists = ParkingEvent.query.filter_by(spot_id=spot_id).first()
        if spot_exists:
            return SpotType(spot_id=spot_id)
        return None

schema = strawberry.Schema(Query)

app.add_url_rule(
    '/graphql',
    view_func=GraphQLView.as_view(
        'graphql_view',
        schema=schema,
        graphiql=True
    )
)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
