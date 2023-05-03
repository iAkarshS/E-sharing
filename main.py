from datetime import datetime, timedelta
import json
import os
import random

from flask import Flask, render_template, request
from pandas_datareader import data as pdr 
import pandas as pd
import requests
import yfinance as yf
import boto3
FLASK_APP: "main.py"


app = Flask(__name__)
instances = []
urls = []	
auditlogs = [] 
region = os.environ.get('AWS_REGION')
print (region)
aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
aws_session_token = os.environ.get('AWS_SESSION_TOKEN')
lambda_name = 'lambda1'
lambda_handler_name = 'code.main'
s3_bucket_name = 'lambda-code-12'
s3_key_name = 'code.zip'
if region is None:
	  region= "us-east-1"
	  aws_session_token= "FwoGZXIvYXdzENT//////////wEaDNo9foHVNcYcAHmzoCLFATQmCM9djilStJpvBRzURZTtfwri/IdjWjlDBSYPc1/qMlMQ7vitc9E8zGe0CWw7A7/O5k1d1hwpydr4Km4CBgCfXRwNVbUDbkhjkCjVa4qKAQc/4HNfyNpyHKxQ1yGXSr5YmVnf4IeyTnmvfNHVvkMKTXVs0mKF1f10o9M0qT8d8HiH/5JA6Zp+QOwBbV9sLo4NDKVlOJyDXrD5rlRD7JB3gdLEQLzoE4v4fX5UDHeitnz45JyLg5EGEuySvjZ4d67llLLjKL/pjqIGMi3q5N/HwYicTLnphCAhMUuAI1bB4NTl8VSbeGtt2/F0e5mvsxQHZDiQ4omo4w0="
	  aws_access_key_id= "ASIA2DEPGKPY4YXFNHUK"
	  aws_secret_access_key= "7UWZW5tbkB62m2+cuxWF7vBy5aT0OdZ9WtkSqOIR"
aws_client_kwargs = {
    'aws_access_key_id': aws_access_key_id,
    'aws_secret_access_key': aws_secret_access_key,
    'region_name': region,
    'aws_session_token': aws_session_token
}
ec2 = boto3.resource('ec2', **aws_client_kwargs)
lambda_client = boto3.client('lambda', **aws_client_kwargs)
instance_type = 't2.micro'
user_data = '''#!/bin/bash
sudo systemctl enable flask && sudo systemctl start flask'''



@app.route("/")
def start():
	return render_template("index.html")
	
	
@app.route("/getriskvalues", methods=["POST"])
def getriskvalues():
	if request.method == "POST":
	
		global auditlogs
		global instances
		global urls
		
		auditlogs.append(list())
		auditlogs[-1].append(int(request.form["r"]))
		auditlogs[-1].append("Lambda" if request.form["S"] == "yes" else "EC2")
		
		time_start = datetime.now()
		
		if request.form["S"] == "yes":
		
			create_lambda_function()

		else:
			for ec2 in create_ec2_instances(int(request.form["r"]), int(request.form["r"]), instance_type, user_data):
				ec2.wait_until_running()
				ec2.reload()
				instances.append(ec2)
				urls.append(ec2.public_dns_name)
		
		endtime = (datetime.now() - time_start).seconds
		
		auditlogs[-1].append(endtime)
	
	return render_template("getriskvalues.html")
	
	
@app.route("/simulation", methods=["POST"])
def simulation():
    if request.method == "POST":
        global auditlogs
        global urls
        
        r = int(auditlogs[-1][0])
        
        auditlogs[-1].extend([request.form["h"], request.form["d"], request.form["p"], request.form["t"]])
        
        data = []
        time_start = datetime.now()
        
        if len(urls) == 0:
            for i in range(r):
                response = invoke_lambda_function(get_stock_data().to_json(), request.form["h"], request.form["d"], request.form["p"], request.form["t"])
              
                data.append(response)
            
            content = calculate(data, int(request.form["p"]))
            
        else:
           
            data = []
            
            for url in urls:
                ec2_url = f"http://{ url }:5000/analyze"
                payload = {
                    "data": get_stock_data().to_json(),
                    "H": request.form["h"],
                    "D": request.form["d"],
                    "P": request.form["p"],
                    "T": request.form["t"]
                }
                
                response = requests.post(ec2_url, json=payload)
                data.append(eval(response.content))
                print(data)
                
            content = calculate(data, int(request.form["p"]))
        
        avg_var_95, avg_var_99, profit_95, profit_99 = [0]*4
        
        for row in content[1:]:
            avg_var_95 += row[1]
            avg_var_99 += row[2]
            profit_95 += row[3]
            profit_99 += row[4]
        
        avg_var_95 /= len(content[1:])
        avg_var_99 /= len(content[1:])
        profit_95 /= len(content[1:])
        profit_99 /= len(content[1:])
        
        auditlogs[-1].extend([avg_var_95, avg_var_99, profit_95, profit_99, (datetime.now() - time_start).seconds])
        
        data_json = json.dumps({"data": content})
        #return render_template("calculatedvalues.html", data=data_json)
        return doRender('calculatedvalues.html',{'data':data_json,'Avg95':avg_var_95,'Avg99':avg_var_99,})

	
