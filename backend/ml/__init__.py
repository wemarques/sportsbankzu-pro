"""ML Pipeline — Multi-season ensemble prediction system.

Modules:
    historical_data     - Multi-season data collection via FootyStats API
    feature_engineering - Rolling averages, Elo ratings, temporal decay weights
    train_model         - Random Forest + XGBoost ensemble training
    predictor           - Production inference with Champion/Challenger evaluation
"""
