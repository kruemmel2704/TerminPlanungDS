from . import db
from flask_login import UserMixin
from datetime import datetime

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    discord_id = db.Column(db.String(100), unique=True)
    username = db.Column(db.String(150))
    avatar = db.Column(db.String(255))
    is_admin = db.Column(db.Boolean, default=False)
    google_token = db.Column(db.Text)  # Store JSON serialized token for Calendar
    google_calendar_id = db.Column(db.String(200), nullable=True) # Persistent calendar ID

class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(50), default='voting') # voting, pending, finalized
    winner_option_id = db.Column(db.Integer, db.ForeignKey('option.id'), nullable=True)
    
    # Roster Fields
    war_orga = db.Column(db.String(200))
    players = db.Column(db.String(500)) # Storing as comma-separated or simple text
    substitutes = db.Column(db.String(500))
    
    options = db.relationship('Option', backref='poll', lazy=True, cascade="all, delete-orphan", foreign_keys="Option.poll_id")

    @property
    def unique_voter_count(self):
        return len(set(vote.user_id for option in self.options for vote in option.votes))

    @property
    def unique_voter_names(self):
        voters = {vote.user_name for option in self.options for vote in option.votes}
        return sorted(list(voters))

class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    votes = db.relationship('Vote', backref='option', lazy=True, cascade="all, delete-orphan")

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.Integer, db.ForeignKey('option.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_name = db.Column(db.String(150), nullable=False)  # Cache username at time of vote
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
