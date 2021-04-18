from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
from flask_cors import CORS, cross_origin
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup as bs
import pandas as pd
from time import sleep
import requests
from urllib.request import urlopen as uReq
import nums_from_string as ns
import re
import pymongo
import logging
import os
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import io

"""Logger"""
# create logger with 'spam_application'
logger = logging.getLogger('scrapper application')
logger.setLevel(logging.DEBUG)

# create file handler which logs even debug messages
fh = logging.FileHandler('scrapping.log')
fh.setLevel(logging.DEBUG)

# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)

# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)



def get_chromeDriver():
    try:
        """# For selenium driver implementation on local machine
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument("disable-dev-shm-usage")
        driver = webdriver.Chrome(executable_path=ChromeDriverManager().install(), chrome_options=chrome_options)
        return driver"""
        # for selenium on heroku
        # references : https://inblog.in/PYTHON-SELENIUM-HEROKU-fNaKtKRozt
        # references : https://www.youtube.com/watch?v=Ven-pqwk3ec
        chrome_options = webdriver.ChromeOptions()
        chrome_options.binary_location = os.environ.get("GOOGLE_CHROME_BIN")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        driver = webdriver.Chrome(executable_path=os.environ.get("CHROMEDRIVER_PATH"), options=chrome_options)
        return driver
    except Exception as e:
        raise Exception("chrome driver initialization failed\n" + str(e))



def get_monogoConnection(usrnm, pswd):
    #for connecting to mongo DB
    try:
        url = "mongodb+srv://{}:{}@cluster0.7ilhs.mongodb.net/myFirstDatabase?retryWrites=true&w=majority".format(usrnm, pswd)
        client = pymongo.MongoClient(url)
        return client
    except Exception as e:
        raise Exception("MongoDB Atlas initialization failed\n" + str(e))

def get_searchpage(flipkart_url, seachString,driver):
    #for getting page on which search elements are present
    try:
        search_url = f"{flipkart_url}/search?q={seachString}"
        driver.get(search_url)
        uClient = uReq(search_url)  # requesting the webpage from the internet
        flipkartPage = uClient.read()  # reading the webpage
        uClient.close()  # closing the connection to the web server
        flipkart_html = bs(flipkartPage, "html.parser")  # parsing the webpage as HTML
        return flipkart_html, search_url

    except Exception as e:
        raise Exception("problem getting the search string page\n" + str(e))

def get_productPage(productLink):
    try:
        product_url = productLink
        uClient = uReq(product_url)  # requesting the webpage from the internet
        flipkartPorductPage = uClient.read()  # reading the webpage
        uClient.close()  # closing the connection to the web server
        product_html_soup = bs(flipkartPorductPage, "html.parser")  # parsing the webpage as HTML
        return product_html_soup
    except Exception as e:
        raise Exception("problem getting the search string page\n" + str(e))


def get_productLink(search_url, flipkart_main_soup, flipkart_main_url, product_quantity):
    #get total number of products found
    try:
        total = 0
        for total_products in flipkart_main_soup.find_all('div',{'class':'_1YokD2 _2GoDe3 col-12-12'}):
            total = total_products.div.div.span.text
        total_products_found = ns.get_nums(total.replace(",",""))[1]
    except:
        total_products_found = 0
    try:
        no_of_product = 0
        #checking number of pages which are available for the seached product
        for number_of_product_pages in flipkart_main_soup.find_all('div', {'class': '_2MImiq'}):
            no_of_product = number_of_product_pages.span.text
        num = ns.get_nums(no_of_product)[-1]
    except:
        num = 0

    if num != 0: #  if there is are more than one product pages then find the products links according to quantity mentioned by user
        product_links = []
        i = 1
        while i <= num:
            #print(i)
            soup = get_productPage(str(search_url) + "&page=" + str(i))
            bigboxes = soup.findAll("div", {"class": "_1AtVbE col-12-12"})
            # print(bigboxes)
            for box in bigboxes:
                try:
                    # if prod name and list present then append them in temp
                    product_links.append((box.div.div.div.a.img['alt'],
                                          flipkart_main_url + box.div.div.div.a["href"]))
                    if (len(product_links) >= product_quantity):
                        return product_links, total_products_found
                except:
                    pass
            i += 1
        return product_links, total_products_found
    else: # if there are no pages then give links of the products available
        product_links = []
        soup = get_productPage(str(search_url))
        bigboxes = soup.findAll("div", {"class": "_1AtVbE col-12-12"})
        for box in bigboxes:
            try:
                # if prod name and list present then append them in temp
                product_links.append((box.div.div.div.a.img['alt'],
                                      flipkart_main_url + box.div.div.div.a["href"]))
            except:
                pass
        return product_links, total_products_found


