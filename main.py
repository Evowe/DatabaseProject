from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from csi3335f2025 import mysql
from models import db, User, Post, Comment, Like
from forms import LoginForm, RegistrationForm, TeamStatsForm, PostForm, CommentForm
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


# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.created_at.desc()).paginate(page=page, per_page=10)
    form = PostForm()
    return render_template('index.html', posts=posts, form=form)


@app.route('/post/create', methods=['POST'])
@login_required
def create_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(content=form.content.data, user_id=current_user.id)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
    return redirect(url_for('index'))


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)

    # Only allow post author or admin to delete
    if post.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    db.session.delete(post)
    db.session.commit()

    return jsonify({'success': True})


@app.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)

    # Check if user already liked this post
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()

    if existing_like:
        # Unlike
        db.session.delete(existing_like)
        db.session.commit()
        return jsonify({'success': True, 'liked': False, 'like_count': post.get_like_count()})
    else:
        # Like
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        db.session.commit()
        return jsonify({'success': True, 'liked': True, 'like_count': post.get_like_count()})


@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)

    # Handle AJAX JSON request
    if request.is_json:
        data = request.get_json()
        content = data.get('content', '').strip()

        if not content or len(content) > 500:
            return jsonify({'success': False, 'message': 'Invalid comment'}), 400

        comment = Comment(content=content, user_id=current_user.id, post_id=post_id)
        db.session.add(comment)
        db.session.commit()

        return jsonify({
            'success': True,
            'comment_id': comment.id,
            'username': current_user.username
        })

    # Handle form submission (traditional)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(content=form.content.data, user_id=current_user.id, post_id=post_id)
        db.session.add(comment)
        db.session.commit()
        flash('Your comment has been added!', 'success')

    return redirect(url_for('index'))


@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    post_id = comment.post_id

    # Only allow comment author or admin to delete
    if comment.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    db.session.delete(comment)
    db.session.commit()

    return jsonify({'success': True})


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


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard to manage users"""
    users = User.query.all()
    return render_template('admin/dashboard.html', users=users)


@app.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    """Toggle admin status for a user"""
    user = User.query.get_or_404(user_id)

    # Prevent admin from removing their own admin status
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot change your own admin status'}), 400

    user.is_admin = not user.is_admin
    db.session.commit()

    status = 'promoted to' if user.is_admin else 'demoted from'
    flash(f'User {user.username} has been {status} admin.', 'success')
    return jsonify({'success': True, 'is_admin': user.is_admin})


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user"""
    user = User.query.get_or_404(user_id)

    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot delete your own account'}), 400

    username = user.username
    db.session.delete(user)
    db.session.commit()

    flash(f'User {username} has been deleted.', 'success')
    return jsonify({'success': True})


@app.route('/api/players', methods=['GET'])
def get_players():
    """API endpoint to get player suggestions based on search query"""
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return jsonify({'players': []})

    try:
        connection = pymysql.connect(
            host=mysql['host'],
            user=mysql['user'],
            password=mysql['password'],
            database=mysql['database']
        )

        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # Get players that match the query
            sql = """
            SELECT playerID, nameFirst, nameLast
            FROM people
            WHERE nameFirst LIKE %s OR nameLast LIKE %s OR CONCAT(nameFirst, ' ', nameLast) LIKE %s
            ORDER BY nameFirst, nameLast
            LIMIT 10
            """
            cursor.execute(sql, (f"%{query}%", f"%{query}%", f"%{query}%"))
            players = cursor.fetchall()

        connection.close()

        return jsonify({
            'players': [{'id': p['playerID'], 'name': f"{p['nameFirst']} {p['nameLast']}"} for p in players]
        })
    except Exception as e:
        return jsonify({'players': [], 'error': str(e)}), 500


