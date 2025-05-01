import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import random
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a strong secret key

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Redirect root to register page
@app.route('/')
def index():
    return redirect(url_for('register'))

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        if not name or not email or not password or not confirm:
            return render_template('register.html', error='All fields are required.')
        if password != confirm:
            return render_template('register.html', error='Passwords do not match.')

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (email, password, name) VALUES (?, ?, ?)', (email, password, name))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error='Email already exists.')
        conn.close()
        return redirect(url_for('login'))

    return render_template('register.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT name FROM users WHERE email = ? AND password = ?', (email, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['user'] = user[0]  # Store user's name
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error='Invalid email or password.')

    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# Home page
@app.route('/home')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['user'])

# Amazon scraper
def get_amazon_product_data(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }
    try:
        page = requests.get(url, headers=headers)
        soup = BeautifulSoup(page.content, "html.parser")

        title_tag = soup.find("span", {"id": "productTitle"})
        title = title_tag.get_text(strip=True) if title_tag else "No Title Found"

        price_tag = (
            soup.find("span", {"id": "priceblock_ourprice"}) or
            soup.find("span", {"id": "priceblock_dealprice"}) or
            soup.find("span", {"class": "a-price-whole"})
        )
        price_text = price_tag.get_text(strip=True).replace(",", "").replace("₹", "") if price_tag else None
        price = int(float(price_text.split('.')[0])) if price_text else None

        image_tag = soup.find("img", {"id": "landingImage"})
        image_url = image_tag['src'] if image_tag else None

        return title, price, image_url

    except Exception as e:
        print("Error scraping:", e)
        return None, None, None

# Price prediction API
@app.route('/predict', methods=['POST'])
def predict():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    product_url = data.get('url')

    title, real_price, image_url = get_amazon_product_data(product_url)
    if real_price is None:
        return jsonify({"error": "Could not fetch product data."}), 400

    prices = [real_price + random.randint(-200, 200) for _ in range(6)] + [real_price]
    dates = [(datetime.now() - timedelta(days=6 - i)).strftime('%Y-%m-%d') for i in range(7)]

    trend = (prices[-1] - prices[0]) / 6
    predicted_price = round(prices[-1] + trend)
    suggestion = "Buy Now ✅" if predicted_price > prices[-1] else "Wait 🕒"

    return jsonify({
        'title': title,
        'current_price': real_price,
        'predicted_price': predicted_price,
        'suggestion': suggestion,
        'prices': prices,
        'dates': dates,
        'image_url': image_url
    })

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
