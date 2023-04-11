# CAD Challenges
A web app that hosts CAD modelling problems for self-paced learning in Onshape. Previously named the "CAD Learner". 

- [Daily maintenance and use](#daily-maintenance-and-use)
    - [Add new questions to the database](#add-new-questions-to-database)
    - [Add reviewer to the app](#add-reviewer-to-the-app)
    - [Local launch of the app](#local-launch-of-the-app)
    - [Local development](#local-development)
    - [Manually modify database](#manually-modify-database)
- [First time setup](#first-time-setup)

## Daily maintenance and use 

### Add new questions to database 

See instructions on Wiki page [Quesiton Preperation Guide](https://github.com/PTC-Education/cad-learner/wiki/Question-Preparation-Guide) and add questions through the admin portal of the app (`base_url/admin/`). It also works the same way for localhost database. 

### Add reviewer to the app 

See instructions on Wiki page [User Management Guide](https://github.com/PTC-Education/cad-learner/wiki/User-Management-Guide) and assign reviewers through the admin portal of the app. It also works the same way for localhost database. 

### Local launch of the app 

1. Make sure you are in the virtual environment of the repository. I.e., you should see `(venv) (base) User@usercomputer` at the beginning of your command line. Otherwise, start the environment by running the command `source venv/bin/activate`. 
2. If you started a new terminal session, add configuration variables to your virtual environment by running the following commands: 
    - `export OAUTH_URL=https://oauth.onshape.com`
    - `export OAUTH_CLIENT_ID=xxxxxxxxxxxx`
    - `export OAUTH_CLIENT_SECRET=xxxxxxxxxxxxxxxxx`
3. Double check if uninstalled packages are used by the app, and install them if any, with the command `pip install -r requirements.txt`. 
4. Make sure you migrate any new changes to your local database with the command `python3 manage.py migrate`. 
5. Launch the web with command `python3 manage.py runserver`. 
6. Open a new terminal and launch your local redis library for background job queue with command `redis-server`. 
7. Open a third terminal window and complete step 1 and 2 again in the new terminal window. Then, launch the web worker with command `python3 manage.py rqworker high default low`. 
8. Make sure you have three terminals running steps 5 - 8, respectively. Once finished with local testing, you can quit all of them with `ctrl` + `C`. 

### Local development 

If changes are made to the fields of any Django models (typically changes made to the attributes in classes in any one of the `models.py` files), you need to create new migration files to initiate updates to the database. If unsure, always run step 1 below. 

1. First run `python3 manage.py makemigrations` to scan if any changes are made. 
2. If changes are detected, new migration files are automatically created. Run `python3 manage.py migrate` to apply those new changes to your local database. 
3. No changes are required for the cloud database, as automatic actions are already specified in the `Procfile`. 

If new Python packages are installed and used for the app, make sure it is recorded in the `requirements.txt`, so the cloud version also has access to the library. 

1. First run `pip install xxx` in the virtual environment, so that the package is installed locally. 
2. Run `pip freeze > requirements.txt` to update the requirement file. 

If unnecessary or unused packages are installed or added to the `requirements.txt`, you should uninstall the packages to keep the cloud repository as light-weight as possible. 

1. First run `pip uninstall xxx` in the virtual environment to uninstall the package. 
2. Run `pip freeze > requirements.txt` to update the requirement file. 

When new packages are used by other contributors and added to the `requirements.txt`, or when packages are upgraded to newer versions, you may want to update/upgrade your local development environment: 

1. Make sure you pull the updated changes to your local development environment. 
2. In the virtual environment, run `pip install -r requirements.txt` to install all the packages (and versions) specified in the `requirements.txt` file. Packages that are already installed (and up-to-date) will not be installed with duplicates. 
    - For security reasons, you may sometimes need to add `--trusted-host pypi.org --trusted-host files.pythonhosted.org` to the end of the command above. 

### Manually modify database 

While changes to some fields and entries of the database are locked or forbidden through the user interface of the app, changes can be made manually through the shell. This can be done for both the local database and the database in the cloud. However, this should be done with extra caution! 

1. Launch the shell in the terminal with command 
    - `python3 manage.py shell` for local database 
    - `heroku run python manage.py shell` for Heroku cloud database 
2. Now you should see `>>>` at the front of the next available command line, and any Python codes you commit will be applied to the database. 

Example of how you would update an entry: 

1. Open the database in one window with the data table you would to modify opened. 
2. Import the Django model that the data belongs to: e.g., `from questioner.models import Question_SPPS`
3. Query for the entry (row) of the data (more documentation can be found [here](https://docs.djangoproject.com/en/4.1/topics/db/queries/)): e.g., `q = Question_SPPS.objects.get(question_id=3)`
4. Make the changes you would like to make to the data: e.g., `q.completion_feature_cnt = [10,2,4,10,20,3]` 
5. Make sure the changes are saved to the database, otherwise all changes will be discarded. E.g., `q.save()`
6. Quit the shell when finished: `quit()`

## First time setup 

Follow the instructions below for first time local setup for testing and development: 

1. Git clone this repository to your local directory and open the repository in a local IDE, where Python needs to be available and supported. 
2. Make sure you have `HomeBrew` installed, instructions to install can be found [here](https://brew.sh). 
3. Install the `Postgres.app` [here](https://postgresapp.com) to enable PostgreSQL in your computer. After installation, open the app and initiate the database. Try running `which psql` in a terminal to check if installation is successful. 
4. Install Redis [here](https://redis.io/docs/getting-started/installation/install-redis-on-mac-os/) locally to allow background job queue. After installation, try running `redis-server` to start the server as a check of successful installation. 
5. Create a local virtual environment in your repository by running the command `python3 -m venv venv` in a terminal window. 
6. Switch into the created virtual environment with command `source venv/bin/activate`. 
7. Download all required packages in the virtual environment `pip install -r requirements.txt`. 
8. Migrate all migration files in the repository to set up your local database for the app with command `python3 manage.py migrate`. 
9. With a new database, you need to create an intial access credential to the admin portal of the app. Run the command `python3 manage.py createsuperuser` and follow the prompts to complete the process. 
10. Follow instructions for a [local launch of the app](#local-launch-of-the-app). 
11. Before adding any questions to the app as detailed in [this section](#add-new-questions-to-database), make sure you first assign at least one "main admin" from the reviewers. Details can be found in [this section](#add-reviewer-to-the-app). 
