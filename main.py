import yaml
import pandas as pd
from datetime import datetime
from scrapers import amazon, currys, richer, johnlewis

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

models = config["models"]
sites = config["sites"]

results = []

for model in models:
    results += amazon.scrape(sites["amazon"].format(query=model), model)
    results += currys.scrape(sites["currys"].format(query=model), model)
    results += richer.scrape(sites["richersounds"].format(query=model), model)
    results += johnlewis.scrape(sites["johnlewis"].format(query=model), model)

df = pd.DataFrame(results)
df["timestamp"] = datetime.now()

df.to_csv("data/prices.csv", mode="a", index=False, header=not pd.io.common.file_exists("data/prices.csv"))
print(df)