def fetch_image_urls( wd: webdriver, productURL, img_qty: int, sleep_between_interactions: int = 1):

    search_url = productURL
    # load the page
    wd.get(search_url)

    image_urls = set()
    image_count = 0
    results_start = 0

    # get all image thumbnail results
    thumbnail_results = wd.find_elements_by_css_selector("div.q6DClP")
    if img_qty < len(thumbnail_results):
        number_results = img_qty
    else:
        number_results = len(thumbnail_results)

    for img in thumbnail_results[results_start:number_results]:
        # try to click every thumbnail such that we can get the real image behind it
        try:
            ActionChains(wd).move_to_element(img).click(img).perform()  # simple click() will give interaction error as few images thumbnails are not visible, so we are using Action Chains Clicks
            #print("clicked")
            time.sleep(sleep_between_interactions)
        except Exception:
            continue
        # extract image urls
        actual_images = wd.find_elements_by_css_selector('img._396cs4')
        for actual_image in actual_images:
            if actual_image.get_attribute('src') and 'http' in actual_image.get_attribute('src'):
                # print(actual_image.get_attribute('src'))
                image_urls.add(actual_image.get_attribute('src'))

    return image_urls

def persist_image(target_folder, image_urls):
    counter = 0
    for elem in image_urls:
        if not "placeholder" in elem:
            try:
                image_content = requests.get(elem).content
            except Exception as e:
                print(f"ERROR - Could not download {elem} - {e}")

            try:
                f = open(os.path.join(target_folder, 'jpg' + "_" + str(counter) + ".jpg"), 'wb')
                f.write(image_content)
                f.close()
                print(f"SUCCESS - saved {elem} - as {target_folder}")
            except Exception as e:
                print(f"ERROR - Could not save {elem} - {e}")
        counter += 1

def search_and_download(product_id, productURL, img_qty, driver):
    #creating new folder
    try:
        target_path = "static/images"
        target_folder = os.path.join(target_path, '_'.join(product_id.lower().split(' ')))

        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
    except Exception as e:
        raise Exception("problem creating folder\n" + str(e))

    # extracting image links from the page
    image_urls = fetch_image_urls( driver, productURL, img_qty = 20, sleep_between_interactions=1)

    # downloading and saving the images
    persist_image(target_folder, image_urls)