@app.route('/find-player')
@login_required
def find_player():
    """Player search page"""
    return render_template('find_player.html')


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
    batting_stats = None
    pitching_stats = None
    fielding_stats = None
    team_name = None
    year = None
    error_message = None

    if form.validate_on_submit():
        team_name = form.team.data
        year = form.year.data

        try:
            connection = pymysql.connect(
                host=mysql['host'],
                user=mysql['user'],
                password=mysql['password'],
                database=mysql['database']
            )

            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # Query for batting stats
                batting_query = """
                SELECT 
                    p.playerID as player_id,
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
                    ROUND(b.b_H / NULLIF(b.b_AB, 0), 3) as batting_average,
                    CASE WHEN hf.playerID IS NOT NULL THEN 1 ELSE 0 END as is_hall_of_fame,
                    hf.yearID as hof_year
                FROM batting b
                JOIN people p ON b.playerID = p.playerID
                JOIN teams t ON b.teamID = t.teamID AND b.yearId = t.yearID
                LEFT JOIN halloffame hf ON p.playerID = hf.playerID AND hf.inducted = 'Y'
                WHERE (t.team_name LIKE %s OR t.teamID LIKE %s) AND b.yearId = %s
                ORDER BY b.b_AB DESC
                """
                cursor.execute(batting_query, (f"%{team_name}%", f"%{team_name}%", year))
                batting_stats = cursor.fetchall()

                # Query for pitching stats
                pitching_query = """
                SELECT 
                    p.playerID as player_id,
                    p.nameFirst as first_name,
                    p.nameLast as last_name,
                    pi.p_G as games,
                    pi.p_GS as games_started,
                    pi.p_CG as complete_games,
                    pi.p_SHO as shutouts,
                    pi.p_W as wins,
                    pi.p_L as losses,
                    pi.p_SV as saves,
                    pi.p_IPOuts as ip_outs,
                    pi.p_H as hits,
                    pi.p_R as runs,
                    pi.p_ER as earned_runs,
                    pi.p_BB as walks,
                    pi.p_SO as strikeouts,
                    pi.p_HR as home_runs,
                    pi.p_ERA as era,
                    pi.p_BAOpp as batting_avg_allowed,
                    CASE WHEN hf.playerID IS NOT NULL THEN 1 ELSE 0 END as is_hall_of_fame,
                    hf.yearID as hof_year
                FROM pitching pi
                JOIN people p ON pi.playerID = p.playerID
                JOIN teams t ON pi.teamID = t.teamID AND pi.yearId = t.yearID
                LEFT JOIN halloffame hf ON p.playerID = hf.playerID AND hf.inducted = 'Y'
                WHERE (t.team_name LIKE %s OR t.teamID LIKE %s) AND pi.yearId = %s
                ORDER BY pi.p_IPOuts DESC
                """
                cursor.execute(pitching_query, (f"%{team_name}%", f"%{team_name}%", year))
                pitching_stats = cursor.fetchall()

                # Query for fielding stats
                fielding_query = """
                SELECT 
                    p.playerID as player_id,
                    p.nameFirst as first_name,
                    p.nameLast as last_name,
                    f.position as position,
                    COALESCE(f.f_G, 0) as games,
                    COALESCE(f.f_GS, 0) as games_started,
                    COALESCE(f.f_InnOuts, 0) as innings_outs,
                    COALESCE(f.f_PO, 0) as putouts,
                    COALESCE(f.f_A, 0) as assists,
                    COALESCE(f.f_E, 0) as errors,
                    COALESCE(f.f_DP, 0) as double_plays,
                    COALESCE(f.f_PB, 0) as passed_balls,
                    ROUND(COALESCE(f.f_PO, 0) / NULLIF(COALESCE(f.f_G, 0), 0), 2) as putouts_per_game,
                    CASE WHEN (COALESCE(f.f_PO, 0) + COALESCE(f.f_A, 0) + COALESCE(f.f_E, 0)) > 0 THEN ROUND((COALESCE(f.f_PO, 0) + COALESCE(f.f_A, 0)) / NULLIF((COALESCE(f.f_PO, 0) + COALESCE(f.f_A, 0) + COALESCE(f.f_E, 0)), 0), 3) ELSE 0 END as fielding_avg,
                    CASE WHEN hf.playerID IS NOT NULL THEN 1 ELSE 0 END as is_hall_of_fame,
                    hf.yearID as hof_year
                FROM fielding f
                JOIN people p ON f.playerID = p.playerID
                JOIN teams t ON f.teamID = t.teamID AND f.yearId = t.yearID
                LEFT JOIN halloffame hf ON p.playerID = hf.playerID AND hf.inducted = 'Y'
                WHERE (t.team_name LIKE %s OR t.teamID LIKE %s) AND f.yearId = %s
                ORDER BY f.f_G DESC
                """
                cursor.execute(fielding_query, (f"%{team_name}%", f"%{team_name}%", year))
                fielding_stats = cursor.fetchall()

            connection.close()

            if not batting_stats and not pitching_stats and not fielding_stats:
                error_message = f"No data found for {team_name} in {year}. Please check the team name and year."

        except Exception as e:
            error_message = f"Error querying database: {str(e)}"
            flash(error_message, 'danger')

    return render_template('search.html', form=form, batting_stats=batting_stats, pitching_stats=pitching_stats,
                           fielding_stats=fielding_stats, team_name=team_name, year=year,
                           error_message=error_message)


