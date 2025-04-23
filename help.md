# Learning Platform

A comprehensive Django-based learning platform for managing courses, lessons, live sessions, and student interactions.

## Project Overview

This platform is designed to facilitate online learning with the following core features:

1. **Content Management System**
   - Course creation and organization
   - Lesson management with multimedia support
   - Resource sharing and organization

2. **Live Session Management**
   - Schedule one-on-one or group sessions
   - Google Meet/Teams integration
   - Email reminders for upcoming sessions
   - Session notes and homework tracking

3. **Assessment Tools**
   - Custom quiz creation with various question types
   - Student progress tracking
   - Automated and manual grading

4. **Student Repositories**
   - Personal file storage for each student
   - Organization by course/topic
   - Access and engagement tracking

5. **Booking and Payment Tracking**
   - Teacher availability management
   - Teaching hours tracking
   - Credit management system

## Technology Stack

- **Backend**: Django 5.0+
- **Database**: PostgreSQL
- **Task Queue**: Celery with Redis
- **File Storage**: Local storage (dev) / Amazon S3 (production)
- **Frontend**: HTML, CSS, JavaScript, Bootstrap
- **APIs**: Google Calendar, Meet, etc.

## Project Structure

The project follows a modular architecture with the following Django apps:

```
learning_platform/
├── apps/
│   ├── account/         # User authentication and profiles
│   ├── content/         # Courses, lessons, resources
│   ├── meetings/        # Session scheduling, calendar integration
│   ├── assessment/      # Quizzes, questions, grading
│   ├── repository/      # File storage, student access
│   ├── booking/         # Availability, credits, payments
│   ├── dashboards/      # UI dashboards for different user types
│   └── front_pages/     # Public-facing pages
├── config/              # Project settings and configuration
├── templates/           # Global templates
├── static/              # Static files (CSS, JS, images)
├── media/               # User-uploaded content
└── manage.py            # Django management script
```

## Setup Instructions

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Redis

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/learning-platform.git
   cd learning-platform
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root (see `.env.example` for template):
   ```
   cp .env.example .env
   ```
   Then edit the `.env` file to add your database credentials and other configuration.

5. Run migrations:
   ```
   python manage.py migrate
   ```

6. Create a superuser:
   ```
   python manage.py createsuperuser
   ```

7. Start the development server:
   ```
   python manage.py runserver
   ```

8. In a separate terminal, start Redis and Celery:
   ```
   redis-server
   celery -A config worker -l info
   ```

### Setting Up PostgreSQL

1. Install PostgreSQL on your system
2. Create a database:
   ```
   psql -U postgres
   CREATE DATABASE learning_platform;
   CREATE USER myuser WITH PASSWORD 'mypassword';
   GRANT ALL PRIVILEGES ON DATABASE learning_platform TO myuser;
   ```
3. Update the database settings in your `.env` file

## Development Workflow

1. Create feature branches from `develop` branch
2. Write tests for your features
3. Submit pull requests to `develop`
4. CI/CD pipeline will run tests
5. After review, changes are merged to `develop`
6. Periodically, `develop` is merged to `main` for releases

## Testing

Run tests with:
```
python manage.py test
```

Run with coverage:
```
coverage run --source='.' manage.py test
coverage report
```

## Deployment

The application is configured for deployment on any platform that supports Django. For production:

1. Set `DEBUG=False` in `.env`
2. Configure `ALLOWED_HOSTS`
3. Set up PostgreSQL database
4. Set up Redis
5. Configure S3 or other storage for static/media files
6. Set up a proper web server (Nginx, etc.) with Gunicorn

## API Documentation

API documentation can be accessed at `/api/docs/` when the server is running.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests.




# Running celery
Run celery and celery beat alongside your application:

celery -A web_project worker -l info
celery -A web_project beat -l info