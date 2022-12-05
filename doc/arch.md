# Architecture 

## Main functions 
We provide the drawing specification of a list of parts for users (students) to practice their CAD modelling skills in Onshape. After they finish modelling the part, the app will analyze their feature tree (i.e., how the model is constructed). Then, the app will present 
1. The path the user chose to model their part
2. The different paths that other users chose to model the same part
3. The number of users that chose each of the different paths to model the same part. 

Consequently, the user should be able to compare the modelling path they chose to the other more popular paths, and they are encouraged to reflect on their modelling history to see if they can model the same part in a more efficient approach. 

**GOAL**: teach CAD modelling strategies in an automatic and sustainable way. 

## Front end (user interface)
```
 ------------------------ 
| (1) User opens the app |               --------------------
| in the right panel of  | A workspace? | Ask the user to    |
| an Onshape document    |------------> | return to the main |
| (should be an empty    |         | No | workspace or open  |
| part studio)           |         |    | a branch           |
 ------------------------          |     --------------------
                               Yes |
                                   |
                                   V
                     ---------------------------------
                    | Check and proceed only if the   |
                    | user is in an empty part studio |
                     ---------------------------------
                                   |
                                   | Checked 
 --------------------------        |
| (2) The app presents a   | <------
| list of parts that the   |
| user can choose to model.| 
| Info should include:     | 
| (i) a thumbnail of the   | 
| part, (ii) the number    | 
| of people that have      |
| modelled this part,      |
| (iii) the difficulty     |
| of this model.           |
 -------------------------- 
                |
                |
                V
 ------------------------------- 
| (3) Ask the user to download  |
| the drawings in PDF. The app  |
| should redirect to a new page |
| indicating that the modelling |
| task is in progress. We       |
| should only allow a maximum   |
| of 1.5 hours modelling time   |
| (OAuth token expiring time).  |
 -------------------------------
                |
                | Users model in their 
                | Onshape document 
                V
 -----------------------------------
| (4) When users finish, they click | 
| submit in the app.                |
 -----------------------------------
                |
                |
                V
 ---------------------------------------
| (5) The app shows the modelling paths | 
| as described in the main functions    |
 ---------------------------------------
```

## Back end (database)
```
 ------------------------
| (1) User opens the app | User ID in database?  
| in the right panel as  | ---------------------------------| 
| an Onshape extension.  |        |                   Yes   |
 ------------------------      No |                         | 
                                  V                         |
             ---------------------------                    |
            | Create new database entry |       OAuth token | 
            | for the user              |       expired?    |
             ---------------------------        (90 mins    |
                             |                  since       | 
                             |                  initialized)| 
                             V                              |
             --------------------------    Yes              |
            | A new attempt; initiaite |<-------------------|
            | OAuth authorization      |                    |
             --------------------------                     |
                                    |                    No |
                                    |                       |
                                    V                       |
 ---------------------   No   ----------------------        |
| Quit and ask the    | <----| Make an API call to  |       |
| user to use an      |      | check if the current |       |
| empty part studio   |      | part studio is empty |       |
| or clear the        |       ----------------------        |
| current part studio |                 | Yes               |
 ---------------------                  |                   |
                                        V                   |
 ------------------------------------------------------     |
| (2) Present the list of available models to start in |    |
| a static HTML page. Detailed info is shown as        |    |
| accordions. Users pick one model to start modelling. |    |
 ------------------------------------------------------     |
                |                                           |
                | Create a new database                     |
                | entry for this attemp                     |
                V                                           V
 ---------------------------------------------------------------
| (3) A static HTML page should be shown as the user starts the |
| modelling task. The following info should be presented:       |
| (i).   The drawing(s) of the model's dimension specifications |
|        in PDF. It should be provided to the user as a web     |
|        link that will open a new page. The user can view in   |
|        a new browser tab or download the PDF.                 |
| (ii).  A thumbnail image of the completed part for reference. |
| (iii). A button that allows the user to click and submit      |
|        (i.e., indicating they finish).                        |
 ---------------------------------------------------------------
                |                             ^
                | (4) User submits            | Model not 
                V                             | correct   
 ---------------------------------------------------
| Check if the model is correct with the following  |
| criteria:                                         |
| (i).   The mass of the model is correct           |
|        -> Get the mass property of the model      |
|           through the API                         |
| (ii).  The orientation of the model (required for |
|        image clustering)                          |
|        -> Compare the image of the final model to |
|           the reference model                     |
| (iii). There should be only one part in the part  |
|        studio                                     |
 ---------------------------------------------------
                |
                | Model is correct
                V
 ---------------------------------------------------------------
| The following will be performed in the backend, in order:     |
| (i).   Create a version of the document on the user's behalf. |
| (ii).  Retrieve the list of features in the part studio with  |
|        the API.                                               |
| (iii). Roll the rollback bar after each non-sketch and        |
|        non-plane feature in the feature list, then retrieve   |
|        a thumbnail image for each stage of the reconstruction |
|        process.                                               |
| (iv).  Use the DBSCAN algorithm to cluster the user's         |
|        modelling process (as rebuilt with images) with the    |
|        existing dataset. Eventually, a graph can be created   |
|        with nodes being all the stages of the construction    |
|        process, directed edges being the sequence of          |
|        construction, and weightings of edges being the number |
|        of users that had taken this path to model.            |
 ---------------------------------------------------------------
                |                               |
                |                               |
                V                               V
 ---------------------------       ------------------------------
| (5) Present the resulting |     | Record the design process of |
|     graph to the user.    |     | the user in the database for |
 ---------------------------      | future users to learn from   |
                                  | their modelling process and  |
                                  | strategies.                  |
                                   ------------------------------
```

## Open Sourced Dataset 
As we collect data of the design process in order to accomplish our teaching goal, we open source all the collected (anonymized) data for the research community. 

By using this app to practice CAD modelling and learning the modelling strategies in CAD, the users agree to allow the collection of anonymized data and have them open-sourced for academic research purposes. 

However, considering the time and resources that it takes, the public version of the database will only be updated every 24 hours. 
