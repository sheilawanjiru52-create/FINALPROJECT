# FINALPROJECT

# Project Proposal

# K-Nutrition app

## **Nutrition and Dietary Health Recommendation System - Kenya**

## 1. Introduction and Problem Statement

Nutrition plays an important role in maintaining good health and reducing the risk of diet-related conditions such as type 2 diabetes, hypertension, obesity, and certain nutritional deficiencies. However, many people struggle to monitor their daily nutrient intake, identify nutritional gaps, and understand how their dietary habits may influence their long-term health.

Although food-tracking applications are available, many focus primarily on calorie counting and may not adequately incorporate locally consumed foods, individual nutritional requirements, historical dietary patterns, or personalized recommendations.

This project proposes the development of a machine-learning-based nutrition application that uses Kenyan food composition data to calculate nutritional intake, identify dietary patterns, forecast future nutrient consumption, and recommend foods that support healthier dietary choices. The system will also assess selected diet-related risk factors using appropriate nutritional guidelines and, where suitable data are available, machine-learning models.

The application will be developed using Python and Streamlit, with machine-learning techniques including K-Means clustering, Long Short-Term Memory (LSTM) networks, and a content-based recommendation system.

## 2. Main Aim

To develop an advanced machine-learning-based nutrition application that analyzes dietary intake, identifies dietary patterns, forecasts future nutrient consumption, and provides personalized food recommendations to support healthier eating habits and reduce selected diet-related health risks.

## 3. Specific Objectives

1. To develop a nutritional database of Kenyan foods using the Kenya Food Composition Tables and other reliable nutritional sources.
2. To develop a system that calculates users' daily calorie and nutrient intake based on the foods and quantities consumed.
3. To apply K-Means clustering to identify patterns in users' dietary intake.
4. To develop an LSTM time-series model to forecast future calorie and nutrient consumption using historical dietary records.
5. To develop a personalized food recommendation system that suggests foods based on identified nutritional gaps and individual dietary requirements.
6. To incorporate a health assessment component that evaluates selected diet-related risk factors using established nutritional guidelines and appropriate health data.
7. To evaluate the performance of the machine-learning models and integrate the components into an interactive Streamlit application.

## 4. Research Questions

1. How can Kenyan food composition data be used to estimate the calorie and nutrient intake of individuals?
2. Can K-Means clustering identify meaningful dietary patterns based on users' nutritional intake?
3. How accurately can an LSTM model forecast future calorie and nutrient consumption from historical dietary records?
4. How can a content-based recommendation system provide personalized food recommendations based on identified nutritional gaps?
5. How can dietary intake and relevant personal characteristics be incorporated into an assessment of selected diet-related health risk factors?

## 5. Methodology

### 5.1 Research Design

The project will adopt an applied machine-learning and software-development approach. Publicly available food composition and health datasets will be used to develop and evaluate the analytical components, which will subsequently be integrated into an interactive application.

### 5.2 Data Collection

The primary nutritional data source will be the **Kenya Food Composition Tables 2018**, published by the Government of Kenya with support from FAO. The tables provide nutritional information for Kenyan foods and recipes.

Additional datasets will be sought for historical dietary intake and relevant health outcomes. Potential sources include national nutrition and health surveys, demographic and health surveys, and publicly available research datasets. The suitability of each dataset will depend on the availability of the required variables, repeated dietary observations, and appropriate outcome labels.

### 5.3 Data Preprocessing

The collected data will be cleaned to address missing values, inconsistent units, duplicate records, and invalid entries. Nutrient measurements will be standardized, categorical variables encoded, and numerical features scaled where necessary. Historical dietary records will be organized chronologically for time-series analysis.

### 5.4 Nutritional Analysis

Users will enter their personal characteristics, such as age, sex, height, weight, activity level, and relevant health conditions, together with the foods and quantities consumed.

The application will calculate BMI, estimate daily energy requirements using established equations, and calculate the total calories and nutrients consumed using food composition values adjusted for the quantity entered.

Daily intake will be compared against appropriate age- and sex-specific nutritional reference values. The system will identify potential nutrient inadequacies and excessive intake without presenting these findings as medical diagnoses.

### 5.5 Machine-Learning Development

**A. Dietary pattern identification — K-Means clustering**

K-Means will group dietary records according to similarities in calorie intake, macronutrients, fibre, and selected micronutrients. The resulting clusters will be interpreted to identify patterns such as high-calorie intake, low-fibre intake, or relatively balanced diets. The number of clusters will be selected using methods such as the elbow method and silhouette score.

**B. Nutrient forecasting — LSTM**

An LSTM neural network will be developed to analyze sequential dietary records and forecast future calorie and nutrient intake. The model will use historical daily intake as input and predict selected nutritional variables over a defined future period. Its performance will be evaluated using mean absolute error (MAE) and root mean squared error (RMSE).

This component will require sufficiently long, sequential dietary records. If suitable longitudinal data cannot be obtained, the forecasting component will be treated as a prototype or evaluated using appropriately collected and documented dietary records.

**C. Personalized food recommendations — Content-based filtering**

A content-based recommendation system will match foods to users' identified nutritional gaps using nutrient composition, dietary preferences, and relevant restrictions. For example, it may recommend iron-rich or fibre-rich foods when the user's recorded intake is below the relevant reference level. Recommendations will be tailored to locally available Kenyan foods.

**D. Diet-related health assessment**

The system will assess selected dietary risk factors, such as excessive sodium intake, high saturated-fat intake, or inadequate fibre intake, using established guidelines. If a suitable labelled dataset is available, a supervised classification model may be developed to investigate associations between dietary characteristics and selected health outcomes. Such predictions will be presented as estimates, not diagnoses, and will not imply that diet alone determines disease risk.

### 5.6 Model Evaluation

K-Means clustering will be evaluated using the silhouette score and cluster interpretability. LSTM forecasting performance will be assessed using MAE and RMSE against held-out chronological observations. The recommendation system will be evaluated using suitable ranking or relevance measures and, where feasible, expert review. Any supervised health-outcome model will be evaluated using appropriate metrics such as precision, recall, F1-score, ROC-AUC, and validation on held-out data.

### 5.7 Application Development

The final application will be built using Streamlit and Python libraries, including Pandas, NumPy, Scikit-learn, and TensorFlow/Keras. It will allow users to record foods and quantities, view daily nutritional summaries, review dietary patterns, see nutrient forecasts, and receive personalized food recommendations.

## 6. Summarized Methodology

1. **Data collection:** Obtain Kenyan food composition data and suitable dietary or health datasets.
2. **Preprocessing:** Clean, standardize, and prepare the data for analysis.
3. **Nutritional calculations:** Estimate calories, nutrient intake, BMI, and individualized reference requirements.
4. **Clustering:** Apply K-Means to identify dietary patterns.
5. **Time-series forecasting:** Train an LSTM model to forecast future nutrient intake.
6. **Recommendation system:** Use content-based filtering to suggest foods that address identified nutritional gaps.
7. **Health assessment:** Evaluate selected dietary risk factors using established guidelines and, where data permit, a supervised model.
8. **Evaluation and deployment:** Evaluate each component and integrate the system into a Streamlit application.

## 7. Expected Outcomes

The project is expected to produce:

* An interactive nutrition application featuring Kenyan foods.
* Automated calorie and nutrient calculations based on user-entered quantities.
* Clusters representing distinct dietary patterns.
* Forecasts of future calorie and nutrient intake, subject to data availability.
* Personalized food recommendations based on nutritional gaps.
* A dietary health assessment feature that communicates potential risk factors responsibly.
* An evaluation of the performance and limitations of the implemented machine-learning techniques.
