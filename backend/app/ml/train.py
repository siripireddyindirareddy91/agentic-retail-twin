"""Offline training from user-supplied historical CSVs. No synthetic accuracy claims."""
import argparse, json
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, precision_score, recall_score, f1_score, roc_auc_score

FEATURES=['supplier_reliability','average_lead_time','lead_time_variation','inventory_availability','shipment_delay_history','demand_variation','historical_disruptions']
def train(path, task):
    df=pd.read_csv(path)
    target='demand' if task=='demand' else 'disrupted'
    required=FEATURES+[target,'date']
    if any(c not in df for c in required):raise ValueError('CSV requires: '+', '.join(required))
    df=df.sort_values('date').dropna(subset=required)
    if len(df)<100: return {'trained':False,'reason':'At least 100 complete chronological records required','fallback':'Moving average / probability × impact'}
    split=int(len(df)*.8);x=df[FEATURES].to_numpy();y=df[target].to_numpy();x_train,x_test=x[:split],x[split:];y_train,y_test=y[:split],y[split:]
    if task=='risk' and (len(np.unique(y_train))<2 or len(np.unique(y_test))<2):return {'trained':False,'reason':'Both chronological partitions need two classes','fallback':'Probability × impact'}
    models={'Random Forest Regressor':RandomForestRegressor(n_estimators=100,random_state=42),'Gradient Boosting Regressor':GradientBoostingRegressor(random_state=42)} if task=='demand' else {'Random Forest Classifier':RandomForestClassifier(n_estimators=100,class_weight='balanced',random_state=42),'Logistic Regression':make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000,class_weight='balanced',random_state=42))}
    results={}
    for name,model in models.items():
        model.fit(x_train,y_train);pred=model.predict(x_test)
        if task=='demand':results[name]={'MAE':mean_absolute_error(y_test,pred),'RMSE':float(np.sqrt(mean_squared_error(y_test,pred))),'R2':r2_score(y_test,pred)}
        else:results[name]={'precision':precision_score(y_test,pred,zero_division=0),'recall':recall_score(y_test,pred,zero_division=0),'F1':f1_score(y_test,pred,zero_division=0),'ROC_AUC':roc_auc_score(y_test,model.predict_proba(x_test)[:,1])}
    if task=='demand':
        baseline=np.repeat(np.mean(y_train[-7:]),len(y_test));results['Moving average baseline']={'MAE':mean_absolute_error(y_test,baseline),'RMSE':float(np.sqrt(mean_squared_error(y_test,baseline))),'R2':r2_score(y_test,baseline)}
    return {'trained':True,'deployment_status':'Offline evaluation only; models are not automatically activated','split':'Chronological 80/20','records':len(df),'metrics':results}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('csv');parser.add_argument('--task',choices=['demand','risk'],required=True);args=parser.parse_args();print(json.dumps(train(args.csv,args.task),indent=2))
