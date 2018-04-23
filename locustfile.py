"""
Load testing script.

Run via:

$ locust

Then visit http://localhost:8089 on host to run a test via the web UI.
"""
from locust import HttpLocust, TaskSet, task
from hashlib import sha1
from random import randint

HOST = "http://localhost:8080"

# NOTE: Change this based on your test user & plan
USERNAME = 'testuser'
PASSWORD = 'Test123$'
PLAN_ID = 5

# Configuration/instance specific. Assumes PA instance.
NUM_DISTRICTS_IN_PLAN = 18
REASSIGNMENT_POST_DATA = {
    'geolevel': 2,
    'geounits': 731,
    'version': 0,
}


class UserActions(TaskSet):
    def on_start(self):
        self.login()

    def login(self):
        get_response = self.client.get('/accounts/login/')
        csrftoken = get_response.cookies['csrftoken']
        # Connection is unencrypted so the password is hashed before being sent
        # to backend.
        hashed_password = sha1(PASSWORD.encode('utf-8')).hexdigest()
        # NOTE: Cookies are stored in client object
        redirect_url = '/districtmapping/plan/{plan_id}/edit/'.format(
            plan_id=PLAN_ID)
        with self.client.post(
                '/accounts/login/', {
                    'username': USERNAME,
                    'password': hashed_password,
                    'next': redirect_url,
                },
                headers={'X-CSRFToken': csrftoken},
                catch_response=True) as post_response:
            if post_response.url != HOST + redirect_url:
                post_response.failure('Authentication failed')

    @task(1)
    def index(self):
        self.client.get('/')

    @task(2)
    def plan(self):
        self.client.get(
            '/districtmapping/plan/{plan_id}/edit/'.format(plan_id=PLAN_ID))

    @task(10)
    def reassign(self):
        get_response = self.client.get(
            '/districtmapping/plan/{plan_id}/edit/'.format(plan_id=PLAN_ID))
        csrftoken = get_response.cookies['csrftoken']
        # Reassign geounit to random district
        with self.client.post(
                '/districtmapping/plan/{plan_id}/district/{new_district}/add/'.
                format(
                    plan_id=PLAN_ID,
                    new_district=randint(1, NUM_DISTRICTS_IN_PLAN),
                ),
                REASSIGNMENT_POST_DATA,
                name=
                '/districtmapping/plan/{plan_id}/district/[new_district]/add/'.
                format(plan_id=PLAN_ID),
                headers={'X-CSRFToken': csrftoken},
                catch_response=True,
                allow_redirects=False) as post_response:
            # NOTE: If authentication has not worked properly, you will be
            # redirected to the home page
            if post_response.status_code == 302:
                post_response.failure(
                    'User was not authenticated to perform reassignment and was redirected to login page'
                )
            else:
                if not post_response.json()['success']:
                    post_response.failure('Failed to reassign geounit')


class ApplicationUser(HttpLocust):
    task_set = UserActions
    host = HOST
    min_wait = 0
    max_wait = 0
