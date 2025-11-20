from flask import render_template, redirect, url_for, flash, request, jsonify, make_response
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from csi3335f2025 import mysql
from models import db, User, Post, Comment, Like
from forms import LoginForm, RegistrationForm, TeamStatsForm, PostForm, CommentForm
import pymysql
import csv
from io import StringIO


# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


def register_routes(app):
    """Register all routes with the Flask app"""

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
                        CASE WHEN b.b_CS IS NOT NULL THEN b.b_CS ELSE 0 END as caught_stealing,
                        b.b_2B as doubles,
                        b.b_3B as triples,
                        b.b_BB as walks,
                        CASE WHEN b.b_IBB IS NOT NULL THEN b.b_IBB ELSE 0 END as intentional_walks,
                        CASE WHEN b.b_HBP IS NOT NULL THEN b.b_HBP ELSE 0 END as hit_by_pitch,
                        CASE WHEN b.b_SH IS NOT NULL THEN b.b_SH ELSE 0 END as sacrifice_hits,
                        CASE WHEN b.b_SF IS NOT NULL THEN b.b_SF ELSE 0 END as sacrifice_flies,
                        b.b_SO as strikeouts,
                        CASE WHEN b.b_GIDP IS NOT NULL THEN b.b_GIDP ELSE 0 END as gdp,
                        (b.b_AB + b.b_BB + CASE WHEN b.b_HBP IS NOT NULL THEN b.b_HBP ELSE 0 END + CASE WHEN b.b_SH IS NOT NULL THEN b.b_SH ELSE 0 END + CASE WHEN b.b_SF IS NOT NULL THEN b.b_SF ELSE 0 END) as plate_appearances,
                        ROUND(b.b_H / NULLIF(b.b_AB, 0), 3) as batting_average,
                        ROUND((b.b_H + b.b_BB + CASE WHEN b.b_HBP IS NOT NULL THEN b.b_HBP ELSE 0 END) / NULLIF((b.b_AB + b.b_BB + CASE WHEN b.b_HBP IS NOT NULL THEN b.b_HBP ELSE 0 END + CASE WHEN b.b_SF IS NOT NULL THEN b.b_SF ELSE 0 END), 0), 3) as on_base_pct,
                        ROUND(((b.b_H - b.b_HR) + (b.b_2B * 2) + (b.b_3B * 3) + (b.b_HR * 4)) / NULLIF(b.b_AB, 0), 3) as slugging_pct,
                        ROUND(((b.b_H - b.b_HR) + (b.b_2B * 2) + (b.b_3B * 3) + (b.b_HR * 4)) / NULLIF(b.b_AB, 0), 3) - ROUND(b.b_H / NULLIF(b.b_AB, 0), 3) as isolated_power,
                        ROUND((b.b_H - b.b_HR) / NULLIF((b.b_AB - b.b_SO - b.b_HR + CASE WHEN b.b_SF IS NOT NULL THEN b.b_SF ELSE 0 END), 0), 3) as babip,
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
                        ROUND(pi.p_IPOuts / 3, 1) as innings_pitched,
                        pi.p_H as hits,
                        pi.p_R as runs,
                        pi.p_ER as earned_runs,
                        pi.p_BB as walks,
                        CASE WHEN pi.p_IBB IS NOT NULL THEN pi.p_IBB ELSE 0 END as intentional_walks,
                        CASE WHEN pi.p_HBP IS NOT NULL THEN pi.p_HBP ELSE 0 END as hit_by_pitch,
                        pi.p_SO as strikeouts,
                        pi.p_HR as home_runs,
                        CASE WHEN pi.p_WP IS NOT NULL THEN pi.p_WP ELSE 0 END as wild_pitches,
                        CASE WHEN pi.p_BK IS NOT NULL THEN pi.p_BK ELSE 0 END as balks,
                        CASE WHEN pi.p_BFP IS NOT NULL THEN pi.p_BFP ELSE 0 END as batters_faced,
                        CASE WHEN pi.p_GF IS NOT NULL THEN pi.p_GF ELSE 0 END as games_finished,
                        CASE WHEN pi.p_SH IS NOT NULL THEN pi.p_SH ELSE 0 END as sacrifice_hits,
                        CASE WHEN pi.p_SF IS NOT NULL THEN pi.p_SF ELSE 0 END as sacrifice_flies,
                        CASE WHEN pi.p_GIDP IS NOT NULL THEN pi.p_GIDP ELSE 0 END as gdp,
                        pi.p_ERA as era,
                        pi.p_BAOpp as batting_avg_allowed,
                        ROUND((pi.p_H + pi.p_BB) / NULLIF(ROUND(pi.p_IPOuts / 3, 1), 0), 3) as whip,
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
                        CASE WHEN f.f_G IS NOT NULL THEN f.f_G ELSE 0 END as games,
                        CASE WHEN f.f_GS IS NOT NULL THEN f.f_GS ELSE 0 END as games_started,
                        CASE WHEN f.f_InnOuts IS NOT NULL THEN f.f_InnOuts ELSE 0 END as innings_outs,
                        CASE WHEN f.f_PO IS NOT NULL THEN f.f_PO ELSE 0 END as putouts,
                        CASE WHEN f.f_A IS NOT NULL THEN f.f_A ELSE 0 END as assists,
                        CASE WHEN f.f_E IS NOT NULL THEN f.f_E ELSE 0 END as errors,
                        CASE WHEN f.f_DP IS NOT NULL THEN f.f_DP ELSE 0 END as double_plays,
                        CASE WHEN f.f_PB IS NOT NULL THEN f.f_PB ELSE 0 END as passed_balls,
                        ROUND((CASE WHEN f.f_PO IS NOT NULL THEN f.f_PO ELSE 0 END) / NULLIF((CASE WHEN f.f_G IS NOT NULL THEN f.f_G ELSE 0 END), 0), 2) as putouts_per_game,
                        CASE WHEN ((CASE WHEN f.f_PO IS NOT NULL THEN f.f_PO ELSE 0 END) + (CASE WHEN f.f_A IS NOT NULL THEN f.f_A ELSE 0 END) + (CASE WHEN f.f_E IS NOT NULL THEN f.f_E ELSE 0 END)) > 0 THEN ROUND(((CASE WHEN f.f_PO IS NOT NULL THEN f.f_PO ELSE 0 END) + (CASE WHEN f.f_A IS NOT NULL THEN f.f_A ELSE 0 END)) / NULLIF(((CASE WHEN f.f_PO IS NOT NULL THEN f.f_PO ELSE 0 END) + (CASE WHEN f.f_A IS NOT NULL THEN f.f_A ELSE 0 END) + (CASE WHEN f.f_E IS NOT NULL THEN f.f_E ELSE 0 END)), 0), 3) ELSE 0 END as fielding_avg,
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
                    CASE WHEN b.b_G IS NOT NULL THEN b.b_G ELSE 0 END as games,
                    CASE WHEN b.b_H IS NOT NULL THEN b.b_H ELSE 0 END as hits,
                    CASE WHEN b.b_AB IS NOT NULL THEN b.b_AB ELSE 0 END as at_bats,
                    CASE WHEN b.b_R IS NOT NULL THEN b.b_R ELSE 0 END as runs,
                    CASE WHEN b.b_RBI IS NOT NULL THEN b.b_RBI ELSE 0 END as rbis,
                    CASE WHEN b.b_HR IS NOT NULL THEN b.b_HR ELSE 0 END as home_runs,
                    CASE WHEN b.b_SB IS NOT NULL THEN b.b_SB ELSE 0 END as stolen_bases,
                    CASE WHEN b.b_CS IS NOT NULL THEN b.b_CS ELSE 0 END as caught_stealing,
                    CASE WHEN b.b_2B IS NOT NULL THEN b.b_2B ELSE 0 END as doubles,
                    CASE WHEN b.b_3B IS NOT NULL THEN b.b_3B ELSE 0 END as triples,
                    CASE WHEN b.b_BB IS NOT NULL THEN b.b_BB ELSE 0 END as walks,
                    CASE WHEN b.b_IBB IS NOT NULL THEN b.b_IBB ELSE 0 END as intentional_walks,
                    CASE WHEN b.b_HBP IS NOT NULL THEN b.b_HBP ELSE 0 END as hit_by_pitch,
                    CASE WHEN b.b_SH IS NOT NULL THEN b.b_SH ELSE 0 END as sacrifice_hits,
                    CASE WHEN b.b_SF IS NOT NULL THEN b.b_SF ELSE 0 END as sacrifice_flies,
                    CASE WHEN b.b_SO IS NOT NULL THEN b.b_SO ELSE 0 END as strikeouts,
                    CASE WHEN b.b_GIDP IS NOT NULL THEN b.b_GIDP ELSE 0 END as gdp,
                    (b.b_AB + b.b_BB + CASE WHEN b.b_HBP IS NOT NULL THEN b.b_HBP ELSE 0 END + CASE WHEN b.b_SH IS NOT NULL THEN b.b_SH ELSE 0 END + CASE WHEN b.b_SF IS NOT NULL THEN b.b_SF ELSE 0 END) as plate_appearances,
                    ROUND((CASE WHEN b.b_H IS NOT NULL THEN b.b_H ELSE 0 END) / NULLIF((CASE WHEN b.b_AB IS NOT NULL THEN b.b_AB ELSE 0 END), 0), 3) as batting_average,
                    ROUND(((CASE WHEN b.b_H IS NOT NULL THEN b.b_H ELSE 0 END) + (CASE WHEN b.b_BB IS NOT NULL THEN b.b_BB ELSE 0 END) + (CASE WHEN b.b_HBP IS NOT NULL THEN b.b_HBP ELSE 0 END)) / NULLIF(((CASE WHEN b.b_AB IS NOT NULL THEN b.b_AB ELSE 0 END) + (CASE WHEN b.b_BB IS NOT NULL THEN b.b_BB ELSE 0 END) + (CASE WHEN b.b_HBP IS NOT NULL THEN b.b_HBP ELSE 0 END) + (CASE WHEN b.b_SF IS NOT NULL THEN b.b_SF ELSE 0 END)), 0), 3) as on_base_pct,
                    ROUND((((CASE WHEN b.b_H IS NOT NULL THEN b.b_H ELSE 0 END) - (CASE WHEN b.b_HR IS NOT NULL THEN b.b_HR ELSE 0 END)) + ((CASE WHEN b.b_2B IS NOT NULL THEN b.b_2B ELSE 0 END) * 2) + ((CASE WHEN b.b_3B IS NOT NULL THEN b.b_3B ELSE 0 END) * 3) + ((CASE WHEN b.b_HR IS NOT NULL THEN b.b_HR ELSE 0 END) * 4)) / NULLIF((CASE WHEN b.b_AB IS NOT NULL THEN b.b_AB ELSE 0 END), 0), 3) as slugging_pct,
                    ROUND((((CASE WHEN b.b_H IS NOT NULL THEN b.b_H ELSE 0 END) - (CASE WHEN b.b_HR IS NOT NULL THEN b.b_HR ELSE 0 END)) + ((CASE WHEN b.b_2B IS NOT NULL THEN b.b_2B ELSE 0 END) * 2) + ((CASE WHEN b.b_3B IS NOT NULL THEN b.b_3B ELSE 0 END) * 3) + ((CASE WHEN b.b_HR IS NOT NULL THEN b.b_HR ELSE 0 END) * 4)) / NULLIF((CASE WHEN b.b_AB IS NOT NULL THEN b.b_AB ELSE 0 END), 0), 3) - ROUND((CASE WHEN b.b_H IS NOT NULL THEN b.b_H ELSE 0 END) / NULLIF((CASE WHEN b.b_AB IS NOT NULL THEN b.b_AB ELSE 0 END), 0), 3) as isolated_power,
                    ROUND(((CASE WHEN b.b_H IS NOT NULL THEN b.b_H ELSE 0 END) - (CASE WHEN b.b_HR IS NOT NULL THEN b.b_HR ELSE 0 END)) / NULLIF(((CASE WHEN b.b_AB IS NOT NULL THEN b.b_AB ELSE 0 END) - (CASE WHEN b.b_SO IS NOT NULL THEN b.b_SO ELSE 0 END) - (CASE WHEN b.b_HR IS NOT NULL THEN b.b_HR ELSE 0 END) + (CASE WHEN b.b_SF IS NOT NULL THEN b.b_SF ELSE 0 END)), 0), 3) as babip
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
                    CASE WHEN pi.p_G IS NOT NULL THEN pi.p_G ELSE 0 END as games,
                    CASE WHEN pi.p_GS IS NOT NULL THEN pi.p_GS ELSE 0 END as games_started,
                    CASE WHEN pi.p_CG IS NOT NULL THEN pi.p_CG ELSE 0 END as complete_games,
                    CASE WHEN pi.p_SHO IS NOT NULL THEN pi.p_SHO ELSE 0 END as shutouts,
                    CASE WHEN pi.p_W IS NOT NULL THEN pi.p_W ELSE 0 END as wins,
                    CASE WHEN pi.p_L IS NOT NULL THEN pi.p_L ELSE 0 END as losses,
                    CASE WHEN pi.p_SV IS NOT NULL THEN pi.p_SV ELSE 0 END as saves,
                    CASE WHEN pi.p_IPOuts IS NOT NULL THEN pi.p_IPOuts ELSE 0 END as ip_outs,
                    ROUND((CASE WHEN pi.p_IPOuts IS NOT NULL THEN pi.p_IPOuts ELSE 0 END) / 3, 1) as innings_pitched,
                    CASE WHEN pi.p_H IS NOT NULL THEN pi.p_H ELSE 0 END as hits,
                    CASE WHEN pi.p_R IS NOT NULL THEN pi.p_R ELSE 0 END as runs,
                    CASE WHEN pi.p_ER IS NOT NULL THEN pi.p_ER ELSE 0 END as earned_runs,
                    CASE WHEN pi.p_BB IS NOT NULL THEN pi.p_BB ELSE 0 END as walks,
                    CASE WHEN pi.p_IBB IS NOT NULL THEN pi.p_IBB ELSE 0 END as intentional_walks,
                    CASE WHEN pi.p_HBP IS NOT NULL THEN pi.p_HBP ELSE 0 END as hit_by_pitch,
                    CASE WHEN pi.p_SO IS NOT NULL THEN pi.p_SO ELSE 0 END as strikeouts,
                    CASE WHEN pi.p_HR IS NOT NULL THEN pi.p_HR ELSE 0 END as home_runs,
                    CASE WHEN pi.p_WP IS NOT NULL THEN pi.p_WP ELSE 0 END as wild_pitches,
                    CASE WHEN pi.p_BK IS NOT NULL THEN pi.p_BK ELSE 0 END as balks,
                    CASE WHEN pi.p_BFP IS NOT NULL THEN pi.p_BFP ELSE 0 END as batters_faced,
                    CASE WHEN pi.p_GF IS NOT NULL THEN pi.p_GF ELSE 0 END as games_finished,
                    CASE WHEN pi.p_SH IS NOT NULL THEN pi.p_SH ELSE 0 END as sacrifice_hits,
                    CASE WHEN pi.p_SF IS NOT NULL THEN pi.p_SF ELSE 0 END as sacrifice_flies,
                    CASE WHEN pi.p_GIDP IS NOT NULL THEN pi.p_GIDP ELSE 0 END as gdp,
                    CASE WHEN pi.p_ERA IS NOT NULL THEN pi.p_ERA ELSE 0 END as era,
                    CASE WHEN pi.p_BAOpp IS NOT NULL THEN pi.p_BAOpp ELSE 0 END as batting_avg_allowed,
                    ROUND(((CASE WHEN pi.p_H IS NOT NULL THEN pi.p_H ELSE 0 END) + (CASE WHEN pi.p_BB IS NOT NULL THEN pi.p_BB ELSE 0 END)) / NULLIF(ROUND((CASE WHEN pi.p_IPOuts IS NOT NULL THEN pi.p_IPOuts ELSE 0 END) / 3, 1), 0), 3) as whip
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
                    CASE WHEN f.f_G IS NOT NULL THEN f.f_G ELSE 0 END as games,
                    CASE WHEN f.f_GS IS NOT NULL THEN f.f_GS ELSE 0 END as games_started,
                    CASE WHEN f.f_InnOuts IS NOT NULL THEN f.f_InnOuts ELSE 0 END as innings_outs,
                    CASE WHEN f.f_PO IS NOT NULL THEN f.f_PO ELSE 0 END as putouts,
                    CASE WHEN f.f_A IS NOT NULL THEN f.f_A ELSE 0 END as assists,
                    CASE WHEN f.f_E IS NOT NULL THEN f.f_E ELSE 0 END as errors,
                    CASE WHEN f.f_DP IS NOT NULL THEN f.f_DP ELSE 0 END as double_plays,
                    CASE WHEN f.f_PB IS NOT NULL THEN f.f_PB ELSE 0 END as passed_balls,
                    ROUND((CASE WHEN f.f_PO IS NOT NULL THEN f.f_PO ELSE 0 END) / NULLIF((CASE WHEN f.f_G IS NOT NULL THEN f.f_G ELSE 0 END), 0), 2) as putouts_per_game,
                    CASE WHEN ((CASE WHEN f.f_PO IS NOT NULL THEN f.f_PO ELSE 0 END) + (CASE WHEN f.f_A IS NOT NULL THEN f.f_A ELSE 0 END) + (CASE WHEN f.f_E IS NOT NULL THEN f.f_E ELSE 0 END)) > 0 THEN ROUND(((CASE WHEN f.f_PO IS NOT NULL THEN f.f_PO ELSE 0 END) + (CASE WHEN f.f_A IS NOT NULL THEN f.f_A ELSE 0 END)) / NULLIF(((CASE WHEN f.f_PO IS NOT NULL THEN f.f_PO ELSE 0 END) + (CASE WHEN f.f_A IS NOT NULL THEN f.f_A ELSE 0 END) + (CASE WHEN f.f_E IS NOT NULL THEN f.f_E ELSE 0 END)), 0), 3) ELSE 0 END as fielding_avg
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
        response = make_response(csv_content)
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.headers['Content-Type'] = 'text/csv'

        return response

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error.html', message="Page not found"), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('error.html', message="An internal server error occurred"), 500