def get_ProductDetailsInfo(product_page_soup, product_id, productName, driver, productURL, img_qty):
    #get product images
    search_and_download(product_id, productURL, img_qty, driver) #function to get product images


    # for getting the product details like price, discounts highlights, color options, description.
    product_header = product_page_soup.find_all('div', {'class': "aMaAEs"})
    for product in product_header:
        try:
            #extract full name
            product_full_name = product.div.h1.span.text
        except:
            product_full_name = "no full name"
        try:
            #extract overall ratings
            overall_ratings = product.find_all('div',{'class':'_3LWZlK'})[0].text
        except:
            overall_ratings = "no overall rating"

        try:
            r = []
            #extract total reviews and ratings
            for reviews in product.find_all('span', {'class': '_2_R_DZ'}):
                r = reviews.span.text.replace(",", "")
            total_ratings = ns.get_nums(r)[0]
            total_reviews = ns.get_nums(r)[1]
        except:
            total_ratings = 0
            total_reviews = 0


        try:
            # extra discount
            extra_discount = product.find_all('div', {'class': '_1V_ZGU'})[0].text
        except:
            extra_discount = "extra discount missing"

        try:
            # extract price
            price = product.find_all('div', {'class': '_30jeq3 _16Jk6d'})[0].text.replace("₹", "")
            price = price.replace(",", "")
            price = ns.get_nums(price)[0]
        except:
            price = 0

        try:
            # extract maximum price
            max_price = product.find_all('div', {'class': '_3I9_wc _2p6lqe'})[0].text.replace("₹", "")
            max_price = max_price.replace(",", "")
            max_price = ns.get_nums(max_price)[0]
        except:
            max_price = 0

        try:
            # extract percentage off
            percent_off = product.find_all('div',{'class':'_3Ay6Sb _31Dcoz'})[0].text
        except:
            percent_off = "percentage off missing"

        if len(product_page_soup.find_all('ul',{'class': ["_36LmXx", "_2jr1F_"]})) != 0:  # in case there is no review for the product
            try:
                s = []
                for star_ratings in product_page_soup.find_all('ul', {'class': ["_36LmXx", "_2jr1F_"]}):
                    s.append(star_ratings.find_all('div', {'class', '_1uJVNT'}))

                stars = []
                for rating in s:
                    if len(
                            rating) == 0:  # there is possibility that both 'ul' are present but only one will contain information
                        pass
                    else:
                        for r in rating:
                            stars.append(ns.get_nums(r.text.replace(",", "")))
            except:
                stars = [[0], [0], [0], [0], [0]]
        else:
            stars = [[0], [0], [0], [0], [0]]

        try:
            # get product options
            options = []
            for desc in product_page_soup.find_all('div', {'class': "_22QfJJ"}):
                options_title = desc.span.text
                options.append(options_title)
                for j in desc.find_all('div', {'class': "_3Oikkn _3_ezix _2KarXJ"}):
                    opt_dtls = j.text
                    options.append(opt_dtls)
        except:
            options = "no product options"

        try:
            # get product highlights
            highlights = []
            for product_highlights in product_page_soup.find_all('li', {'class': "_21Ahn-"}):
                highlights.append(product_highlights.text)
        except:
            highlights = "no product highlights"

        try:
            easy_payment_options = []
            for easy_pay_opts in product_page_soup.find_all('li', {'class': "_1Ma4bX"}):
                easy_payment_options.append(easy_pay_opts.text)
        except:
            easy_payment_options = "no easy payment"

        try:
            # get product description
            desc = product_page_soup.find_all('div', {'class': "_1mXcCf RmoJUa"})[0].text
        except:
            desc = "no description"

        header_dict = {"Product_ID": product_id, "Product_Name": productName, "Product_Full_Name": product_full_name, "Overall_ratings": overall_ratings,
                   "Total_Reviews": total_reviews, "Total_Ratings": total_ratings, "Extra_Discount": extra_discount,
                   "Price": price, "Maximum_Price": max_price, "Percent_off": percent_off,
                   "5Stars": stars[0][0], "4Stars": stars[1][0], "3Stars": stars[2][0], "2Stars": stars[3][0],"1Stars": stars[4][0],
                   "Options": options, "Highlights": highlights, "Easy_Payment_Options": easy_payment_options, "Description": desc}
        driver.execute_script('window.scroll(0,2500)')
        sleep(1)
        return header_dict


def get_comments(soup, product_id, product_name, driver):
    commentboxes = soup.find_all('div', {'class': ["_16PBlm", "_27M-vq"]})
    comm = []
    for commentbox in commentboxes:
        try:
            name = commentbox.div.div.find_all('p', {'class': '_2sc7ZR _2V5EHH'})[0].text
        except:
            name = 'No Name'

        try:
            rating = commentbox.div.div.div.div.text

        except:
            rating = 'No Rating'

        try:
            commentHead = commentbox.div.div.div.p.text
        except:
            commentHead = 'No Comment Heading'
        try:
            likes = commentbox.div.div.find_all('div', {'class': '_1LmwT9'})[0].text
        except:
            likes = '0'

        try:
            dislikes = commentbox.div.div.find_all('div', {'class': '_1LmwT9 pkR4jH'})[0].text
        except:
            dislikes = '0'

        try:
            comtag = commentbox.div.div.find_all('div', {'class': ''})
            custComment = comtag[0].div.text
        except:
            custComment = 'No Customer Comment'

        mydict = {"Product_ID": product_id, "Product_Name": product_name, "Name": name, "Rating": rating,
                  "Likes": likes, "Dislikes": dislikes, "CommentHead": commentHead, "Comment": custComment}
        comm.append(mydict)

        driver.execute_script('window.scroll(0,2500)')
        sleep(1)
    return comm

