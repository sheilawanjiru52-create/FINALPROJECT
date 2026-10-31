# NutriTrack App

## Introduction

Nutrition plays an important role in maintaining good health and preventing diet-related diseases. However, many people struggle to understand their nutritional intake, identify nutritional deficiencies and make informed food choices.

This project aims to develop NutriTrack, a machine learning-based nutritional tracking and food recommendation system. The system uses a nutritional database containing different food items and their nutrient compositions. Machine learning techniques, particularly K-Means clustering, are applied to group foods according to their nutritional characteristics.

The application allows users to record their daily food consumption, monitor their nutrient intake over time and receive personalized food recommendations based on their nutritional goals. It also incorporates time-based analysis to identify nutritional patterns and changes in eating habits.

## Problem Statement

Many individuals lack an effective way of monitoring their daily nutritional intake and understanding whether their diets meet their nutritional requirements.

Existing food-tracking approaches may provide basic calorie information but often offer limited personalized recommendations, nutritional pattern analysis and insights into the overall quality of an individual's diet.

Additionally, identifying foods that can help individuals meet specific nutritional goals can be challenging, particularly when dealing with large nutritional databases.

There is therefore a need for an intelligent nutritional tracking system that integrates nutritional data analysis, machine learning and time-based tracking to help users understand their eating habits and make more informed food choices.

## Main Aim
To develop a machine learning-based nutritional tracking and food recommendation system that enables users to monitor their dietary intake, identify nutritional patterns and receive personalized food recommendations based on their nutritional goals.

### Specific Objectives

1. To develop a nutritional database: Collect, clean and organize food composition data containing different foods and their nutritional values to establish a reliable nutritional database.

2. To apply machine learning techniques for food clustering: Implement K-Means clustering to group foods according to their nutritional characteristics and identify similarities between different food items.

3. To develop a nutritional tracking system: Create an application that allows users to record their daily food consumption and monitor their intake of calories, macronutrients and other available nutrients.

4. To develop a machine learning-based food recommendation system: Recommend suitable foods based on users' nutritional goals, using nutritional characteristics and the identified food clusters.

5. To implement time-based nutritional analysis: Analyse users' food consumption history over different periods to identify nutritional trends, recurring eating patterns and changes in nutrient intake.

6. To evaluate the performance of the developed system: Assess the effectiveness of the clustering techniques and the functionality of the nutritional tracking and recommendation system.

## Methodology

### Stage 1: Data Collection and Preparation

Obtain food composition data containing nutritional information such as energy, protein, carbohydrates, fats, fibre, vitamins and minerals. Clean the dataset, handle missing values, distinguish trace values and prepare the data for analysis.

### Stage 2: Exploratory Data Analysis and Machine Learning

Explore the nutritional dataset through statistical analysis and visualizations. Apply feature scaling and K-Means clustering to group foods according to their nutrient composition. Evaluate clustering performance using metrics such as Silhouette Score, Davies-Bouldin Index and Calinski-Harabasz Index.

### Stage 3: Application Development

Develop an interactive web application using Python and Streamlit. Implement user registration, login, food tracking, nutritional summaries and a SQLite database to store individual users' food consumption records.

### Stage 4: Food Recommendation System

Integrate the machine learning clustering results into the application. Develop a recommendation mechanism that suggests foods based on nutritional goals such as higher protein, higher fibre, lower energy or a specific nutrient selected by the user.

### Stage 5: Time-Based Nutritional Analysis

Analyse stored food consumption records over time. Generate daily, two-day and weekly nutritional summaries, visualize nutrient trends and identify recurring dietary patterns. Use these insights to help users understand their eating habits.

### Stage 6: Testing and Evaluation

Test the application to ensure that user records are stored correctly, nutritional calculations are accurate, recommendations are relevant and clustering results are reliable. Evaluate the overall functionality and performance of the system.

## Data Source

Source: Food and Agriculture Organization of the United Nations (FAO)

Contains: Kenya Food Composition Tables (2018)

## Expected Outcome

The expected outcome is that the app:

- Provides a structured nutritional database.
  
- Groups foods according to their nutritional similarities using machine learning.

-  Allows users to monitor their daily nutritional intake.

-  Provides personalized food recommendations based on nutritional goals.

-  Tracks nutritional intake over time and identifies eating patterns.

-  Helps users make more informed nutritional decisions.
