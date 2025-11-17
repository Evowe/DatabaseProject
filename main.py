from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from csi3335f2025 import mysql
from models import db, User
from forms import LoginForm, RegistrationForm, TeamStatsForm
import pymysql

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-later'
app.config[
    'SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{mysql['user']}:{mysql['password']}@{mysql['host']}/{mysql['database']}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Redirect here if not logged in


# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return "<h1>About Baseball Stats</h1><p>This is a baseball statistics database application.</p>"


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now registered!', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('login'))

        login_user(user)
        flash(f'Welcome back, {user.username}!', 'success')
        next_page = request.args.get('next')
        return redirect(next_page) if next_page else redirect(url_for('index'))

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/api/teams', methods=['GET'])
def get_teams():
    """API endpoint to get team suggestions based on search query"""
    query = request.args.get('q', '').strip()

    if not query or len(query) < 1:
        return jsonify({'teams': []})

    try:
        connection = pymysql.connect(
            host=mysql['host'],
            user=mysql['user'],
            password=mysql['password'],
            database=mysql['database']
        )

        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # Get unique teams that match the query, ordered by team_name
            sql = """
            SELECT DISTINCT team_name, teamID
            FROM teams
            WHERE team_name LIKE %s OR teamID LIKE %s
            ORDER BY team_name
            LIMIT 10
            """
            cursor.execute(sql, (f"%{query}%", f"%{query}%"))
            teams = cursor.fetchall()

        connection.close()

        return jsonify({
            'teams': [{'name': t['team_name'], 'id': t['teamID']} for t in teams]
        })
    except Exception as e:
        return jsonify({'teams': [], 'error': str(e)}), 500


@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    """Search for team statistics by team name and year"""
    form = TeamStatsForm()
    stats = None
    team_name = None
    year = None
    error_message = None

    if form.validate_on_submit():
        team_name = form.team.data
        year = form.year.data

        try:
            # Query to get batting stats for a team in a given year
            query = """
            SELECT 
                p.nameFirst as first_name,
                p.nameLast as last_name,
                b.b_G as games,
                b.b_H as hits,
                b.b_AB as at_bats,
                b.b_R as runs,
                b.b_RBI as rbis,
                b.b_HR as home_runs,
                b.b_SB as stolen_bases,
                b.b_2B as doubles,
                b.b_3B as triples,
                b.b_BB as walks,
                b.b_SO as strikeouts,
                ROUND(b.b_H / NULLIF(b.b_AB, 0), 3) as batting_average
            FROM batting b
            JOIN people p ON b.playerID = p.playerID
            JOIN teams t ON b.teamID = t.teamID AND b.yearId = t.yearID
            WHERE (t.team_name LIKE %s OR t.teamID LIKE %s) AND b.yearId = %s
            ORDER BY b.b_AB DESC
            """

            # Create a direct connection to execute raw SQL
            connection = pymysql.connect(
                host=mysql['host'],
                user=mysql['user'],
                password=mysql['password'],
                database=mysql['database']
            )

            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(query, (f"%{team_name}%", f"%{team_name}%", year))
                stats = cursor.fetchall()

            connection.close()

            if not stats:
                error_message = f"No data found for {team_name} in {year}. Please check the team name and year."

        except Exception as e:
            error_message = f"Error querying database: {str(e)}"
            flash(error_message, 'danger')

    return render_template('search.html', form=form, stats=stats, team_name=team_name, year=year,
                           error_message=error_message)


@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', message="Page not found"), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error.html', message="An internal server error occurred"), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)