def get_productReviews(flipkart_main_url, product_page_soup, product_id, product_name, driver, qty):
    try:  # finding the links which contains "/product-reviews" string as it will contain link to all reviews page
        links = []
        for t in product_page_soup.findAll('a', attrs={'href': re.compile("/product-reviews")}):  # regular expression is simply there just to match the links of all links which have "product-reviews" string in many available links
            q = t.get('href')
            links.append(q)
    except:
        links = "none"
    #print(links)

    # finding number of review pages available
    pages = 0
    for link in links:
        if 'marketplace=FLIPKART' in link:  # if there is review link available then go into the reviews page
            f_url = ("https://flipkart.com" + str(link))
            driver.get(f_url)
            #print(f_url)
            soup = get_productPage(f_url)  # finding number of review pages
            for total_review_pages in soup.findAll('div', {'class': '_2MImiq _1Qnn1K'}):
                try:
                    pages = ns.get_nums(total_review_pages.span.text)[1]
                except:
                    pass
    #print(pages)
    # iterating through each review
    comments = []
    if pages != 0:  # if there are pages then iterate through each page and get the comments otherwise get the comments which are on the page
        i = 1
        while i <= pages:
            driver.get(str(f_url) + "&page=" + str(i))
            comment = get_comments(get_productPage(str(f_url) + "&page=" + str(i)), product_id, product_name, driver)
            comments.extend(comment)
            if len(comments) >= qty:
                return comments
            i += 1
        return comments
    else:
        comments = get_comments(product_page_soup, product_id, product_name, driver)
        return comments
app = Flask(__name__)  # initialising the flask app with the name 'app'

@app.route('/',methods=['POST','GET']) # route with allowed methods as POST and GET
@cross_origin()
def index():
    if request.method == 'POST':
        searchString = request.form['content'] # obtaining the search string entered in the form
        product_quantity = request.form['product_qty'].replace(" ", "") # obtaining number of Products to be scrapped
        if product_quantity == "":
            product_quantity = 2 #default number of products
            product_quantity = int(product_quantity)
        else:
            product_quantity = int(product_quantity)

        reviews_quantity = request.form['review_qty'].replace(" ", "") # obtaining number of reviews required for each product
        if reviews_quantity == "":
            reviews_quantity = 20 #default number of reviews
            reviews_quantity = int(reviews_quantity)
        else:
            reviews_quantity = int(reviews_quantity)
        images_quantity = request.form['image_qty'].replace(" ", "") #get no. of product images required
        logger.info("search string : {}, product quantity : {}, reviews quantitiy : {}".format(searchString, product_quantity, reviews_quantity))
        try:

            client = get_monogoConnection(usrnm='user1', pswd='user123')
            db = client['crawlerDB']  # connecting to the database called crawlerDB
            searchString_store_name = searchString.replace(".","")
            searchString_store_name = searchString_store_name.replace(",", " ")
            searchString_store_name = searchString_store_name.replace("|", " ")
            searchString_store_name = searchString_store_name.replace(" ", "_")

            ss = searchString.replace(".", "")
            ss = ss.replace(",", " ")
            ss = ss.replace("|", " ")
            ss = ss.replace(" ", "+")
            reviews = db[searchString_store_name].find({})  # searching the collection with the name same as the keyword
            logger.info("finding search string in DB")
            if reviews.count() > 0:  # if there is a collection with searched keyword and it has records in it
                logger.info("DB exist. Retrieving the result")
                return render_template('results.html', reviews=reviews)  # show the results to user
            else:
                driver = get_chromeDriver()
                flipkart_main_url = "https://flipkart.com" # base url
                logger.info("DB does not exist retrieving the search string on flipkart page")
                flipkart_main_soup, search_url = get_searchpage(flipkart_main_url, ss, driver) # getting souped page for search URL and the URL of the page
                product_links, total_products_found = get_productLink(search_url, flipkart_main_soup, flipkart_main_url, product_quantity)  # getting the hyperlinks of the products from the product page
                logger.info("got {} product Hyperlinks ".format(len(product_links)))
                # print(product_links)
                product_info = []
                product_information_table = db[searchString_store_name]
                #extracting first 4 products
                i = 0
                for productName, productURL in product_links:

                    driver.get(productURL)
                    product_page_soup = get_productPage(productURL)

                    #getting product details and images
                    i += 1
                    product_id = searchString_store_name + "_" + str(i)
                    product_details = get_ProductDetailsInfo(product_page_soup, product_id, productName, driver, productURL, images_quantity) #function to scrape details and images
                    product_information_table.insert_one(product_details)  # insertig the dictionary containing the rview comments to the collection
                    product_info.append(product_details)
                    logger.info("product details saved to db for {}".format(product_details['Product_Name']))
                    #getting reviews on the product

                    product_review_table =db[product_id]
                    product_reviews = get_productReviews(flipkart_main_url, product_page_soup, product_id, product_details['Product_Name'], driver, reviews_quantity)
                    product_review_table.insert_many(product_reviews)
                    logger.info("reviews saved in {}".format(product_id))

                    # extract comment boxes from product HTML

                return render_template('results.html', reviews=product_info)

        except Exception as e:
            raise Exception("problem in \n" + str(e))

            #return render_template('results.html')
    else:
        return render_template('index.html')