@app.route('/player/<player_id>')
@login_required
def player_detail(player_id):
    """Display career statistics for a player"""
    try:
        connection = pymysql.connect(
            host=mysql['host'],
            user=mysql['user'],
            password=mysql['password'],
            database=mysql['database']
        )

        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # Get player info
            player_query = """
            SELECT nameFirst, nameLast, birthYear, deathYear
            FROM people
            WHERE playerID = %s
            """
            cursor.execute(player_query, (player_id,))
            player_info = cursor.fetchone()

            if not player_info:
                connection.close()
                return render_template('error.html', message="Player not found"), 404

            # Get batting career stats year by year
            batting_query = """
            SELECT 
                b.yearId as year,
                t.team_name as team,
                t.teamID as team_id,
                COALESCE(b.b_G, 0) as games,
                COALESCE(b.b_H, 0) as hits,
                COALESCE(b.b_AB, 0) as at_bats,
                COALESCE(b.b_R, 0) as runs,
                COALESCE(b.b_RBI, 0) as rbis,
                COALESCE(b.b_HR, 0) as home_runs,
                COALESCE(b.b_SB, 0) as stolen_bases,
                COALESCE(b.b_2B, 0) as doubles,
                COALESCE(b.b_3B, 0) as triples,
                COALESCE(b.b_BB, 0) as walks,
                COALESCE(b.b_SO, 0) as strikeouts,
                ROUND(COALESCE(b.b_H, 0) / NULLIF(COALESCE(b.b_AB, 0), 0), 3) as batting_average
            FROM batting b
            JOIN teams t ON b.teamID = t.teamID AND b.yearId = t.yearID
            WHERE b.playerID = %s
            ORDER BY b.yearId DESC
            """
            cursor.execute(batting_query, (player_id,))
            batting_stats = cursor.fetchall()

            # Get pitching career stats year by year
            pitching_query = """
            SELECT 
                pi.yearId as year,
                t.team_name as team,
                t.teamID as team_id,
                COALESCE(pi.p_G, 0) as games,
                COALESCE(pi.p_GS, 0) as games_started,
                COALESCE(pi.p_CG, 0) as complete_games,
                COALESCE(pi.p_SHO, 0) as shutouts,
                COALESCE(pi.p_W, 0) as wins,
                COALESCE(pi.p_L, 0) as losses,
                COALESCE(pi.p_SV, 0) as saves,
                COALESCE(pi.p_IPOuts, 0) as ip_outs,
                COALESCE(pi.p_H, 0) as hits,
                COALESCE(pi.p_R, 0) as runs,
                COALESCE(pi.p_ER, 0) as earned_runs,
                COALESCE(pi.p_BB, 0) as walks,
                COALESCE(pi.p_SO, 0) as strikeouts,
                COALESCE(pi.p_HR, 0) as home_runs,
                COALESCE(pi.p_ERA, 0) as era,
                COALESCE(pi.p_BAOpp, 0) as batting_avg_allowed
            FROM pitching pi
            JOIN teams t ON pi.teamID = t.teamID AND pi.yearId = t.yearID
            WHERE pi.playerID = %s
            ORDER BY pi.yearId DESC
            """
            cursor.execute(pitching_query, (player_id,))
            pitching_stats = cursor.fetchall()

            # Get fielding career stats year by year
            fielding_query = """
            SELECT 
                f.yearId as year,
                t.team_name as team,
                t.teamID as team_id,
                f.position as position,
                COALESCE(f.f_G, 0) as games,
                COALESCE(f.f_GS, 0) as games_started,
                COALESCE(f.f_InnOuts, 0) as innings_outs,
                COALESCE(f.f_PO, 0) as putouts,
                COALESCE(f.f_A, 0) as assists,
                COALESCE(f.f_E, 0) as errors,
                COALESCE(f.f_DP, 0) as double_plays,
                COALESCE(f.f_PB, 0) as passed_balls,
                ROUND(COALESCE(f.f_PO, 0) / NULLIF(COALESCE(f.f_G, 0), 0), 2) as putouts_per_game,
                CASE WHEN (COALESCE(f.f_PO, 0) + COALESCE(f.f_A, 0) + COALESCE(f.f_E, 0)) > 0 THEN ROUND((COALESCE(f.f_PO, 0) + COALESCE(f.f_A, 0)) / NULLIF((COALESCE(f.f_PO, 0) + COALESCE(f.f_A, 0) + COALESCE(f.f_E, 0)), 0), 3) ELSE 0 END as fielding_avg
            FROM fielding f
            JOIN teams t ON f.teamID = t.teamID AND f.yearId = t.yearID
            WHERE f.playerID = %s
            ORDER BY f.yearId DESC
            """
            cursor.execute(fielding_query, (player_id,))
            fielding_stats = cursor.fetchall()

            # Check if player is in Hall of Fame
            hof_query = """
            SELECT yearID FROM halloffame
            WHERE playerID = %s AND inducted = 'Y'
            """
            cursor.execute(hof_query, (player_id,))
            hof_info = cursor.fetchone()

        connection.close()

        return render_template('player.html',
                               player_info=player_info,
                               player_id=player_id,
                               batting_stats=batting_stats,
                               pitching_stats=pitching_stats,
                               fielding_stats=fielding_stats,
                               hof_info=hof_info)

    except Exception as e:
        return render_template('error.html', message=f"Error loading player: {str(e)}"), 500


@app.route('/export/csv', methods=['POST'])
@login_required
def export_csv():
    """Export team statistics to CSV file"""
    import csv
    from io import StringIO

    data = request.get_json()
    table_type = data.get('table_type')
    team_name = data.get('team_name')
    year = data.get('year')
    rows = data.get('rows', [])
    headers = data.get('headers', [])

    if not rows or not headers:
        return {'error': 'No data to export'}, 400

    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)

    # Write headers
    writer.writerow(headers)

    # Write rows
    for row in rows:
        writer.writerow(row)

    # Get CSV content
    csv_content = output.getvalue()
    output.close()

    # Create filename
    filename = f"{team_name}_{year}_{table_type}.csv"
    filename = filename.replace(' ', '_')

    # Return as file download
    from flask import make_response
    response = make_response(csv_content)
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.headers['Content-Type'] = 'text/csv'

    return response


@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', message="Page not found"), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error.html', message="An internal server error occurred"), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)