from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.shortcuts import redirect
from datetime import timedelta, datetime
from django.db.models import Count, Sum, Avg, Q
from web_project import TemplateLayout

# Import models from different apps
from apps.content.models import Course, Lesson
from apps.repository.models import TeacherResource, StudentFile
from apps.meetings.models import Meeting
from apps.booking.models import BookingSlot, CreditTransaction
from apps.assessment.models import Quiz, Answer


class DashboardOverviewView(LoginRequiredMixin, TemplateView):
    """Enhanced dashboard view that aggregates data from all platform components"""
    template_name = "dashboard_analytics.html"
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set dashboard type to ensure proper menu highlighting
        context['dashboard_type'] = 'overview'
        
        # Set active menu attributes based on the JSON structure
        context['active_menu'] = 'dashboard'
        context['active_submenu'] = 'dashboard-overview'
        
        now = timezone.now()
        user = self.request.user
        
        # Initialize data containers
        context['now'] = now
        
        # ===== Basic User Stats =====
        if user.is_teacher:
            # Teacher statistics
            taught_courses = Course.objects.filter(teacher=user)
            context['course_count'] = taught_courses.count()
            
            # Count unique students across all courses
            student_ids = set()
            for course in taught_courses:
                student_ids.update(course.students.values_list('id', flat=True))
            context['student_count'] = len(student_ids)
            
            # Upcoming teaching sessions
            upcoming_meetings = Meeting.objects.filter(
                teacher=user,
                start_time__gte=now
            ).order_by('start_time')
            context['upcoming_sessions'] = upcoming_meetings.count()
            context['upcoming_meetings'] = upcoming_meetings[:5]  # For display
            
            # Teaching hours this month
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            completed_meetings = Meeting.objects.filter(
                teacher=user,
                start_time__gte=month_start,
                start_time__lt=now
            )
            teaching_hours = sum([meeting.duration for meeting in completed_meetings]) / 60.0
            context['teaching_hours'] = round(teaching_hours, 1)
            
        else:
            # Student statistics
            enrolled_courses = user.enrolled_courses.all()
            context['enrolled_courses'] = enrolled_courses.count()
            
            # Count completed lessons
            completed_lessons = 0
            for course in enrolled_courses:
                # This assumes you're tracking progress in your models
                try:
                    progress = user.course_progress.get(course=course)
                    completed_lessons += progress.lessons_completed.count()
                except:
                    # If no progress model exists
                    pass
            context['completed_lessons'] = completed_lessons
            
            # Get credit balance
            credit_balance = 0
            if CreditTransaction.objects.filter(student=user).exists():
                try:
                    last_transaction = CreditTransaction.objects.filter(student=user).latest('created_at')
                    credit_balance = last_transaction.get_balance()
                except:
                    pass
            context['credit_balance'] = credit_balance
            
            # Get average assessment score
            try:
                total_answers = Answer.objects.filter(student=user).count()
                if total_answers > 0:
                    correct_answers = Answer.objects.filter(student=user, is_correct=True).count()
                    avg_score = (correct_answers / total_answers) * 100
                    context['avg_score'] = round(avg_score)
                else:
                    context['avg_score'] = 0
            except:
                context['avg_score'] = 0
            
            # Upcoming booked sessions
            upcoming_meetings = Meeting.objects.filter(
                students=user,
                start_time__gte=now
            ).order_by('start_time')
            context['upcoming_meetings'] = upcoming_meetings[:5]
        
        # Add links to other parts of the application based on the menu structure
        context['menu_links'] = {
            'courses': '/content/courses/',
            'repository': '/repository/',
            'calendar': '/meetings/calendar/',
            'booking': '/booking/',
            'assessment': '/assessment/quizzes/',
            'messaging': '/chat/'
        }
        
        # Create quick navigation links based on user type
        if user.is_teacher:
            context['quick_links'] = [
                {'name': 'Create Course', 'url': '/content/courses/create/', 'icon': 'book-plus'},
                {'name': 'Schedule Session', 'url': '/meetings/create/', 'icon': 'calendar-plus'},
                {'name': 'Upload Resource', 'url': '/repository/resources/upload/', 'icon': 'upload'},
                {'name': 'Create Quiz', 'url': '/assessment/quizzes/create/', 'icon': 'file-text'}
            ]
        else:
            context['quick_links'] = [
                {'name': 'Browse Courses', 'url': '/content/courses/', 'icon': 'books'},
                {'name': 'Book Session', 'url': '/booking/slots/', 'icon': 'calendar-event'},
                {'name': 'My Resources', 'url': '/repository/files/', 'icon': 'folder'},
                {'name': 'Take Quiz', 'url': '/assessment/quizzes/', 'icon': 'writing'}
            ]
        
        # Generate data for charts based on the template's requirements
        self._add_chart_data(context, user)
        
        # ===== Recent Activity =====
        context['recent_activities'] = self._get_recent_activities(user, now)
        
        # ===== Course Progress =====
        courses_queryset = Course.objects.filter(teacher=user) if user.is_teacher else user.enrolled_courses.all()
        context['courses'] = self._get_course_data(user, courses_queryset)
        
        # ===== Latest Resources =====
        context['resources'] = self._get_resource_data(user)
        
        return context
    
    def _add_chart_data(self, context, user):
        """Add chart data to the context based on user type"""
        now = timezone.now()
        
        # Weekly activity data
        weekly_hours = []
        for day in range(7):
            day_date = now - timedelta(days=now.weekday()) + timedelta(days=day)
            
            # In a real app, you'd query an activity tracking model
            # For demo, generate some reasonable random data
            import random
            if user.is_teacher:
                # Teaching hours per day
                try:
                    day_meetings = Meeting.objects.filter(
                        teacher=user,
                        start_time__date=day_date.date()
                    )
                    hours = sum([meeting.duration for meeting in day_meetings]) / 60.0
                except:
                    hours = random.uniform(0.5, 2.0) if day < 5 else random.uniform(0, 1.0)
            else:
                # Learning hours per day (just for demo - would be tracked in real app)
                hours = random.uniform(0.5, 3.0) if day < 5 else random.uniform(0, 1.5)
                
            weekly_hours.append(round(hours, 1))
        
        context['weekly_hours'] = weekly_hours
        
        # Calculate total stats
        context['total_hours'] = round(sum(weekly_hours))
        
        if user.is_teacher:
            try:
                context['total_completed'] = TeacherResource.objects.filter(teacher=user).count()
                context['assessments_taken'] = Quiz.objects.filter(teacher=user).count()
                context['total_sessions'] = Meeting.objects.filter(teacher=user).count()
            except:
                context['total_completed'] = 0
                context['assessments_taken'] = 0
                context['total_sessions'] = 0
        else:
            context['total_completed'] = context.get('completed_lessons', 0)
            try:
                context['assessments_taken'] = Answer.objects.filter(student=user).values('question__quiz').distinct().count()
                context['total_sessions'] = Meeting.objects.filter(students=user).count()
            except:
                context['assessments_taken'] = 0
                context['total_sessions'] = 0
    
    def _get_recent_activities(self, user, now):
        """Get recent activities for the user"""
        recent_activities = []
        
        # Check for recent meeting attendance
        try:
            recent_meetings = Meeting.objects.filter(
                Q(teacher=user) | Q(students=user),
                start_time__lt=now,
                start_time__gte=now - timedelta(days=7)
            ).order_by('-start_time')[:3]
            
            for meeting in recent_meetings:
                activity = {
                    'title': f"{'Taught' if user.is_teacher else 'Attended'} session",
                    'description': meeting.title,
                    'time_ago': self._get_time_ago(meeting.start_time),
                    'icon': 'video',
                    'color': 'success'
                }
                recent_activities.append(activity)
        except:
            pass
        
        # Check for recent quiz attempts
        if not user.is_teacher:
            try:
                recent_answers = Answer.objects.filter(
                    student=user
                ).order_by('-id')[:3]
                
                for answer in recent_answers:
                    activity = {
                        'title': f"Answered a question",
                        'description': f"Quiz: {answer.question.quiz.title}",
                        'time_ago': self._get_time_ago(answer.question.quiz.created_at),
                        'icon': 'file-text',
                        'color': 'info'
                    }
                    recent_activities.append(activity)
            except:
                pass
        
        # Check for recent uploads
        if user.is_teacher:
            try:
                recent_resources = TeacherResource.objects.filter(
                    teacher=user
                ).order_by('-upload_date')[:3]
                
                for resource in recent_resources:
                    activity = {
                        'title': f"Uploaded resource",
                        'description': resource.title,
                        'time_ago': self._get_time_ago(resource.upload_date),
                        'icon': 'upload',
                        'color': 'primary'
                    }
                    recent_activities.append(activity)
            except:
                pass
        else:
            try:
                recent_files = StudentFile.objects.filter(
                    student=user
                ).order_by('-upload_date')[:3]
                
                for file in recent_files:
                    activity = {
                        'title': f"Uploaded file",
                        'description': file.title,
                        'time_ago': self._get_time_ago(file.upload_date),
                        'icon': 'upload',
                        'color': 'primary'
                    }
                    recent_activities.append(activity)
            except:
                pass
        
        # Sort activities by recency and take the 5 most recent
        recent_activities.sort(key=lambda x: self._parse_time_ago(x['time_ago']))
        return recent_activities[:5]
    
    def _get_course_data(self, user, courses_queryset):
        """Get course data based on user type"""
        courses = []
        
        if user.is_teacher:
            # For teachers, show stats about their courses
            for course in courses_queryset[:5]:
                total_students = course.students.count()
                total_lessons = course.lessons.count()
                
                # Calculate average progress across all students
                if total_students > 0:
                    total_progress = 0
                    for student in course.students.all():
                        try:
                            progress = student.course_progress.get(course=course)
                            student_progress = (progress.lessons_completed.count() / max(total_lessons, 1)) * 100
                            total_progress += student_progress
                        except:
                            pass
                    avg_progress = total_progress / total_students if total_students > 0 else 0
                else:
                    avg_progress = 0
                    
                course_data = {
                    'id': course.id,
                    'title': course.title,
                    'progress': round(avg_progress),
                    'image': course.image if hasattr(course, 'image') else None,
                    'students_count': total_students,
                    'lessons_count': total_lessons
                }
                courses.append(course_data)
        else:
            # For students, show their course progress
            for course in courses_queryset[:5]:
                total_lessons = course.lessons.count()
                completed = 0
                
                try:
                    progress = user.course_progress.get(course=course)
                    completed = progress.lessons_completed.count()
                except:
                    pass
                    
                progress_pct = (completed / max(total_lessons, 1)) * 100
                
                course_data = {
                    'id': course.id,
                    'title': course.title,
                    'lessons_count': total_lessons,
                    'progress': round(progress_pct),
                    'completed_lessons': completed,
                    'image': course.image if hasattr(course, 'image') else None,
                }
                courses.append(course_data)
        
        return courses
    
    def _get_resource_data(self, user):
        """Get resource data based on user type"""
        resources = []
        
        try:
            if user.is_teacher:
                latest_resources = TeacherResource.objects.filter(
                    teacher=user
                ).order_by('-upload_date')[:5]
            else:
                # Get resources the student has access to
                accessible_resources = user.accessible_resources.all()
                
                # Also include resources from enrolled courses
                course_resources = TeacherResource.objects.filter(
                    course__in=user.enrolled_courses.all(),
                    is_public=True
                )
                
                # Combine and sort
                latest_resources = list(accessible_resources)
                for resource in course_resources:
                    if resource not in latest_resources:
                        latest_resources.append(resource)
                
                latest_resources = sorted(latest_resources, key=lambda x: x.upload_date, reverse=True)[:5]
            
            # Add file type icons
            for resource in latest_resources:
                r = {
                    'id': resource.id,
                    'title': resource.title,
                    'file_type': self._get_file_type(resource.file.name)
                }
                
                # Add appropriate icon based on file type
                if 'pdf' in r['file_type'].lower():
                    r['icon'] = 'file-text'
                elif 'image' in r['file_type'].lower() or r['file_type'].lower() in ['jpg', 'png', 'gif']:
                    r['icon'] = 'image'
                elif 'video' in r['file_type'].lower() or r['file_type'].lower() in ['mp4', 'avi', 'mov']:
                    r['icon'] = 'video'
                elif 'audio' in r['file_type'].lower() or r['file_type'].lower() in ['mp3', 'wav']:
                    r['icon'] = 'music'
                elif r['file_type'].lower() in ['doc', 'docx']:
                    r['icon'] = 'file-text'
                elif r['file_type'].lower() in ['xls', 'xlsx']:
                    r['icon'] = 'table'
                elif r['file_type'].lower() in ['ppt', 'pptx']:
                    r['icon'] = 'presentation'
                else:
                    r['icon'] = 'file'
                    
                resources.append(r)
        except:
            pass
        
        return resources
    
    def _get_time_ago(self, date_time):
        """Helper method to format time ago from datetime"""
        now = timezone.now()
        
        # Handle both datetime objects and IDs
        if not isinstance(date_time, timezone.datetime):
            # Just a placeholder for demo - in a real app you'd use the correct timestamp
            import random
            days_ago = random.randint(0, 14)
            date_time = now - timedelta(days=days_ago, 
                                      hours=random.randint(0, 23), 
                                      minutes=random.randint(0, 59))
        
        diff = now - date_time
        
        if diff.days > 7:
            return date_time.strftime('%b %d, %Y')
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"

    def _parse_time_ago(self, time_ago_str):
        """Helper method to parse time ago string for sorting"""
        if 'Just now' in time_ago_str:
            return 0
        elif 'minute' in time_ago_str:
            return int(time_ago_str.split()[0]) * 60
        elif 'hour' in time_ago_str:
            return int(time_ago_str.split()[0]) * 3600
        elif 'day' in time_ago_str:
            return int(time_ago_str.split()[0]) * 86400
        else:
            # For dates in format "Feb 23, 2023"
            try:
                dt = datetime.strptime(time_ago_str, '%b %d, %Y')
                now = timezone.now()
                return (now - dt).total_seconds()
            except:
                return 999999999  # Very old
                
    def _get_file_type(self, filename):
        """Helper method to get file type from filename"""
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        if ext in ['pdf']:
            return 'PDF'
        elif ext in ['doc', 'docx']:
            return 'Document'
        elif ext in ['xls', 'xlsx']:
            return 'Spreadsheet'
        elif ext in ['ppt', 'pptx']:
            return 'Presentation'
        elif ext in ['jpg', 'jpeg', 'png', 'gif']:
            return 'Image'
        elif ext in ['mp4', 'avi', 'mov', 'webm']:
            return 'Video'
        elif ext in ['mp3', 'wav', 'ogg']:
            return 'Audio'
        else:
            return 'File'


