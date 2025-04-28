from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stress_chatbot.db'
app.config['SESSION_TYPE'] = 'filesystem'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    history = db.relationship('ChatHistory', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    command = db.Column(db.String(50))
    result = db.Column(db.Text)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('signup'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('signup'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    history = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.timestamp.desc()).all()
    return render_template('dashboard.html', history=history)

@app.route('/chatbot', methods=['GET', 'POST'])
@login_required
def chatbot():
    if request.method == 'POST':
        command = request.form.get('command')
        field = request.form.get('field')
        
        # Get session data from cookies or initialize empty dict
        session_data = {}
        if 'session_data' in session:
            session_data = session['session_data']
        
        if field:
            # Store the answer in session
            session_data[field] = command
            session['session_data'] = session_data
            
            # Get next question or recommendations
            response = get_next_question(session_data)
        else:
            # Process new command
            response = process_command(command)
        
        if response['type'] == 'question':
            # Save to history
            history = ChatHistory(
                user_id=current_user.id,
                command=command,
                result=response['question']
            )
            db.session.add(history)
            db.session.commit()
            
            return render_template('chatbot.html', 
                                result=response['question'],
                                is_question=True,
                                field=response['field'])
        else:
            # Save to history
            history = ChatHistory(
                user_id=current_user.id,
                command=command,
                result=response['message']
            )
            db.session.add(history)
            db.session.commit()
            
            # Clear session data after providing recommendations
            if 'session_data' in session:
                session.pop('session_data')
            
            return render_template('chatbot.html', result=response['message'])
    
    return render_template('chatbot.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

def process_command(command):
    if command.lower() == 'recommend':
        # Start the recommendation process
        if 'session_data' not in session:
            # Initialize the recommendation process
            return {
                'type': 'question',
                'question': 'What is your current stress level (1-10)?',
                'field': 'stress_level'
            }
        else:
            # Continue with the next question based on session data
            return get_next_question(session['session_data'])
    elif command.lower() == 'analyze':
        return {
            'type': 'question',
            'question': 'How many hours do you sleep per night?',
            'field': 'sleep_duration'
        }
    elif command.lower() == 'help':
        return {
            'type': 'response',
            'message': 'Available commands:\n1. recommend - Get personalized coping mechanism recommendations\n2. analyze - Analyze your stress factors\n3. help - Show this help message'
        }
    else:
        return {
            'type': 'response',
            'message': 'I didn\'t understand that command. Type "help" to see available commands.'
        }

def get_next_question(session_data):
    # This function will determine the next question based on previous answers
    questions = [
        {'field': 'sleep_duration', 'question': 'How many hours do you sleep per night?'},
        {'field': 'study_hours', 'question': 'How many hours do you study per week?'},
        {'field': 'social_media', 'question': 'How many hours do you spend on social media per day?'},
        {'field': 'exercise', 'question': 'How many hours do you exercise per week?'},
        {'field': 'family_support', 'question': 'Rate your family support (1-5):'},
        {'field': 'financial_stress', 'question': 'Rate your financial stress (1-5):'},
        {'field': 'peer_pressure', 'question': 'Rate your peer pressure (1-5):'},
        {'field': 'relationship_stress', 'question': 'Rate your relationship stress (1-5):'}
    ]
    
    # Get the next unanswered question
    for question in questions:
        if question['field'] not in session_data:
            return {
                'type': 'question',
                'question': question['question'],
                'field': question['field']
            }
    
    # If all questions are answered, provide recommendations
    return generate_recommendations(session_data)

def generate_recommendations(answers):
    stress_level = int(answers.get('stress_level', 5))
    sleep_duration = int(answers.get('sleep_duration', 7))
    study_hours = int(answers.get('study_hours', 20))
    social_media = int(answers.get('social_media', 3))
    exercise = int(answers.get('exercise', 2))
    family_support = int(answers.get('family_support', 3))
    financial_stress = int(answers.get('financial_stress', 3))
    peer_pressure = int(answers.get('peer_pressure', 3))
    relationship_stress = int(answers.get('relationship_stress', 3))
    
    recommendations = []
    
    # Sleep-related recommendations
    if sleep_duration < 7:
        recommendations.append("• Try to get at least 7-8 hours of sleep per night")
        recommendations.append("• Establish a regular sleep schedule")
    
    # Study-related recommendations
    if study_hours > 40:
        recommendations.append("• Consider breaking your study sessions into smaller chunks")
        recommendations.append("• Take regular breaks during study sessions")
    
    # Social media recommendations
    if social_media > 4:
        recommendations.append("• Try to limit social media usage to 2-3 hours per day")
        recommendations.append("• Take digital detox breaks")
    
    # Exercise recommendations
    if exercise < 3:
        recommendations.append("• Aim for at least 3 hours of exercise per week")
        recommendations.append("• Try activities like walking, yoga, or team sports")
    
    # Stress level based recommendations
    if stress_level >= 7:
        recommendations.append("• Practice mindfulness meditation daily")
        recommendations.append("• Consider talking to a counselor or therapist")
        recommendations.append("• Try progressive muscle relaxation techniques")
    elif stress_level >= 4:
        recommendations.append("• Practice deep breathing exercises")
        recommendations.append("• Maintain a regular exercise routine")
        recommendations.append("• Keep a stress journal")
    else:
        recommendations.append("• Continue with your current stress management practices")
        recommendations.append("• Consider preventive stress management techniques")
    
    # Social support recommendations
    if family_support < 3:
        recommendations.append("• Try to communicate more with family members")
        recommendations.append("• Consider joining support groups")
    
    # Financial stress recommendations
    if financial_stress >= 4:
        recommendations.append("• Create a budget plan")
        recommendations.append("• Seek financial counseling if needed")
    
    # Peer pressure recommendations
    if peer_pressure >= 4:
        recommendations.append("• Practice assertiveness skills")
        recommendations.append("• Surround yourself with supportive friends")
    
    # Relationship stress recommendations
    if relationship_stress >= 4:
        recommendations.append("• Practice open communication")
        recommendations.append("• Consider relationship counseling if needed")
    
    return {
        'type': 'response',
        'message': 'Based on your responses, here are some recommendations:\n' + '\n'.join(recommendations)
    }

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 