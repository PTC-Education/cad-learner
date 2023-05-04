# CAD Challenges
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.7897262.svg)](https://doi.org/10.5281/zenodo.7897262)
![](questioner/static/questioner/images/logo.svg)

The *CAD Challenges* app is a web app that hosts CAD modelling challenges for self-paced learning in Onshape. The app is currently hosted on Heroku and integrated to Onshape through Onshape's OAuth authorization. The app was previously named the *CAD Learner*. 

## What does this app do? 

The *CAD Challenges* app is built to achieve the following: 
- **CAD Education**: the supply of CAD modelling challenges in various types and difficulty levels provides asynchronous parametric modelling practice for students and CAD users in general 
- **CAD Research**: as users work on the modelling challenges in their Onshape documents, we collect a variety of design data of their designing process and the products for research. More notes on data collection can be found on: https://cad-learner.herokuapp.com/. 

An overview of the framework design is illustrated below: 
![](https://user-images.githubusercontent.com/15113020/220923374-d90f4ec7-ac80-4fa0-a171-9a2acbb787de.png)


## Who is this app for? 

### For General Onshape Users 
If you would like to practice your CAD modelling skills in Onshape, or you would like some practicing resources to prepare the Onshape certification exams, you can simply subscribe to our app through Onshape's Appstore [here](https://appstore.onshape.com/apps/Utilities/M2YDH5LM52FAL5JIWB7HUCVOFQZDQURENUPHV2Q=/description). 

### For Educators 
If you would like to contribute additional questions to the app for your students to practice, please contact the maintainers in [this section](#maintainers). A guide on preparing a question for the app can be found on this [wiki page](https://github.com/PTC-Education/cad-learner/wiki/Question-Preparation-Guide), and a list of currently published questions can be found on this [wiki page](https://github.com/PTC-Education/cad-learner/wiki/Questions). Please note that the list of question may not be up-to-date. 

If you would like to fork our repository and host your own *CAD Challenges* app for your students, you may follow instructions on this [wiki page](https://github.com/PTC-Education/cad-learner/wiki/Development-Guide). 

### For Researchers 
If you would like to gain access to the dataset created by this app, please contact the maintainers in [this section](#maintainers). You can find the detailed data collection documentation on this [wiki page](https://github.com/PTC-Education/cad-learner/wiki/Data-Collection-Documentation), and a dashboard of some simple statistics generated from the dataset can be found on: https://cad-learner.herokuapp.com/dashboard/. 

You may also want to fork our repository and host your own CAD research platform for unobtrusive data collection in Onshape. The development guide on this [wiki page](https://github.com/PTC-Education/cad-learner/wiki/Development-Guide) documents some useful information. 

If your research is benefited from this app and/or its general framework, please cite our paper in any research publication https://doi.org/10.1115/DETC2023-114927 

```bibtex
@inproceedings{deng2023cad,
  title={CAD Challenges App: An Informatics Framework for Parametric Modeling Practice and Research Data Collection in Computer-Aided Design},
  author={Deng, Yuanzhe and Mueller, Matthew and Shields, Matt},
  booktitle={International Design Engineering Technical Conferences and Computers and Information in Engineering Conference},
  year={2023},
  organization={American Society of Mechanical Engineers}
}
```

## Maintainers 
If you would like to contact the maintainers of the app for any inquiry, please use this form: https://docs.google.com/forms/d/e/1FAIpQLSeOcFJo3V05CMtQSAXmmiF22xdfsdaob7_tBCTCDEwZVdVRwA/viewform