@app.route("/clear" , methods=["GET", "POST"])
def clearlogs():
	if request.method == "GET":
		global auditlogs
		auditlogs = []
		return render_template("index.html")
	
@app.route("/audit", methods=["GET", "POST"])
def getauditlogs():
	if request.method == "POST":
		global auditlogs
		print(auditlogs)
		return render_template("auditlogs.html", data = json.dumps({"data": auditlogs}))
		
	
@app.route("/close", methods=["GET", "POST"])
def terminate():
	if request.method == "GET":
		global instances, urls
		
		if len(instances) > 0:
			ec2_client = boto3.client("ec2", aws_access_key_id=aws_access_key_id,
					      aws_secret_access_key=aws_secret_access_key, region_name=region, aws_session_token= aws_session_token)
			ec2_instance_ids = [ec2.instance_id for ec2 in instances]
			ec2_client.terminate_instances(InstanceIds=ec2_instance_ids)
			instances.clear()
			urls.clear()
	return render_template("index.html")


def calculate(risk_values, p):
    data = pd.DataFrame(risk_values[0], columns=["date", "var95", "var99"])


    for i, risk_value in enumerate(risk_values[1:]):
        for j, signal in enumerate(risk_value):
            data.iloc[j, 1] += signal[1]
            data.iloc[j, 2] += signal[2]

    num_rows = len(risk_values[0])
    data["var95"] /= num_rows
    data["var99"] /= num_rows

    stock_data = get_stock_data()
    new_95 = []
    new_99 = []
    for _, signal in data.iterrows():
        date = pd.to_datetime(int(signal[0]), unit="ms")
        temp = stock_data.index.get_loc(date)
       
        if temp + p >= len(stock_data):
            old = stock_data.iloc[-1:].Close.values[0]
        else:
            old = stock_data.iloc[temp + p].Close.item()
            
        new_95.append(signal[1] * old)
        new_99.append(signal[2] * old)
        
    data["profit_95"] = new_95
    data["profit_99"] = new_99

    chart_data = data.values.tolist()
    chart_data.insert(0, data.columns.tolist())

    return chart_data


def create_lambda_function():
    try:
        response = lambda_client.create_function(
            FunctionName=lambda_name,
            Runtime='python3.9',
            Handler=lambda_handler_name,
            Code={
                'S3Bucket': s3_bucket_name,
                'S3Key': s3_key_name
            },
            Timeout=120,
            Role="arn:aws:iam::693937525745:role/LabRole"
        )
        return response
    except lambda_client.exceptions.ResourceConflictException:
        return None
        

def create_ec2_instances(min_count, max_count, instance_type, user_data):
    response = ec2.create_instances(
        ImageId='ami-073e3e061da1d924e',
        MinCount=min_count,
        MaxCount=max_count,
        SecurityGroups=["launch-wizard-1"],
        InstanceType=instance_type,
        UserData=user_data
    )
    return response


def get_stock_data():
  yf.pdr_override()
  start_date = datetime.now() - timedelta(days=3652)
  end_date = datetime.now()
  stock_data = pdr.get_data_yahoo('NFLX', start_date, end_date)
  return stock_data
    

def invoke_lambda_function(stock_data, h, d, p, t):
    payload = {
        'data': stock_data,
        'h': h,
        'd': d,
        'p': p,
        't': t
    }
    response = lambda_client.invoke(
        FunctionName=lambda_name,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload).encode('utf-8')
    )
    
    data = eval(response['Payload'].read().decode('utf-8'))
    return data
def doRender(tname, values={}):
	if not os.path.isfile( os.path.join(os.getcwd(), 
'templates/'+tname) ): #No such file
		return render_template('index.html')
	return render_template(tname, **values) 		
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
	
	