class TeacherDashboardView(LoginRequiredMixin, TemplateView):
    """Teacher-specific dashboard view"""
    template_name = "dashboard_teacher.html"
    
    def get(self, request, *args, **kwargs):
        # Admin users can access all dashboards
        if request.user.is_superuser or request.user.is_staff:
            return super().get(request, *args, **kwargs)
            
        # Check if user has the is_teacher attribute and it's True
        if hasattr(request.user, 'is_teacher') and request.user.is_teacher:
            return super().get(request, *args, **kwargs)
        elif hasattr(request.user, 'is_student') and request.user.is_student:
            # Redirect students to student dashboard
            return redirect('dashboards:dashboard-student')
        else:
            # For users without defined roles, show general dashboard
            return redirect('dashboards:overview')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set dashboard type to ensure proper menu highlighting
        context['dashboard_type'] = 'teacher'
        
        # Set active menu attributes based on the JSON structure
        context['active_menu'] = 'dashboard'
        context['active_submenu'] = 'dashboard-teacher'
        
        now = timezone.now()
        user = self.request.user
        
        # Initialize data containers
        context['now'] = now
        
        # ===== Teacher Statistics =====
        # For admin users viewing the teacher dashboard, provide sample data
        if user.is_superuser or user.is_staff:
            if not hasattr(user, 'is_teacher') or not user.is_teacher:
                # Add a note that this is admin view
                context['admin_view'] = True
                
                # Provide some sample data or fetch data for all teachers
                try:
                    # Get teacher users
                    teacher_users = User.objects.filter(is_teacher=True)
                    
                    if teacher_users.exists():
                        # Use the first teacher's data for demonstration
                        sample_teacher = teacher_users.first()
                        context['viewing_as_teacher'] = sample_teacher.username
                        
                        # Set user to the sample teacher for data fetching
                        user = sample_teacher
                    else:
                        # No teachers in the system, provide defaults
                        context['course_count'] = 0
                        context['student_count'] = 0
                        context['upcoming_sessions'] = 0
                        context['teaching_hours'] = 0
                        context['course_analytics'] = []
                        context['student_activities'] = []
                        context['resources'] = []
                        context['weekly_schedule'] = []
                        return context
                except:
                    # Fallback to defaults if error occurs
                    context['course_count'] = 0
                    context['student_count'] = 0
                    context['upcoming_sessions'] = 0
                    context['teaching_hours'] = 0
                    context['course_analytics'] = []
                    context['student_activities'] = []
                    context['resources'] = []
                    context['weekly_schedule'] = []
                    return context
        
        # Get all courses taught by this teacher (or sample teacher for admin)
        taught_courses = Course.objects.filter(teacher=user)
        context['course_count'] = taught_courses.count()
        
        # Count students across all courses
        student_count = 0
        student_ids = set()
        for course in taught_courses:
            student_ids.update(course.students.values_list('id', flat=True))
        context['student_count'] = len(student_ids)
        
        # Get upcoming scheduled sessions
        upcoming_meetings = Meeting.objects.filter(
            teacher=user,
            start_time__gte=now
        ).order_by('start_time')
        context['upcoming_sessions'] = upcoming_meetings.count()
        context['upcoming_meetings'] = upcoming_meetings[:5]
        
        # Get teaching hours this month
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        completed_meetings = Meeting.objects.filter(
            teacher=user,
            start_time__gte=month_start,
            start_time__lt=now
        )
        teaching_hours = sum([meeting.duration for meeting in completed_meetings]) / 60.0
        context['teaching_hours'] = round(teaching_hours, 1)
        
        # ===== Course Analytics =====
        course_analytics = []
        
        for course in taught_courses:
            # Get student count
            student_count = course.students.count()
            
            # Get lesson count
            lesson_count = course.lessons.count()
            
            # Get completion rate
            completion_rate = 0
            if student_count > 0 and lesson_count > 0:
                completed_lessons = 0
                for student in course.students.all():
                    try:
                        progress = student.course_progress.get(course=course)
                        completed_lessons += progress.lessons_completed.count()
                    except:
                        pass
                
                max_possible = student_count * lesson_count
                completion_rate = (completed_lessons / max_possible) * 100 if max_possible > 0 else 0
            
            # Get quiz performance
            quiz_avg_score = 0
            quiz_count = Quiz.objects.filter(course=course).count()
            
            if quiz_count > 0:
                total_score = 0
                total_submissions = 0
                
                for quiz in Quiz.objects.filter(course=course):
                    for student in course.students.all():
                        try:
                            result = quiz.grade_quiz(student)
                            total_score += result['percentage']
                            total_submissions += 1
                        except:
                            pass
                
                quiz_avg_score = total_score / total_submissions if total_submissions > 0 else 0
            
            # Add to course analytics
            course_analytics.append({
                'id': course.id,
                'title': course.title,
                'student_count': student_count,
                'lesson_count': lesson_count,
                'completion_rate': round(completion_rate),
                'quiz_count': quiz_count,
                'quiz_avg_score': round(quiz_avg_score),
                'image': course.image if hasattr(course, 'image') else None
            })
        
        context['course_analytics'] = course_analytics
        
        # ===== Recent Student Activity =====
        student_activities = []
        
        # Get recent quiz submissions
        recent_quiz_submissions = Answer.objects.filter(
            question__quiz__course__teacher=user
        ).select_related('student', 'question__quiz').order_by('-id')[:10]
        
        for submission in recent_quiz_submissions:
            try:
                activity = {
                    'student_name': submission.student.username,
                    'student_id': submission.student.id,
                    'type': 'quiz',
                    'title': f"Submitted answer for {submission.question.quiz.title}",
                    'result': 'Correct' if submission.is_correct else 'Incorrect',
                    'time_ago': self._get_time_ago(submission.id), # Assuming Answer has created_at field
                    'color': 'success' if submission.is_correct else 'danger'
                }
                student_activities.append(activity)
            except:
                pass
        
        # Recent session attendance
        recent_sessions = Meeting.objects.filter(
            teacher=user,
            start_time__lt=now,
            start_time__gte=now - timedelta(days=14)
        ).order_by('-start_time')[:10]
        
        for session in recent_sessions:
            for student in session.students.all():
                try:
                    activity = {
                        'student_name': student.username,
                        'student_id': student.id,
                        'type': 'session',
                        'title': f"Attended {session.title}",
                        'result': 'Attended',
                        'time_ago': self._get_time_ago(session.start_time),
                        'color': 'primary'
                    }
                    student_activities.append(activity)
                except:
                    pass
        
        # Sort by recency
        student_activities.sort(key=lambda x: self._parse_time_ago(x['time_ago']))
        context['student_activities'] = student_activities[:6]
        
        # ===== Teaching Resources =====
        try:
            recent_resources = TeacherResource.objects.filter(
                teacher=user
            ).order_by('-upload_date')[:5]
            
            resources = []
            for resource in recent_resources:
                r = {
                    'id': resource.id,
                    'title': resource.title,
                    'file_type': self._get_file_type(resource.file.name),
                    'views': resource.access_logs.count(),
                    'upload_date': resource.upload_date
                }
                
                # Add appropriate icon based on file type
                if 'pdf' in r['file_type'].lower():
                    r['icon'] = 'file-text'
                elif 'image' in r['file_type'].lower() or r['file_type'].lower() in ['jpg', 'png', 'gif']:
                    r['icon'] = 'image'
                elif 'video' in r['file_type'].lower() or r['file_type'].lower() in ['mp4', 'avi', 'mov']:
                    r['icon'] = 'video'
                elif 'audio' in r['file_type'].lower() or r['file_type'].lower() in ['mp3', 'wav']:
                    r['icon'] = 'music'
                elif r['file_type'].lower() in ['doc', 'docx']:
                    r['icon'] = 'file-text'
                elif r['file_type'].lower() in ['xls', 'xlsx']:
                    r['icon'] = 'table'
                elif r['file_type'].lower() in ['ppt', 'pptx']:
                    r['icon'] = 'presentation'
                else:
                    r['icon'] = 'file'
                    
                resources.append(r)
            
            context['resources'] = resources
        except:
            context['resources'] = []
            
        # ===== Upcoming Schedule =====
        context['weekly_schedule'] = self._get_weekly_schedule(user, now)
        
        return context
    
    def _get_weekly_schedule(self, user, now):
        """Get the teacher's weekly schedule"""
        # Start from beginning of current week (Monday)
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        
        # Get all meetings for this week
        weekly_meetings = Meeting.objects.filter(
            teacher=user,
            start_time__gte=week_start,
            start_time__lt=week_end
        ).order_by('start_time')
        
        # Organize by day
        schedule = []
        for day_idx in range(7):
            day_date = week_start + timedelta(days=day_idx)
            day_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][day_idx]
            
            day_meetings = []
            for meeting in weekly_meetings:
                if meeting.start_time.date() == day_date.date():
                    day_meetings.append({
                        'id': meeting.id,
                        'title': meeting.title,
                        'start_time': meeting.start_time.strftime('%H:%M'),
                        'duration': meeting.duration,
                        'student_count': meeting.students.count()
                    })
            
            schedule.append({
                'day_name': day_name,
                'date': day_date.strftime('%b %d'),
                'is_today': day_date.date() == now.date(),
                'meetings': day_meetings
            })
        
        return schedule
    
    def _get_time_ago(self, date_time):
        """Helper method to format time ago from datetime"""
        now = timezone.now()
        
        # Handle both datetime objects and IDs
        if not isinstance(date_time, timezone.datetime):
            # Just a placeholder for demo - in a real app you'd use the correct timestamp
            import random
            days_ago = random.randint(0, 14)
            date_time = now - timedelta(days=days_ago, 
                                      hours=random.randint(0, 23), 
                                      minutes=random.randint(0, 59))
        
        diff = now - date_time
        
        if diff.days > 7:
            return date_time.strftime('%b %d, %Y')
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"

    def _parse_time_ago(self, time_ago_str):
        """Helper method to parse time ago string for sorting"""
        if 'Just now' in time_ago_str:
            return 0
        elif 'minute' in time_ago_str:
            return int(time_ago_str.split()[0]) * 60
        elif 'hour' in time_ago_str:
            return int(time_ago_str.split()[0]) * 3600
        elif 'day' in time_ago_str:
            return int(time_ago_str.split()[0]) * 86400
        else:
            # For dates in format "Feb 23, 2023"
            try:
                dt = datetime.strptime(time_ago_str, '%b %d, %Y')
                now = timezone.now()
                return (now - dt).total_seconds()
            except:
                return 999999999  # Very old
                
    def _get_file_type(self, filename):
        """Helper method to get file type from filename"""
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        if ext in ['pdf']:
            return 'PDF'
        elif ext in ['doc', 'docx']:
            return 'Document'
        elif ext in ['xls', 'xlsx']:
            return 'Spreadsheet'
        elif ext in ['ppt', 'pptx']:
            return 'Presentation'
        elif ext in ['jpg', 'jpeg', 'png', 'gif']:
            return 'Image'
        elif ext in ['mp4', 'avi', 'mov', 'webm']:
            return 'Video'
        elif ext in ['mp3', 'wav', 'ogg']:
            return 'Audio'
        else:
            return 'File'

