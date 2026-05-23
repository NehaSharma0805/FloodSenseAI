from config import *
from flask import Flask, render_template, request, jsonify
import requests
import math
import sqlite3
import google.generativeai as genai


genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("models/gemini-2.5-flash")

app = Flask(__name__)
def init_db():
  
    conn = sqlite3.connect("history.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        latitude TEXT,
        longitude TEXT,
        risk_score REAL,
        risk_level TEXT,
        location TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

init_db()

# Landing Page
@app.route("/")
def landing():
    return render_template("landing.html")


# Home Page
@app.route("/home")
def home():
    return render_template(
        "home.html",
        maps_api_key=GOOGLE_MAPS_API_KEY
    )

# Result Page
@app.route("/result")
def result():
    return render_template("result.html")


# History Page
@app.route("/history")
def history():
    return render_template("history.html")

@app.route("/clear-history", methods=["POST"])
def clear_history():

    conn = sqlite3.connect("history.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM history")

    conn.commit()
    conn.close()

    return jsonify({
        "message": "History cleared successfully"
    })   


# About Page
@app.route("/about")
def about():
    return render_template("about.html")

# Get History API
@app.route("/get-history")
def get_history():
    conn = sqlite3.connect("history.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM history ORDER BY date DESC")
    rows = cursor.fetchall()

    conn.close()

    return jsonify(rows)



# ✅ ANALYZE ROUTE (MOVE HERE)
@app.route("/analyze", methods=["POST"])
def analyze():

    data = request.get_json()

    lat = data.get("latitude")
    lon = data.get("longitude")
    location_name = data.get("location_name")
    print("Received location:", location_name)
    
    
    API_KEY = WEATHER_API_KEY

    weather_url = (
        f"http://api.weatherapi.com/v1/forecast.json"
        f"?key={API_KEY}&q={lat},{lon}&days=1"
    )

    ELEVATION_API_KEY = GOOGLE_MAPS_API_KEY
    elevation_url = (
        f"https://maps.googleapis.com/maps/api/elevation/json"
        f"?locations={lat},{lon}&key={ELEVATION_API_KEY}"
    )

    # Elevation
    elevation_response = requests.get(elevation_url)
    elevation_data = elevation_response.json()
    if elevation_data.get("results"):
     elevation = elevation_data["results"][0]["elevation"]
    else:
      print("Elevation API error:", elevation_data)
    elevation = 100  # fallback value

    # Weather
    response = requests.get(weather_url)
    weather_data = response.json()

    weather_condition = weather_data["current"]["condition"]["text"]
    temperature = weather_data["current"]["temp_c"]
    rainfall = weather_data["current"]["precip_mm"]
    forecast_rain = weather_data["forecast"]["forecastday"][0]["day"]["totalprecip_mm"]
    humidity = weather_data["current"]["humidity"]
    wind_speed = weather_data["current"]["wind_kph"]
    pressure = weather_data["current"]["pressure_mb"]

    # River distance
    PLACES_API_KEY = GOOGLE_MAPS_API_KEY
    places_url = (
        "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        f"?location={lat},{lon}"
        "&radius=3000"
        "&keyword=water+body|river|stream|lake"
        f"&key={PLACES_API_KEY}"
    )

    places_response = requests.get(places_url)
    places_data = places_response.json()

    river_distance = 10.0

    if places_data.get("results"):
        place_lat = places_data["results"][0]["geometry"]["location"]["lat"]
        place_lon = places_data["results"][0]["geometry"]["location"]["lng"]

        river_distance = float(((float(lat)-place_lat)**2 + (float(lon)-place_lon)**2) ** 0.5 * 111)

    # ------------------ RISK MODEL ------------------

    # Rainfall
    if rainfall > 15:
        rainfall_score = 1
    elif rainfall > 5:
        rainfall_score = 0.6
    else:
        rainfall_score = 0.2

    # Elevation
    if elevation < 50:
        elevation_score = 1
    elif elevation < 200:
        elevation_score = 0.6
    else:
        elevation_score = 0.2

    # River
    if river_distance < 1:
        river_score = 1
    elif river_distance < 5:
        river_score = 0.6
    else:
        river_score = 0.2

    # Forecast
    if forecast_rain > 20:
        forecast_score = 1
    elif forecast_rain > 5:
        forecast_score = 0.6
    else:
        forecast_score = 0.2

    # Final score
    risk_index = (
        0.35 * rainfall_score +
        0.25 * forecast_score +
        0.20 * elevation_score +
        0.20 * river_score
    )

    risk_score = round(risk_index * 10, 2)

    if risk_score >= 7:
        risk_level = "High"
    elif risk_score >= 4:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    # ------------------ GEMINI ------------------

    try:
        prompt = f"""
        Flood Risk Analysis:

        Rainfall: {rainfall} mm
        Forecast Rainfall: {forecast_rain} mm
        Elevation: {round(elevation,2)} meters
        River distance: {round(river_distance,2)} km

        Risk level: {risk_level}

        -Explain the flood risk in 3 short sentences.
        -Give 3 simple safety suggestions.
        

        Do not include headings or numbering.
        """

        response = model.generate_content(prompt)
        text = response.text

        parts = text.split("\n")
        reason = parts[0]
        suggestions = "\n".join(parts[1:])

    except Exception as e:
        print("Gemini error:", e)
        reason = "Flood risk estimated based on environmental conditions."
        suggestions = "Stay alert, avoid risky areas, and follow guidelines."

    # ------------------ CONFIDENCE ------------------

    confidence = 0

    if rainfall is not None:
        confidence += 20
    if forecast_rain is not None:
        confidence += 15
    if elevation is not None:
        confidence += 20

    if river_distance != 10:
        confidence += 15
    else:
        confidence += 5

    if humidity is not None:
        confidence += 10
    if wind_speed is not None:
        confidence += 10
    if pressure is not None:
        confidence += 10

    confidence = min(confidence, 95)

 #------------------------ DATABASE ------------------
    conn = sqlite3.connect("history.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO history (latitude, longitude, risk_score, risk_level, location)
    VALUES (?, ?, ?, ?, ?)
    """, (lat, lon, risk_score, risk_level, location_name))

    conn.commit()
    conn.close() 

    # ------------------ RESPONSE ------------------

    return jsonify({
        "location_name": location_name,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "reason": reason,
        "suggestions": suggestions,
        "weather": weather_condition,
        "temperature": temperature,
        "rainfall": rainfall,
        "forecast_rain": forecast_rain,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "pressure": pressure,
        "elevation": elevation,
        "river_distance": river_distance,
        "confidence": confidence
        
    })



# ALWAYS LAST
if __name__ == "__main__":
    app.run(debug=True)
