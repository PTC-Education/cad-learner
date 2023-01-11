# cad-learner
A web app that hosts CAD modelling problems for self-paced learning in Onshape 

Start the venv by running ```source venv/bin/activate```

You should now see ```(venv) (base) User@usercomputer0``` at the beginning of your command line

Add config vars
```export OAUTH_URL=https://oauth.onshape.com```
```export OAUTH_CLIENT_ID=xxxxxxxxxxxx```
```export OAUTH_CLIENT_SECRET=xxxxxxxxxxxxxxxxx```

If you want to update questions in the database, you will also need to export API keys for an admin
```export ADMIN_ACCESS=xxxxxxxxxxxxxxx```
```export ADMIN_SECRET=xxxxxxxxxxxxxxxxxxxx```


Start the server by running ```python3 manage.py runserver```