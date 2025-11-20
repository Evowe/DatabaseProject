# Baseball Stats Database Application

## Features

### Core Features (Project Requirements)
- **User Authentication**: Secure user registration and login with password hashing
- **Team Statistics Search**: Search for teams by name or ID (e.g., "Boston Red Sox" or "BOS")
- **Batting Statistics Display**: Comprehensive batting statistics including:
  - Games (G), At Bats (AB), Plate Appearances (PA), Hits (H)
  - Singles (1B), Doubles (2B), Triples (3B), Home Runs (HR)
  - Runs (R), RBIs, Walks (BB), Strikeouts (SO), Stolen Bases (SB)
  - Batting Average (AVG), On-Base Percentage (OBP), Slugging % (SLG), Isolated Power (ISO), BABIP
- **Pitching Statistics**: Complete pitching stats with ERA, BAA, WHIP, saves, and more
- **Fielding Statistics**: Fielding data by position including putouts, assists, errors, fielding average
- **Hall of Fame Recognition**: Players inducted into the Hall of Fame are marked with badges

### Enhanced Features
- **Player Career Pages**: View complete career statistics broken down year by year
- **Smart Team Autocomplete**: Real-time team suggestions while typing
- **Player Search**: Quickly find any player in the database with autocomplete
- **CSV Export**: Export team statistics to CSV for further analysis
- **Sortable Tables**: Click column headers to sort statistics in ascending/descending order
- **Admin Dashboard**: Admin users can promote/demote users and manage accounts
- **Social Features**: Create posts, comment on posts, and like content
- **Responsive Design**: Bootstrap 5 UI that works on all device sizes


**Python Version:** 3.12 or later (tested with 3.13.9)

## Installation & Setup

### Prerequisites
- Python 3.12 or later
- MariaDB/MySQL server running

### Step 1: Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install Flask==3.1.2 Flask-SQLAlchemy==3.1.1 Flask-Login==0.6.3 Flask-WTF==1.2.2 PyMySQL==1.1.2 email-validator==2.3.0 python-dotenv==1.2.1 Werkzeug==3.1.3
```

### Step 3: Configure Database Connection
Edit `csi3335f2025.py` with your database credentials:
```python
mysql = {
    'host': 'localhost',           # Your MySQL host
    'user': 'root',                # Your MySQL username
    'password': 'your_password',   # Your MySQL password
    'database': 'baseball'         # The baseball database
}
```

### Step 4: Initialize Database Tables
Run the SQL file to create user-related tables:
```bash
mysql -u root -p baseball < user.sql
```

This creates:
- `users` table for authentication and user management
- `posts` table for social feed posts
- `comments` table for post comments
- `likes` table for post likes
- Default admin user (username: `admin`, password: `admin`)

**Note:** The application has SQLAlchemy models defined in `models.py` that match these database tables. Running the SQL file ensures the database schema is properly initialized.

### Step 5: Run the Application
```bash
flask run
# Or directly:
python main.py
```

The application will start at `http://localhost:5000`

## Usage

### First Time Users
1. Click "Register" to create a new account
2. Enter a username, email, and password
3. Click "Sign In" and login with your credentials

### Admin User
- Username: `admin`
- Password: `admin`
- Admins can access the admin dashboard to manage users and delete any posts/comments

### Searching Team Statistics
1. Login to your account
2. Click "Search Stats" in the navigation
3. Type a team name (e.g., "Yankees", "Red Sox") or team ID (e.g., "NYY", "BOS")
4. Select the year
5. Click "Search"
6. View statistics in batting, pitching, or fielding tabs
7. Click column headers to sort by any statistic
8. Click "Export to CSV" to download the data

### Finding Player Information
1. Click "Find Player" in the navigation
2. Type a player's name
3. Click on a player to view their complete career statistics
4. View year-by-year breakdowns for batting, pitching, and fielding
5. Click column headers to sort the data
6. Hall of Fame players will have a "HOF" badge

### Social Features
1. Create posts on the home feed by typing in the text area
2. Like posts from other users by clicking the heart icon
3. Comment on posts by clicking "Comment" and entering your text
4. Delete your own posts and comments (admins can delete any content)
5. See like and comment counts on each post

### Security Features

- **Password Hashing**: All passwords are hashed using Werkzeug's security functions
- **CSRF Protection**: Flask-WTF provides CSRF tokens on all forms
- **SQL Injection Prevention**: All database queries use parameterized statements
- **Login Required**: Protected routes require authentication with @login_required decorator
- **Admin Authorization**: Admin routes require both authentication and admin flag
- **Session Management**: Flask-Login handles secure session management
- **Input Validation**: WTForms validates all user input before processing

