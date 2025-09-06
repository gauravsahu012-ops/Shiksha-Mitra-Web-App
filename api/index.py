from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pandas as pd
from pymongo import MongoClient
import google.generativeai as genai
from flask_mail import Mail, Message
import os
import re
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # hardcoded

def format_text(text):
    def replace_bold(match):
        return f"<b>{match.group(1)}</b>"
    text = re.sub(r'\*\*(.*?)\*\*', replace_bold, text)
    text = text.replace('*', '•')
    return text

s = "I am applying for REAP (Rajasthan's engineering colleges' admission) counselling rajasthan. Give a very short and brief result. Generate a data only on basis of REAP counselling. Never say it may vary something like that or you have idea or it is difficult to tell. I don't want real time data, I just want rough idea. Even if you have no idea or it may vary,give a rough idea but never say you don't know.Generate result for:"

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'mycardiocareindia@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_mail_password'   # hardcoded
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_DEFAULT_SENDER'] = 'mycardiocare@gmail.com'

mail = Mail(app)

# Configure Google's Generative AI API key
genai.configure(api_key="AIzaSyB-clc5NqNrV1ueQBj-nY4WOqwRRJOgIW8")  # hardcoded

# Load CSV
df = pd.read_csv('static/cutoffs_modified.csv')

# MongoDB connection
client = MongoClient('mongodb+srv://siddharthtomar003:oUIcyUk7xwraNjqp@cluster0.664o03z.mongodb.net/SIH', serverSelectionTimeoutMS=50000)
db = client['SIH']
users_collection = db['users']
collection = db['SIHcollection']

# Issue tracking
db = client['issue_tracker']
issues_collection = db['issues']

# -------- ROUTES BELOW ----------

@app.route('/faqs')
def faq():
    return render_template('faq.html')

@app.route('/ping')
def ping():
    return jsonify({"success": True}), 200

@app.route('/submit_issue', methods=['POST'])
def submit_issue():
    name = request.form['name']
    email = request.form['email']
    mobile = request.form['mobile']
    issue = request.form['issue']
    issues_collection.insert_one({
        'name': name, 'email': email, 'mobile': mobile, 'issue': issue
    })
    msg = Message('Issue Submission Confirmation', recipients=[email])
    msg.body = f"Hello {name},\n\nThank you for submitting your issue. Our team will get back to you shortly.\n\nYour Issue: {issue}\n\nBest regards,\nSupport Team"
    mail.send(msg)
    flash('Your issue has been submitted successfully. A confirmation email has been sent to you.')
    return redirect('/home')

@app.route('/collegepredictor')
def index():
    if 'username' not in session:
        flash('You need to log in first')
        return redirect(url_for('login'))
    return render_template('college_predictor.html')

@app.route('/home')
def home():
    if 'username' not in session:
        flash('You need to log in first')
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/chatbot')
def chatbot():
    if 'username' not in session:
        flash('You need to log in first')
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_data = request.json
    user_message = s + user_data.get('message')
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(user_message)
    response_text = response.text.replace('\n', '<br>')
    response_text = format_text(response_text)
    return jsonify({'response': response_text})

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Username and password are required')
            return redirect(url_for('login'))
        user = users_collection.find_one({'username': username})
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Username and password are required')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        if users_collection.find_one({'username': username}):
            flash('Username already exists')
            return redirect(url_for('register'))
        users_collection.insert_one({'username': username, 'password': hashed_password})
        flash('Registration successful')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out')
    return redirect(url_for('login'))

@app.route('/predict', methods=['POST'])
def predict():
    gender = request.form.get('gender')
    sfs_gas = request.form.get('sfs_gas')
    category = request.form.get('category')
    input_rank = int(request.form.get('rank'))
    filtered_df = df[df['category'].str.strip() == sfs_gas.strip()]
    category_column_map = {
        'Gen': 'gen',
        'EWS': 'mews' if gender == 'male' else 'fews',
        'OBC': 'mobc' if gender == 'male' else 'fobc',
        'SC': 'msc' if gender == 'male' else 'fsc',
        'ST': 'mst' if gender == 'male' else 'fst'
    }
    category_column = category_column_map.get(category)
    if not category_column:
        return "Invalid category", 400
    if category_column not in filtered_df.columns:
        return "Category column not found", 500
    filtered_df[category_column] = pd.to_numeric(filtered_df[category_column], errors='coerce')
    result_df = filtered_df[(filtered_df[category_column] >= input_rank) | (filtered_df[category_column].isna())]
    result_df = result_df[['Institute', 'Branch', category_column]]
    result_list = result_df.to_dict(orient='records')
    return render_template('result.html', results=result_list, category_column=category_column, Branch='Branch', Institute='Institute')
