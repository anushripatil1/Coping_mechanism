from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
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
    conversations = db.relationship('Conversation', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    summary = db.Column(db.String(200))
    messages = db.relationship('ChatMessage', backref='conversation', lazy=True)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.Column(db.String(10))  # 'user' or 'bot'
    content = db.Column(db.Text)

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
    conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.start_time.desc()).all()
    return render_template('dashboard.html', conversations=conversations)

@app.route('/conversation/<int:conversation_id>')
@login_required
def view_conversation(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    if conversation.user_id != current_user.id:
        flash('Access denied')
        return redirect(url_for('dashboard'))
    return render_template('conversation.html', conversation=conversation)

@app.route('/chatbot', methods=['GET', 'POST'])
@login_required
def chatbot():
    try:
        if request.method == 'POST':
            command = request.form.get('command')
            field = request.form.get('field')
            
            # Initialize session data if not exists
            if 'session_data' not in session:
                session['session_data'] = {}
            
            session_data = session['session_data']
            current_conversation = session.get('current_conversation')
            
            # If this is a new conversation (no current conversation)
            if not current_conversation:
                conversation = Conversation(user_id=current_user.id)
                db.session.add(conversation)
                db.session.commit()
                session['current_conversation'] = conversation.id
                current_conversation = conversation.id
            
            # Save user message
            user_message = ChatMessage(
                conversation_id=current_conversation,
                sender='user',
                content=command
            )
            db.session.add(user_message)
            
            if field:
                # Store the answer in session
                session_data[field] = command
                session['session_data'] = session_data
                
                # Get next question or recommendations
                response = get_next_question(session_data)
                
                # If we got recommendations, end the conversation
                if response['type'] == 'response':
                    conversation = Conversation.query.get(current_conversation)
                    conversation.end_time = datetime.utcnow()
                    conversation.summary = f"Stress Analysis - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
                    db.session.commit()
                    
                    # Clear session data
                    session.pop('session_data', None)
                    session.pop('current_conversation', None)
            else:
                # Process new command
                response = process_command(command)
                
                # If starting a new analysis, clear previous session data
                if command.lower() in ['recommend', 'analyze']:
                    session['session_data'] = {}
            
            # Save bot response
            bot_message = ChatMessage(
                conversation_id=current_conversation,
                sender='bot',
                content=response['message'] if response['type'] == 'response' else response['question']
            )
            db.session.add(bot_message)
            db.session.commit()
            
            return jsonify({
                'message': response['message'] if response['type'] == 'response' else response['question'],
                'is_question': response['type'] == 'question',
                'field': response.get('field'),
                'status': 'success'
            })
        
        return render_template('chatbot.html')
    except Exception as e:
        print(f"Error in chatbot route: {str(e)}")  # For debugging
        return jsonify({
            'message': 'Sorry, there was an error processing your request.',
            'status': 'error'
        }), 500

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

def process_command(command):
    if command.lower() in ['recommend', 'analyze']:
        return {
            'type': 'question',
            'question': 'What is your current stress level (1-10)?',
            'field': 'stress_level'
        }
    elif command.lower() == 'help':
        return {
            'type': 'response',
            'message': 'Available commands:\n1. recommend/analyze - Get personalized stress analysis and recommendations\n2. help - Show this help message'
        }
    else:
        return {
            'type': 'response',
            'message': 'I didn\'t understand that command. Type "help" to see available commands.'
        }

def get_next_question(session_data):
    questions = [
        {'field': 'stress_level', 'question': 'What is your current stress level (1-10)?', 'type': 'int', 'min': 1, 'max': 10},
        {'field': 'sleep_duration', 'question': 'How many hours do you sleep per night?', 'type': 'int', 'min': 0, 'max': 24},
        {'field': 'study_hours', 'question': 'How many hours do you study per week?', 'type': 'int', 'min': 0, 'max': 100},
        {'field': 'social_media', 'question': 'How many hours do you spend on social media per day?', 'type': 'int', 'min': 0, 'max': 24},
        {'field': 'exercise', 'question': 'How many hours do you exercise per week?', 'type': 'int', 'min': 0, 'max': 50},
        {'field': 'family_support', 'question': 'Rate your family support (1-5):', 'type': 'int', 'min': 1, 'max': 5},
        {'field': 'financial_stress', 'question': 'Rate your financial stress (1-5):', 'type': 'int', 'min': 1, 'max': 5},
        {'field': 'peer_pressure', 'question': 'Rate your peer pressure (1-5):', 'type': 'int', 'min': 1, 'max': 5},
        {'field': 'relationship_stress', 'question': 'Rate your relationship stress (1-5):', 'type': 'int', 'min': 1, 'max': 5}
    ]

    # Find the first unanswered question
    for q in questions:
        field = q['field']
        if field not in session_data:
            # If this is not the first question, validate the previous answer
            if len(session_data) > 0:
                last_field = list(session_data.keys())[-1]
                last_value = session_data[last_field]
                # Find the question spec for the last field
                last_q = next((item for item in questions if item['field'] == last_field), None)
                if last_q:
                    # Validate integer fields
                    if last_q['type'] == 'int':
                        try:
                            val = int(last_value)
                        except (ValueError, TypeError):
                            return {
                                'type': 'question',
                                'question': f"Please enter a valid number for '{last_q['question']}'",
                                'field': last_field
                            }
                        if not (last_q['min'] <= val <= last_q['max']):
                            return {
                                'type': 'question',
                                'question': f"Please enter a value between {last_q['min']} and {last_q['max']} for '{last_q['question']}'",
                                'field': last_field
                            }
            # Ask the next question
            return {
                'type': 'question',
                'question': q['question'],
                'field': q['field']
            }
    # All questions answered and validated
    return generate_recommendations(session_data)

def generate_recommendations(answers):
    try:
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
        
        # Stress level based recommendations
        if stress_level >= 7:
            recommendations.append("🌟 High stress detected! Let's work on reducing it step by step:")
            recommendations.append("🎯 Practice mindfulness meditation for 10 minutes daily")
            recommendations.append("💆‍♂️ Try progressive muscle relaxation before bed")
            recommendations.append("👥 Consider talking to a counselor or therapist")
        elif stress_level >= 4:
            recommendations.append("✨ Moderate stress levels - good time to implement preventive measures:")
            recommendations.append("🧘‍♀️ Start with 5 minutes of deep breathing exercises daily")
            recommendations.append("📝 Keep a stress journal to track triggers")
            recommendations.append("🏃‍♂️ Regular exercise can help manage stress effectively")
        else:
            recommendations.append("🌱 Low stress levels - great job! Let's maintain this:")
            recommendations.append("🌿 Continue with your current stress management practices")
            recommendations.append("📚 Learn new stress prevention techniques")
        
        # Sleep recommendations
        if sleep_duration < 7:
            recommendations.append("\n🌙 Sleep Improvement Tips:")
            recommendations.append("🛌 Aim for 7-8 hours of quality sleep")
            recommendations.append("⏰ Establish a consistent sleep schedule")
            recommendations.append("📱 Avoid screens 1 hour before bedtime")
        
        # Study recommendations
        if study_hours > 40:
            recommendations.append("\n📚 Study Management:")
            recommendations.append("⏱️ Break study sessions into 25-minute chunks")
            recommendations.append("🔄 Take 5-minute breaks between sessions")
            recommendations.append("📅 Create a balanced study schedule")
        
        # Social media recommendations
        if social_media > 4:
            recommendations.append("\n📱 Digital Wellbeing:")
            recommendations.append("⏰ Set daily social media time limits")
            recommendations.append("🌿 Take regular digital detox breaks")
            recommendations.append("👥 Focus on real-world connections")
        
        # Exercise recommendations
        if exercise < 3:
            recommendations.append("\n💪 Physical Activity:")
            recommendations.append("🏃‍♀️ Aim for 30 minutes of exercise daily")
            recommendations.append("🧘‍♂️ Try yoga or meditation")
            recommendations.append("🚶‍♂️ Take regular walking breaks")
        
        # Social support recommendations
        if family_support < 3:
            recommendations.append("\n👨‍👩‍👧‍👦 Family Support:")
            recommendations.append("💬 Schedule regular family check-ins")
            recommendations.append("🤝 Join family activities")
            recommendations.append("👥 Consider family counseling if needed")
        
        # Financial stress recommendations
        if financial_stress >= 4:
            recommendations.append("\n💰 Financial Wellness:")
            recommendations.append("📊 Create a monthly budget plan")
            recommendations.append("💡 Seek financial counseling")
            recommendations.append("🎯 Set realistic financial goals")
        
        # Peer pressure recommendations
        if peer_pressure >= 4:
            recommendations.append("\n👥 Peer Relationships:")
            recommendations.append("💪 Practice assertiveness skills")
            recommendations.append("🌟 Surround yourself with supportive friends")
            recommendations.append("🎯 Set clear personal boundaries")
        
        # Relationship stress recommendations
        if relationship_stress >= 4:
            recommendations.append("\n❤️ Relationship Health:")
            recommendations.append("🗣️ Practice open communication")
            recommendations.append("👂 Active listening techniques")
            recommendations.append("🤝 Consider relationship counseling")
        
        return {
            'type': 'response',
            'message': '\n'.join(recommendations)
        }
    except Exception as e:
        print(f"Error in generate_recommendations: {str(e)}")  # For debugging
        return {
            'type': 'response',
            'message': 'I encountered an error while generating recommendations. Please try again.'
        }

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 