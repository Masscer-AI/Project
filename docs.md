<style>
    body {
        color: #bebebe;
    }
    .blue {
        color: #1e8a9b;
        font-weight: bold;
    }
    .title {
        background: #000;
        display: block;
        text-align: center;
        padding: 5px
    }
    .rose {
        color: #f6005a;
        font-weight: bold;
    }
    .white {
        color: #fff;
        font-weight: bold;
    }
    .center {
        text-align: center;
        display: block;
    }
</style>

# <span class="blue title">Building a Django API</span>

## <span class="white center">Setting the environment</span>

## <span class="rose">**Install Python**</span>
The first thing to keep in mind is that Django works with Python, for that reason it is necessary to have Python in the computer.
> Remember to mark the option <span class="rose">add to path</span>
***
## <span class="rose">**Create a new directory for the project**</span>
To create a new directory, go to the command line and paste the command:
```
mkdir <directory-name>
```
Where **directory-name** is how you want to name the folder where the project is in.
***
## <span class="rose">**Init a virtual environment**</span>
To initialize a new virtual environment in Python, go to the directory previusly created and open the CLI (Command Line Interface) and run the command:
```
py -m venv venv  
```
A new directory called venv will be created in the directory.
***
## <span class="rose">**Get inside the venv**</span>
To get inside the venv you need to run another command, this command will ensure you're installing all modules inside the environment
```
venv\Scripts\activate
```
Run it in Powershell
## <span class="rose">**Install Django**</span>
To install Django it is as simple as run a command in the current directory
```
pip install django 
```
Once installed, you can check if all is correct running 
```
django-admin --version
```
It will shows you the django-admin version.

## <span class="white center">Initializing empty project</span>
Now that we have completed the setting of the environment, we need to start our project with Django.

## <span class="rose">**Init project**</span>
In django, we have a command to start a new project, it is so simple, you just need to be in the current directory and run:
```
django-admin startproject <project-name> .
```
Change **project-name** with the desired project-name.
The point is to tell django to install the required files in the current directory.

## <span class="rose">**Init app**</span>
Now that we have a project, we need to add modules to that project, in django, that modules are called app, for example, an app can manage the authentication of the users, another app to manage a part of the project, and in that way we can have all our project in different modules. To start a new app, run:
```
python manage.py startapp <app-name>
```
This will create a new app in the current directory, but it is more easy to read if we have our app inside the project, for that reason, just move the **app** inside the **project** folder
```
mv app-name/ project/
```
Now, we need to change the name in **project/app/apps.AuthConfig.name** from **app** to **project.app** depending of the name of the project and app, in this example:
```
class AuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.authenticate'
```

## <span class="rose">**Register app**</span>
To register the app in the project, we need to add it in settings.py.INSTALLED_APPS, for our example:
```
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'api.authenticate'
]
```
## <span class="rose">**Time to test if everything is correct**</span>
Run the command to up the project:
```
python manage.py runserver
```
Go to the browser in the localhost:8000m and you'll see a sample app running. But in the terminar there is an error that tells <span class="rose">You have 18 unapplied migration(s).</span>, maybe the number could be different. 

That error is caused because we need <span class="rose"> to run the migrations</span>. Run the command:

```
python manage.py migrate
```
## <span class="white center">Adding the first view</span>
In Python, we work under the arquitecture **MVT (Model, View, Template)**, where the Model is the instance in the DB (Database), the view is the function that run in a certain route, and the template is the HTML template that is shown in that route.
Keeping that in mind, the first thing we need to add in Python, is a view, just to testing, and starting to work.
I'll add a view just to say "Hello, world" to the visitor of the route.

## <span class="rose">Define the view</span>
In the app, there're a lot of files that comes with it, open views.py and add the following code:
```
from django.http import HttpResponse

def say_hello_world(request):
    return HttpResponse("Hello, world")
```
Now run the server and go to the port 8000. Notice that nothing is happening, that is because we need to register our views first.

## <span class="rose">Register the view</span>
To register the view we need to go to project/urls.py and open the file. Add the following code: 
```
from .authenticate.views import say_hello_world
urlpatterns = [
    path('admin/', admin.site.urls),
    path('hello/', say_hello_world, name="Hello")
]
```
We are importing the view, and adding a new path in the urlpatterns. The path receives three arguments: the route we want to assing to the view, the view itself, and a name that is an indetifier to the the view.

Now go to <span class="rose">localhost:8000/hello/</span> and see the magic.

