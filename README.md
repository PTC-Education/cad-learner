# cad-learner
A web app that hosts CAD modelling problems for self-paced learning in Onshape 

## Add new questions to database
Go to http://localhost:8000/admin and add a question, then fill out form with details from the following.

For Part Studio questions, there should be two documents:
* One document with the naming convention "CAD Learner - V Block (Source)":
    * One Part Studio with original feature list for designing the part
    * Not shared (besides owners)
* One document with the naming convention "CAD Learner - V Block":
    * One Part studio with one derive feature pulling in part(s) from source doc
    * One JPEG element that is of a drawing (used for right panel app interface, so preferably portrait orientation)
    * One Drawing element (to be opened in new tab, so preferably landscape orientation)
    * Link sharing turned on


## Setting up local development environmant
Start the venv by running ```source venv/bin/activate```

You should now see ```(venv) (base) User@usercomputer0``` at the beginning of your command line

Add config vars (need to create new OAuth app from https://dev-portal.onshape.com/ first)
```export OAUTH_URL=https://oauth.onshape.com```
```export OAUTH_CLIENT_ID=xxxxxxxxxxxx```
```export OAUTH_CLIENT_SECRET=xxxxxxxxxxxxxxxxx```

If you want to update questions in the database, you will also need to export API keys for an admin
```export ADMIN_ACCESS=xxxxxxxxxxxxxxx```
```export ADMIN_SECRET=xxxxxxxxxxxxxxxxxxxx```

Start the server by running ```python3 manage.py runserver```

### To add an admin to the app
Run ```python3 manage.py createsuperuser``` then follow the prompts.

### To make a change to the database
First run ```python3 manage.py makemigrations```

Then run ```python3 manage.py migrate```

### To manually update the database from command line
To launch shell locally
```python3 manage.py shell```
Now you should see ```>>>```

Example of how you would update the completion feature count array
```from questioner.models import Question_SPPS```
```q = Question_SPPS.objects.get(question_id=3)```
```q.completion_feature_cnt = [10,2,4,10,20,3]```
```q.save()```
```quit()```

To launch shell in heroku
```heroku run python manage.py shell``