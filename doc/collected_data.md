# Data Collection 
After a user submits the completed model and passes the geometric evaluation, the construction process of the submitted model is collected from the user's document. By starting a modelling task in the app, the user agrees to give consent for data collection of the specific document that the user was working on, and the user agrees to have their anonymized data open-sourced for scientific research. 

**Note:** this data collection is only available right after the completion of the task while we still have access to the user's Onshape document through their OAuth tokens. Since users' Onshape documents are not necessarily public, retroactive data collection is not allowed. 

## Data Types 
Here are the data types that are currently being collected by the app: 
1. [Microversions](#1-microversions)
2. [Details of the final model](#2-final-model)
3. [Step-by-step in-progress models of the final product](#3-in-progress-models)
    - [Model 3D geometries in OBJ format](#31-model-3d-geometries)
    - [Model sketches in xxx format](#32-model-2d-sketches)
    - [Shaded views images in PNG format](#33-shaded-view-images)
4. [User audit trail](#4-user-audit-trail)

### 1. Microversions 
When a user starts a modelling question, the current microversion is recorded. By the time the user finishes the model, the entire microversion history of the document since the starting microversion is retrieved. The document history is queried using this API endpiont [here](https://cad.onshape.com/glassworks/explorer/#/Document/getDocumentHistory), except the `username` for each microversion is filtered out to anonymize the data. 

The microversion history data are stored as a sequential list in reversed chronological order, where each item of the list is a JSON object similar to the example shown below. 

```json 
{
    "date": "2022-12-15T16:11:34.613+00:00",
    "canBeRestored": true,
    "description": "Part Studio 1 :: Insert feature : Sketch 1",
    "userId": "888888888888888888888888",
    "microversionId": "b54e0c116a5957a5e8f16a8f",
    "nextMicroversionId": "97c088c56cc53473e43d9bfb"
}
```

### 2. Final model 
When a user finishes modelling a question, the feature list of the final model will be queried and stored. Specifically, information queried from two API endpoints will be stored: 
1. The feature list of the final model ([ref](https://cad.onshape.com/glassworks/explorer/#/PartStudio/getPartStudioFeatures)): this includes the feature type, user-specified name, and parameters used for each feature in the list, and this also includes all the entities and constraints in each sketch. 
2. The Onshape FeatureScript representation of the entire Part Studio ([ref](https://cad.onshape.com/glassworks/explorer/#/PartStudio/getFeatureScriptRepresentation)). 

### 3. In-progress models 
After the user submits the completed model, a version is created for the user and then a branch from the created version. Given the sequential feature list that constructs the final model that the user submits, we move back the rollback bar in the part studio (in the new branch) to each of the position from the start to the end of the feature list. 

#### 3.1 Model 3D geometries  
For every addition of feature that is neither a sketch nor a plane, we export 3D geometry of the part studio in OBJ format. Since none of the questions requests assignment of surface texture or color and all models should be assigned to the same material to pass the question, only the geometry data is saved and stored, the auxilliary file (in MTL format) is discarded. 

#### 3.2 Model 2D sketches
For all sketches used in the Part Studio, every sketch is exported and stored in DWG format. 

#### 3.3 Shaded view images 
After every addition of feature that is neither a sketch nor a plane (a change to the 3D part), two shaded view images of the model in the following angles are created and stored in PNG format: 
- Isometric view 1 (capturing front, right, and top views)
- Isometric view 2 (capturing back, left, and bottom views)

Each image will be auto zoomed to fit the part in the part studio, and the pixel size of each image will be 128 x 128. 

### 4. User audit trail 
Theoretically, we can queried the user's audit trail from Onshape's backend data warehouse based on the information that we are collecting. However, it is not likely that we can connect to the data warehouse to update this dataset automatically. 

Consequently, this will likely only be provided by request, or Onshape may be able to proivde a periodic update of the dataset for every half year or so. 