class StudentDashboardView(LoginRequiredMixin, TemplateView):
    """Student-specific dashboard view"""
    template_name = "dashboard_student.html"
    
    def get(self, request, *args, **kwargs):
        # Admin users can access all dashboards
        if request.user.is_superuser or request.user.is_staff:
            return super().get(request, *args, **kwargs)
            
        # Check if user has the is_student attribute and it's True
        if hasattr(request.user, 'is_student') and request.user.is_student:
            return super().get(request, *args, **kwargs)
        elif hasattr(request.user, 'is_teacher') and request.user.is_teacher:
            # Redirect teachers to teacher dashboard
            return redirect('dashboards:dashboard-teacher')
        else:
            # For users without defined roles, show general dashboard
            return redirect('dashboards:overview')
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set dashboard type to ensure proper menu highlighting
        context['dashboard_type'] = 'student'
        
        # Set active menu attributes based on the JSON structure
        context['active_menu'] = 'dashboard'
        context['active_submenu'] = 'dashboard-student'
        
        now = timezone.now()
        user = self.request.user
        
        # For admin users viewing the student dashboard, provide sample data
        if user.is_superuser or user.is_staff:
            if not hasattr(user, 'is_student') or not user.is_student:
                # Add a note that this is admin view
                context['admin_view'] = True
                
                # Provide some sample data or fetch data for a sample student
                try:
                    # Get student users
                    student_users = User.objects.filter(is_student=True)
                    
                    if student_users.exists():
                        # Use the first student's data for demonstration
                        sample_student = student_users.first()
                        context['viewing_as_student'] = sample_student.username
                        
                        # Set user to the sample student for data fetching
                        user = sample_student
                    else:
                        # No students in the system, provide defaults
                        context['enrolled_courses'] = 0
                        context['completed_lessons'] = 0
                        context['credit_balance'] = 0
                        context['avg_score'] = 0
                        context['course_progress'] = []
                        context['upcoming_meetings'] = []
                        context['assessment_results'] = []
                        context['resources'] = []
                        context['student_files'] = []
                        return context
                except:
                    # Fallback to defaults if error occurs
                    context['enrolled_courses'] = 0
                    context['completed_lessons'] = 0
                    context['credit_balance'] = 0
                    context['avg_score'] = 0
                    context['course_progress'] = []
                    context['upcoming_meetings'] = []
                    context['assessment_results'] = []
                    context['resources'] = []
                    context['student_files'] = []
                    return context
        
        # Initialize data containers
        context['now'] = now
        
        # ===== Student Statistics =====
        # Enrolled courses
        enrolled_courses = user.enrolled_courses.all()
        context['enrolled_courses'] = enrolled_courses.count()
        
        # Count completed lessons
        completed_lessons = 0
        for course in enrolled_courses:
            # This assumes you're tracking progress in your models
            try:
                progress = user.course_progress.get(course=course)
                completed_lessons += progress.lessons_completed.count()
            except:
                # If no progress model exists
                pass
        context['completed_lessons'] = completed_lessons
        
        # Get credit balance
        credit_balance = 0
        if CreditTransaction.objects.filter(student=user).exists():
            try:
                last_transaction = CreditTransaction.objects.filter(student=user).latest('created_at')
                credit_balance = last_transaction.get_balance()
            except:
                pass
        context['credit_balance'] = credit_balance
        
        # Get average assessment score
        try:
            total_answers = Answer.objects.filter(student=user).count()
            if total_answers > 0:
                correct_answers = Answer.objects.filter(student=user, is_correct=True).count()
                avg_score = (correct_answers / total_answers) * 100
                context['avg_score'] = round(avg_score)
            else:
                context['avg_score'] = 0
        except:
            context['avg_score'] = 0
        
        # ===== Learning Progress =====
        course_progress = []
        
        for course in enrolled_courses:
            total_lessons = course.lessons.count()
            completed = 0
            
            try:
                progress = user.course_progress.get(course=course)
                completed = progress.lessons_completed.count()
            except:
                pass
                
            progress_pct = (completed / max(total_lessons, 1)) * 100
            
            # Get next lesson to complete
            next_lesson = None
            if completed < total_lessons:
                try:
                    completed_ids = progress.lessons_completed.values_list('id', flat=True)
                    next_lesson = course.lessons.exclude(id__in=completed_ids).order_by('order').first()
                except:
                    pass
            
            # Get course teacher name
            teacher_name = course.teacher.username if course.teacher else "Unknown Teacher"
            
            course_data = {
                'id': course.id,
                'title': course.title,
                'teacher': teacher_name,
                'lessons_count': total_lessons,
                'progress': round(progress_pct),
                'completed_lessons': completed,
                'next_lesson': next_lesson,
                'image': course.image if hasattr(course, 'image') else None
            }
            course_progress.append(course_data)
        
        context['course_progress'] = course_progress
        
        # ===== Upcoming Sessions =====
        # Get all upcoming booked sessions
        upcoming_meetings = Meeting.objects.filter(
            students=user,
            start_time__gte=now
        ).order_by('start_time')
        context['upcoming_meetings'] = upcoming_meetings[:5]
        
        # ===== Available Credit Hours =====
        # Calculate how many session hours the student can book with current credits
        bookable_hours = 0
        # Assuming 1 credit = 1 hour session, adjust as needed
        if credit_balance > 0:
            bookable_hours = credit_balance
        context['bookable_hours'] = bookable_hours
        
        # ===== Recent Assessment Results =====
        assessment_results = []
        
        try:
            recent_answers = Answer.objects.filter(
                student=user
            ).select_related('question__quiz').order_by('-id')
            
            # Group by quiz
            quiz_results = {}
            for answer in recent_answers:
                quiz_id = answer.question.quiz.id
                if quiz_id not in quiz_results:
                    quiz_results[quiz_id] = {
                        'quiz': answer.question.quiz,
                        'total_questions': 0,
                        'correct_answers': 0,
                        'latest_attempt': answer.id,  # Using ID instead of timestamp for demo
                        'course': answer.question.quiz.course
                    }
                
                quiz_results[quiz_id]['total_questions'] += 1
                if answer.is_correct:
                    quiz_results[quiz_id]['correct_answers'] += 1
            
            # Convert to list and calculate percentages
            for result in quiz_results.values():
                score = (result['correct_answers'] / result['total_questions']) * 100 if result['total_questions'] > 0 else 0
                
                assessment_results.append({
                    'quiz_id': result['quiz'].id,
                    'title': result['quiz'].title,
                    'course_id': result['course'].id if result['course'] else None,
                    'course_title': result['course'].title if result['course'] else "N/A",
                    'score': round(score),
                    'total_questions': result['total_questions'],
                    'correct_answers': result['correct_answers'],
                    'time_ago': self._get_time_ago(result['latest_attempt'])
                })
        except:
            pass
        
        # Sort by recency
        assessment_results.sort(key=lambda x: self._parse_time_ago(x['time_ago']))
        context['assessment_results'] = assessment_results[:3]
        
        # ===== Learning Resources =====
        resources = []
        
        try:
            # Get resources the student has access to
            accessible_resources = user.accessible_resources.all()
            
            # Also include resources from enrolled courses
            course_resources = TeacherResource.objects.filter(
                course__in=user.enrolled_courses.all(),
                is_public=True
            )
            
            # Combine and sort
            latest_resources = list(accessible_resources)
            for resource in course_resources:
                if resource not in latest_resources:
                    latest_resources.append(resource)
            
            latest_resources = sorted(latest_resources, key=lambda x: x.upload_date, reverse=True)[:5]
            
            # Add file type icons
            for resource in latest_resources:
                r = {
                    'id': resource.id,
                    'title': resource.title,
                    'file_type': self._get_file_type(resource.file.name),
                    'course_title': resource.course.title if resource.course else "N/A",
                    'teacher': resource.teacher.username
                }
                
                # Add appropriate icon based on file type
                if 'pdf' in r['file_type'].lower():
                    r['icon'] = 'file-text'
                elif 'image' in r['file_type'].lower() or r['file_type'].lower() in ['jpg', 'png', 'gif']:
                    r['icon'] = 'image'
                elif 'video' in r['file_type'].lower() or r['file_type'].lower() in ['mp4', 'avi', 'mov']:
                    r['icon'] = 'video'
                elif 'audio' in r['file_type'].lower() or r['file_type'].lower() in ['mp3', 'wav']:
                    r['icon'] = 'music'
                elif r['file_type'].lower() in ['doc', 'docx']:
                    r['icon'] = 'file-text'
                elif r['file_type'].lower() in ['xls', 'xlsx']:
                    r['icon'] = 'table'
                elif r['file_type'].lower() in ['ppt', 'pptx']:
                    r['icon'] = 'presentation'
                else:
                    r['icon'] = 'file'
                    
                resources.append(r)
        except:
            pass
        
        context['resources'] = resources
        
        # ===== Learning Activity Chart =====
        # Generate weekly activity data (placeholder - would be based on real tracking)
        weekly_hours = []
        for day in range(7):
            day_date = now - timedelta(days=now.weekday()) + timedelta(days=day)
            
            # In a real app, you'd query an activity tracking model
            # For demo, generate some reasonable random data
            import random
            # Learning hours per day (just for demo - would be tracked in real app)
            hours = random.uniform(0.5, 3.0) if day < 5 else random.uniform(0, 1.5)
                
            weekly_hours.append(round(hours, 1))
        
        context['weekly_hours'] = weekly_hours
        
        # Calculate total stats
        context['total_hours'] = round(sum(weekly_hours))
        context['total_completed'] = completed_lessons
        
        try:
            context['assessments_taken'] = Answer.objects.filter(student=user).values('question__quiz').distinct().count()
            context['total_sessions'] = Meeting.objects.filter(students=user).count()
        except:
            context['assessments_taken'] = 0
            context['total_sessions'] = 0
        
        # ===== Available Booking Slots =====
        available_slots = []
        
        try:
            # Get available booking slots for the next 7 days
            next_week = now + timedelta(days=7)
            booking_slots = BookingSlot.objects.filter(
                status='available',
                start_time__gte=now,
                start_time__lt=next_week
            ).order_by('start_time')[:5]
            
            for slot in booking_slots:
                available_slots.append({
                    'id': slot.id,
                    'teacher': slot.teacher.username,
                    'date': slot.start_time.strftime('%b %d'),
                    'time': slot.start_time.strftime('%I:%M %p'),
                    'duration': slot.duration,
                    'day_of_week': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][slot.start_time.weekday()]
                })
        except:
            pass
        
        context['available_slots'] = available_slots
        
        
        # ===== Student Files =====
        student_files = []
        
        try:
            recent_files = StudentFile.objects.filter(
                student=user
            ).order_by('-upload_date')[:5]
            
            for file in recent_files:
                f = {
                    'id': file.id,
                    'title': file.title,
                    'file_type': self._get_file_type(file.file.name),
                    'upload_date': file.upload_date,
                    'course_title': file.course.title if file.course else "Personal",
                    'view_count': file.view_count
                }
                
                # Add appropriate icon based on file type
                if 'pdf' in f['file_type'].lower():
                    f['icon'] = 'file-text'
                elif 'image' in f['file_type'].lower() or f['file_type'].lower() in ['jpg', 'png', 'gif']:
                    f['icon'] = 'image'
                elif 'video' in f['file_type'].lower() or f['file_type'].lower() in ['mp4', 'avi', 'mov']:
                    f['icon'] = 'video'
                elif 'audio' in f['file_type'].lower() or f['file_type'].lower() in ['mp3', 'wav']:
                    f['icon'] = 'music'
                elif f['file_type'].lower() in ['doc', 'docx']:
                    f['icon'] = 'file-text'
                elif f['file_type'].lower() in ['xls', 'xlsx']:
                    f['icon'] = 'table'
                elif f['file_type'].lower() in ['ppt', 'pptx']:
                    f['icon'] = 'presentation'
                else:
                    f['icon'] = 'file'
                    
                student_files.append(f)
        except:
            pass
        
        context['student_files'] = student_files
        
        # ===== Learning Recommendations =====
        # Recommend courses based on current enrollment and progress
        recommended_courses = []
        
        try:
            # Find courses the student isn't enrolled in
            all_courses = Course.objects.exclude(id__in=enrolled_courses.values_list('id', flat=True))
            
            # Simple recommendation based on course categories or topics
            # In a real app, you'd use more sophisticated recommendation algorithms
            
            # Get categories/subjects the student is currently learning
            student_subjects = set()
            for course in enrolled_courses:
                # This assumes courses have a 'category' or similar field
                if hasattr(course, 'category'):
                    student_subjects.add(course.category)
            
            # Find courses in similar categories
            for course in all_courses:
                is_recommended = False
                
                # Check if course is in a subject the student is studying
                if hasattr(course, 'category') and course.category in student_subjects:
                    is_recommended = True
                
                # Check if taught by a teacher whose course the student is already taking
                if course.teacher.id in enrolled_courses.values_list('teacher', flat=True):
                    is_recommended = True
                
                if is_recommended:
                    recommended_courses.append({
                        'id': course.id,
                        'title': course.title,
                        'teacher': course.teacher.username,
                        'description': course.description[:100] + '...' if len(course.description) > 100 else course.description,
                        'image': course.image if hasattr(course, 'image') else None
                    })
                
                # Limit to 3 recommendations
                if len(recommended_courses) >= 3:
                    break
        except:
            pass
        
        context['recommended_courses'] = recommended_courses
        
        return context
    
    def _get_time_ago(self, date_time):
        """Helper method to format time ago from datetime"""
        now = timezone.now()
        
        # Handle both datetime objects and IDs
        if not isinstance(date_time, timezone.datetime):
            # Just a placeholder for demo - in a real app you'd use the correct timestamp
            import random
            days_ago = random.randint(0, 14)
            date_time = now - timedelta(days=days_ago, 
                                      hours=random.randint(0, 23), 
                                      minutes=random.randint(0, 59))
        
        diff = now - date_time
        
        if diff.days > 7:
            return date_time.strftime('%b %d, %Y')
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"

    def _parse_time_ago(self, time_ago_str):
        """Helper method to parse time ago string for sorting"""
        if 'Just now' in time_ago_str:
            return 0
        elif 'minute' in time_ago_str:
            return int(time_ago_str.split()[0]) * 60
        elif 'hour' in time_ago_str:
            return int(time_ago_str.split()[0]) * 3600
        elif 'day' in time_ago_str:
            return int(time_ago_str.split()[0]) * 86400
        else:
            # For dates in format "Feb 23, 2023"
            try:
                dt = datetime.strptime(time_ago_str, '%b %d, %Y')
                now = timezone.now()
                return (now - dt).total_seconds()
            except:
                return 999999999  # Very old
                
    def _get_file_type(self, filename):
        """Helper method to get file type from filename"""
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        if ext in ['pdf']:
            return 'PDF'
        elif ext in ['doc', 'docx']:
            return 'Document'
        elif ext in ['xls', 'xlsx']:
            return 'Spreadsheet'
        elif ext in ['ppt', 'pptx']:
            return 'Presentation'
        elif ext in ['jpg', 'jpeg', 'png', 'gif']:
            return 'Image'
        elif ext in ['mp4', 'avi', 'mov', 'webm']:
            return 'Video'
        elif ext in ['mp3', 'wav', 'ogg']:
            return 'Audio'
        else:
            return 'File'