@app.route('/show_products', methods=['POST','GET']) # route with allowed methods as POST and GET
@cross_origin()
def show_products():
    if request.method == 'GET':
        try:
            client = get_monogoConnection(usrnm='user1', pswd='user123')
            db = client['crawlerDB']
            available_products = []
            for i in db.list_collection_names():
                f = db[i]
                if len(f.find_one()) == 20:
                    available_products.append(i)

            return render_template('show_products.html', available_products=available_products)
        except:
            return "something went wrong"

@app.route('/results', methods=['POST','GET']) # route with allowed methods as POST and GET
@cross_origin()
def results():
    if request.method == 'GET':
        try:
            product_name = request.args.get('name')
            client = get_monogoConnection(usrnm='user1', pswd='user123')
            db = client['crawlerDB']  # connecting to the database called crawlerDB
            reviews = db[product_name].find({})  # searching the collection with the name same as the keyword
            if reviews.count() > 0:  # if there is a collection with searched keyword and it has records in it
                logger.info("DB exist. Retrieving the result")
                return render_template('results.html', reviews=reviews)  # show the results to user

        except:
            return "something went wrong"

@app.route('/show_reviews', methods=['POST','GET']) # route with allowed methods as POST and GET
@cross_origin()
def show_reviews():
    if request.method == 'GET':
        try:
            product_name = request.args.get('product_name')
            client = get_monogoConnection(usrnm='user1', pswd='user123')
            db = client['crawlerDB']
            products = db[product_name].find({})
            review_counts = db[product_name].count()
            logger.info("showing reviews for {}".format(product_name))
            return render_template('show_reviews.html', products=products, review_counts=review_counts)
        except:
            return "something went wrong"

@app.route('/show_images', methods=['POST','GET']) # route with allowed methods as POST and GET
@cross_origin()
def show_images():
    if request.method == 'GET':
        try:
            product_name = request.args.get('product_name')
            parent_dir = "static/images"
            path = os.path.join(parent_dir, product_name)
            image_names = os.listdir(path)
            logger.info("showing images of {}".format(product_name))
            return render_template('show_images.html', image_name=image_names, folder=product_name)
        except:
            return "something went wrong"

def build_pie_plot(percentages,name):
    fig = Figure()
    # canvas = FigureCanvas(fig)
    ax1 = fig.add_subplot(111)

    labels = 'scrapped', 'not scrapped'
    explode = (0.1, 0)
    # fig1, ax1 = plt.subplots()
    ax1.pie(percentages, explode=explode,
            labels=labels, autopct='% 1.1f %%',
            shadow=True, startangle=90)
    ax1.axis('equal')

    ax1.set_title(name + ' Reviews')
    return fig
    #my_labels = 'Reviews_Scrapped', 'Not Scrapped'
    #plt.pie(percentages, labels=my_labels, autopct='%1.1f%%')
    #plt.title(name + ' Reviews')
    #plt.axis('equal')

    #return plt


def get_plot(product_name):
    client = get_monogoConnection(usrnm='user1', pswd='user123')
    db = client['crawlerDB']
    no_of_reviews = db[product_name].find({}).count()  # get count of no. of documents present in product review table

    #Get total number of ratings from product detail table
    last_underscore = product_name.rfind("_")
    prod = product_name[:last_underscore]
    product_details_table = db[prod]
    #total_reviews = product_details_table.find({'Product_ID': {"$eq": product_name}}, {'Total_Reviews'})
    total_reviews = product_details_table.find({'Product_ID': {"$eq": product_name}})
    for i in total_reviews:
        a = i['Total_Reviews']
        name = i['Product_Name']
    per_reviews_scrapped = (no_of_reviews / a) * 100
    per_reviews_notscrapped = (100 - per_reviews_scrapped)

    # plotting
    percentages = [per_reviews_scrapped, per_reviews_notscrapped]

    img = build_pie_plot(percentages, name)
    return img

@app.route('/show_graphs', methods=['POST','GET']) # route with allowed methods as POST and GET
@cross_origin()
def show_graphs():
    if request.method == 'GET':
        try:
            product_name = request.args.get('product_name')
            return redirect(url_for('plot_png', product_name=product_name))
        except:
            return "something went wrong"

@app.route('/a', methods=['GET'])
@cross_origin()
def plot_png():
    product_name = request.args.get('product_name', None)
    fig = get_plot(product_name)
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

if __name__ == "__main__":
    #app.run(port=7000, debug=True) # running the app on the local machine on port 8000
    app.run()

