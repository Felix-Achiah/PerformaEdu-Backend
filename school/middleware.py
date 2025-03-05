from django.http import Http404
from .models import School
from threading import local

_thread_locals = local()

def get_current_school():
    return getattr(_thread_locals, 'school', None)

class SubdomainMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]  # Remove port if present
        domain_parts = host.split('.')
        
        if len(domain_parts) > 2:  # e.g., schoolname.maindomain.com
            subdomain = domain_parts[0]
            try:
                school = School.objects.get(subdomain=subdomain)
                _thread_locals.school = school
            except School.DoesNotExist:
                raise Http404("School not found for this subdomain")
        else:
            _thread_locals.school = None  # Main domain (e.g., maindomain.com)

        response = self.get_response(request)
        return response