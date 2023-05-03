from flask import Flask, request
import pandas as pd
import random

app = Flask(__name__)

@app.route("/analyze", methods=["POST"])
def entry():

	if request.method == "POST":
		
		event = request.json
	
		stockdata = pd.DataFrame(eval(event["data"]))
		
		stockdata['Buy']=0 

		stockdata['Sell']=0 


		for i in range(2, len(stockdata)):  

		    body = 0.01 


		    if (stockdata.Close[i] - stockdata.Open[i]) >= body and stockdata.Close[i] > stockdata.Close[i-1] and (stockdata.Close[i-1] - stockdata.Open[i-1]) >= body and stockdata.Close[i-1] > stockdata.Close[i-2] and (stockdata.Close[i-2] - stockdata.Open[i-2]) >= body:
		    	
		    	stockdata.at[stockdata.index[i], 'Buy'] = 1 


		    if (stockdata.Open[i] - stockdata.Close[i]) >= body and stockdata.Close[i] < stockdata.Close[i-1] and (stockdata.Open[i-1] - stockdata.Close[i-1]) >= body and stockdata.Close[i-1] < stockdata.Close[i-2] and (stockdata.Open[i-2] - stockdata.Close[i-2]) >= body:
		    	
		    	stockdata.at[stockdata.index[i], 'Sell'] = 1 

		 
		minhistory = int(event["H"]) 

		shots = int(event["P"])
		
		response = []

		for i in range(minhistory, len(stockdata)):  

		    if stockdata.Buy[i]==1 and event["T"] == "buy": 

			       mean=stockdata.Close[i-minhistory:i].pct_change(1).mean() 

			       std=stockdata.Close[i-minhistory:i].pct_change(1).std() 

			       simulated = [random.gauss(mean,std) for x in range(shots)] 

			       simulated.sort(reverse=True) 

			       var95 = simulated[int(len(simulated)*0.95)] 

			       var99 = simulated[int(len(simulated)*0.99)] 
			       
			       response.append([int(stockdata.index[i]), var95, var99])
			       
			       
		    elif stockdata.Sell[i]==1 and event["T"] == "sell": 

			       mean=stockdata.Close[i-minhistory:i].pct_change(1).mean() 

			       std=stockdata.Close[i-minhistory:i].pct_change(1).std() 
	 

			       simulated = [random.gauss(mean,std) for x in range(shots)] 


			       simulated.sort(reverse=True) 

			       var95 = simulated[int(len(simulated)*0.95)] 

			       var99 = simulated[int(len(simulated)*0.99)] 
			       
			       response.append([int(stockdata.index[i]), var95, var99])
	 
		return response
