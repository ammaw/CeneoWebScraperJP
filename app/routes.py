from app import app
from flask import render_template, request, redirect, url_for, send_file
import os
import json
import requests
import pandas as pd
import numpy as np
import io
from matplotlib import pyplot as plt
import matplotlib 
from bs4 import BeautifulSoup
from app.utils import extract_content, score, selectors, transformations, translate
matplotlib.use('Agg') 

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/extract', methods=['POST', 'GET'])
def extract():
    if request.method == 'POST':
        product_id = request.form.get("product_id")
        url = f"https://www.ceneo.pl/{product_id}"
        response = requests.get(url)
        if response.status_code == requests.codes['ok']:
            page_dom = BeautifulSoup(response.text, "html.parser")
            opinions_count = extract_content(page_dom,'a.product-review__link > span')
            if opinions_count:
                product_name = page_dom.select_one("h1").get_text().strip()
                url = f"https://www.ceneo.pl/{product_id}#tab=reviews"
                all_opinions = []
                while(url):
                    response = requests.get(url)
                    response.status_code
                    page_dom = BeautifulSoup(response.text, "html.parser")
                    opinions = page_dom.select("div.js_product-review")
                    for opinion in opinions:
                        single_opinion = {
                            key: extract_content(opinion, *value)
                                for key, value in selectors.items()
                        }
                        for key, value in transformations.items():
                            single_opinion[key] = value(single_opinion[key])
                        all_opinions.append(single_opinion)
                    try:
                        url = "https://www.ceneo.pl"+extract(page_dom, "a.pagination__next", "href")
                    except TypeError:
                        url = None
                if not os.path.exists("app/data"):
                    os.mkdir("app/data")
                if not os.path.exists("app/data/opinions"):
                    os.mkdir("app/data/opinions")
                with open(f"app/data/opinions/{product_id}.json", "w", encoding="UTF-8") as jf:
                    json.dump(all_opinions, jf, indent=4, ensure_ascii=False)
                opinions = pd.DataFrame.from_dict(all_opinions)
                MAX_SCORE = 5
                opinions.score = opinions.score.apply(lambda s: round(s*MAX_SCORE, 1))
                opinions_count = opinions.index.size
                pros_count = opinions.pros.apply(lambda p: None if not p else p).count()
                cons_count = opinions.cons.apply(lambda c: None if not c else c).count()
                average_score = opinions.score.mean()
                score_distribution = opinions.score.value_counts().reindex(np.arange(0,5.5,0.5), fill_value = 0)
                recommendation_distribution = opinions.recommendation.value_counts(dropna=False).reindex([True, False, None], fill_value = 0)
                statistics = {
                    'product_id' : product_id,
                    'product_name' : extract_content(page_dom, "h1"),
                    'opinions_count' : opinions_count,
                    'pros_count' : int(opinions.pros.astype(bool).sum()),
                    'cons_count' : int(opinions.cons.astype(bool).sum()),
                    'average_score' : opinions.score.mean().round(3),
                    'score_distribution' : opinions.score.value_counts().reindex(np.arange(0,5.5,0.5), fill_value = 0).to_dict(),
                    'recommendation_distribution' : opinions.recommendation.value_counts(dropna=False).reindex([1,np.nan,0]).to_dict()
                }
                if not os.path.exists("app/data/statistics"):
                    os.mkdir("app/data/statistics")
                with open(f"app/data/statistics/{product_id}.json", "w", encoding="UTF-8") as jf:
                    json.dump(statistics, jf, indent=4, ensure_ascii=False)
                    if not os.path.exists("app/static/charts"):
                        os.mkdir("app/static/charts")
                    flg, ax = plt.subplots()
                    score_distribution.plot.bar(color = "purple")
                    plt.xlabel("Number of stars")
                    plt.ylabel("Number of  opinions")
                    plt.title(f"Score histogram for {product_name}")
                    plt.xticks(rotation = 0)
                    ax.bar_label(ax.containers[0], label_type='edge', fmt = lambda l: int(l) if l else "")
                    plt.savefig(f"app/static/charts/{product_id}_score.png")
                    plt.close()
                    recommendation_distribution.plot.pie(
                        labels = ["Recommend", "Not recommend", "Indifferent"],
                        label = "",
                        colors = ["forestgreen", "crimson", "silver"],
                        autopct = lambda l: "{:1.1f}%".format(l) if l else ""
                    )
                    plt.title(f"Recommendations shares for {product_name}")
                    plt.savefig(f"app/static/charts/{product_id}_recommendation.png")
                return redirect(url_for('product', product_id=product_id))
            return render_template("extract.html", error = "Product has no opinions")
        return render_template("extract.html", error = "Product does not exist")
    return render_template("extract.html")

@app.route('/products')
def products():
    products_list = [filename.split(".")[0] for filename in os.listdir("app/data/statistics")]
    products = []
    for product_id in products_list:
        with open(f"app/data/statistics/{product_id}.json", "r", encoding="UTF-8") as jf:
            statistics = json.load(jf)
            products.append(statistics)
    return render_template("products.html", products=products)

@app.route('/author')
def author():
    return render_template("author.html")

@app.route('/product/<product_id>')
def product(product_id):
    if os.path.exists("app/data/opinions"):        
        opinions = pd.read_json(f"app/data/opinions/{product_id}.json")
        return render_template("product.html", product_id=product_id, opinions = opinions.to_html(classes="table table-warning table-striped"), table_id="opinions", index=False)
    return redirect(url_for('extract'))

@app.route('/charts/<product_id>')
def charts(product_id):
    return render_template('charts.html', product_id=product_id)

@app.route('/download_json/<product_id>')
def download_json(product_id):
    return send_file(f"/data/opinions/{product_id}.json", "text/json", as_attachment=True)

@app.route('/download_csv/<product_id>')
def download_csv(product_id):
    opinions = pd.read_json(f"app/data/opinions/{product_id}.json")
    buffer = io.BytesIO(opinions.to_csv(index=False).encode())
    return send_file(buffer, "text/csv", as_attachment=True, download_name=f"{product_id}.csv")

@app.route('/download_xlsx/<product_id>')
def download_xlsx(product_id):
    opinions = pd.read_json(f"app/data/opinions/{product_id}.json")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer) as writer:
        opinions.to_excel(writer, index=False)
    buffer.seek(0)
    return send_file(buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=f"{product_id}.xlsx")