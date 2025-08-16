# parkingAnalyticsService
Deploying to RENDER

# Primer querya za REST
<img width="1096" height="91" alt="image" src="https://github.com/user-attachments/assets/d4559850-aefa-4d65-97cb-331e7761c1e5" />

## Rest queryi ki jih lahko uporabiš
GET	/health	Preveri zdravje (status) servisa
POST	/api/track-parking	Zabeleži dogodek (zasedba/odbitek mesta)
GET	/api/analytics/popular-spots	Najbolj uporabljena parkirna mesta
GET	/api/analytics/frequent-users	Uporabniki z največ parkirnimi sejami
GET	/api/analytics/usage-stats	Statistika uporabe: št. seans, št. uporabnikov
GET	/api/analytics/dashboard	Združeni podatki za prikaz na nadzorni plošči

# Primer querya za GRAPH QL
<img width="1843" height="886" alt="image" src="https://github.com/user-attachments/assets/e45b8689-4421-4e4d-a2c9-5a00745c2011" />

## Graph QL queryi ki jh lahko uporabiš (še več jih je lahko po želji)
query {
  allEvents {
    id
    userId
    spotId
    action
    timestamp
    durationHours
  }
}

query {
  user(userId: "6fe860b7-2a9d-4c4b-88ea-6523deeded0f") {
    userId
    events {
      id
      action
      timestamp
    }
  }
}

query {
  spot(spotId: 9) {
    spotId
    events {
      id
      userId
      action
    }
  }
}