## <span class="rose">Refactoring to be pro</span>
To be a pro, one of the possible things to do is import the urls from each app and assign a routes for each one.
In this case, we will to to that.
First, in project.urls, add:
```
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings


apps = [
    ('auth/', 'api.authenticate.urls', 'auth'),
]

urlpatterns_apps = [path(url, include(urlconf, namespace=namespace)) for url, urlconf, namespace in apps]

urlpatterns_django = [
    path('admin/', admin.site.urls),
]

urlpatterns_static = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns = (urlpatterns_apps + urlpatterns_django + urlpatterns_static)
```
and in each app.urls add:
```
from django.urls import path
from .views import say_hello_world

app_name = 'finetuning'

urlpatterns = [
    path('hello/', say_hello_world, name='hello'),
]
```
Depending of the app name and the views and urls you want for the app
## <span class="rose">Run again the project</span>
```
python manage.py runserver
```
And you will see how you have now routes for each app, and the routes are well distribuited.

## <span class="white center">Start to add models to the db</span>
## <span class="rose">Add a single model</span>
To add a model in Django, we have the models.py file inside each app, and we have prebuild models as the User model. Now we will add a new model to the blog app:
```
from django.contrib.auth.models import User
# Create your models here.

class Post(models.Model):
    title = models.CharField(max_length=100, default=None)
    url = models.CharField(max_length=200, default=None, null=True, blank=True)
    text = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now_add=True, editable=True)
    status = models.CharField(max_length=9, choices=TRIVIA_STATUS, default=DRAFT)
    
    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        super(Post, self).save(*args, **kwargs)

```
## <span class="rose">After adding a model, is needed to migrate</span>
First run the command:
```
python manage.py makemigrations
```
Maybe an action will be required depending of the changes or errors.
Later, run the migrations:
```
python manage.py migrate
```

## <span class="white center">Saving the project in a Github repository</span>
## <span class="rose">Init the git repository</span>
```
git init
```
## <span class="rose">Add the remote</span>
```
git remote add <remote-name> <remote-url>
```
**remote-name** use to be named <span class="rose">**origin**</span> and the **remote-url** is the url of the Github repository.
If everything is correct when you run the command
```
git remote -v
```
You will see your Github repository url for fetch and push.
## <span class="rose">Ignore the modules</span>
Add a file .gitignore to ignore the modules and make our repository more easy to share.
```
touch .gitignore
```
A .gitignore file will be added to the directory, enter in the file with
```
code .gitignore
```
And at the following line:
```
#.gitignore

venv/
```
## <span class="rose">Add the changes to be stage</span>
Add all the files of our application with
```
git add .
```
## <span class="rose">Commit the changes</span>
Commit the changes that you'll be adding  to the remote repository and leave a message
```
git commit -m "a message with the changes you made"
```
## <span class="rose">Finally, upload the changes</span>
The moment of truth, upload the changes to Github
```
git push origin <branch>
```
where **branch** is the name of the current branch or the branch you want to upload the changes, in this case, the branch is <span class="rose">main<span>

## <span class="rose">That's all</span>
if everything was well, check your Github repository and you'll have the latest commit there.


## <span class="white center">Deploying to Render.com</span>
[Documentation here](https://render.com/docs/deploy-django#update-your-app-for-render)

## <span class="rose">Set the secret key</span>
Go to settings.py and add:
```

import os

SECRET_KEY = os.environ.get('SECRET_KEY', default='your secret key')
```
## <span class="rose">Turn off DEBUG if is in production</span>
Always in settings.py
```
DEBUG = 'RENDER' not in os.environ
```
## <span class="rose">Add the ALLOWED_HOST</span>
```
ALLOWED_HOSTS = []

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:    
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
```
## <span class="rose">Install the package to add PostgreSQL database</span>
In the CLI:
```
pip install dj-database-url psycopg2-binary
```

## <span class="rose">Import the package in settings.py</span>
```
import dj_database_url
```
## <span class="rose">Add DATABASE config</span>
```
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',        
        conn_max_age=600    )
    }
```

## <span class="rose">Install whitenoise</span>
In the CLI:
```
pip install whitenoise[brotli]
```
## <span class="rose">Add the whitenoise middleware</span>
In settings.py, add the middleware after SecurityMiddleware
```
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',    ...
]
```
## <span class="rose">Add the settings to the static files</span>
In settings.py
```
STATIC_URL = '/static/'

if not DEBUG:
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```
## <span class="rose">Install gunicorn</span>
In the bash command line:
```
pip install gunicorn
```

## <span class="rose">Freeze the modules to install</span>
```
pip freeze > requirements.txt
```


## <span class="rose">Create build.sh file</span>
```
touch build.sh
```

## <span class="rose">Add the necessary scripts to run</span>

```
#!/usr/bin/env bash
# exit on error

set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
```


## <span class="rose">Give permissions to the build.sh</span>
In the bash command line:
```
chmod a+x build.sh
```

## <span class="rose">Deployment config</span>
In Render.com, when you are deploying, add the necessary configuration
- **.env variables**
  ```
  PYTHON_VERSION=
  DATABASE_URL=
  SECRET_KEY=
  EXTERNAL_HOSTNAME=
  RENDER*
  ```
  * *RENDER is added automatically by Render.
- Build command:
  ```
  ./build.sh
  ```
