import json
import os.path
import re
import time
import traceback
from datetime import datetime
from string import ascii_lowercase

import chromedriver_autoupdater
import requests
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

t = 1
timeout = 10

debug = True

headless = False
images = False
maximize = False

incognito = False

api = "https://surrogatesearch.co.middlesex.nj.us/SurrogateSearch"
json_folder = "middlesex"
asset_dir = "assets"
html_dir = "html"

# test = os.path.exists("README.md")
test = False
if os.path.isfile("GoogleAddress.json"):
    with open("GoogleAddress.json", "r", encoding="utf8") as f:
        googleAddress = json.load(f)
else:
    googleAddress = {}
    with open("GoogleAddress.json", "w", encoding="utf8") as f:
        json.dump(googleAddress, f, indent=4, ensure_ascii=False)
non_property_words = """account
ability
access
insurance
policy
apple
stock
check
vin
VIN
Authorization
continue
author
ins.
claim
acct
bank
bond
fund
limited
inc
llc
ltd
corp
affidavit
credit""".split("\n")
property_words = """condominium
home
house
interest
located 
mortgage for
portion
property
real
share
block
lot
nj""".split("\n")

abbreviations = {
    "alley": "aly",
    "annex": "anx",
    "apartment": "apt",
    "avenue": "ave",
    "basement": "bsmt",
    "boulevard": "blvd",
    "building": "bldg",
    "causeway": "cswy",
    "center": "ctr",
    "circle": "cir",
    "court": "ct",
    "cove": "cv",
    "crossing": "xing",
    "department": "dept",
    "drive": "dr",
    "estate": "est",
    "expressway": "expy",
    "extension": "ext",
    "floor": "fl",
    "freeway": "fwy",
    "grove": "grv",
    "heights": "hts",
    "highway": "hwy",
    "hollow": "holw",
    "junction": "jct",
    "lane": "ln",
    "motorway": "mtwy",
    "overpass": "opas",
    "park": "park",
    "parkway": "pkwy",
    "place": "pl",
    "plaza": "plz",
    "point": "pt",
    "road": "rd",
    "route": "rte",
    "skyway": "skwy",
    "square": "sq",
    "street": "st",
    "terrace": "ter",
    "trail": "trl",
    "unit": "unit",
    "way": "way",
}

usa_states = {
    "alabama": "al",
    "alaska": "ak",
    "american samoa": "as",
    "arizona": "az",
    "arkansas": "ar",
    "california": "ca",
    "colorado": "co",
    "connecticut": "ct",
    "delaware": "de",
    "district of columbia": "dc",
    "florida": "fl",
    "georgia": "ga",
    "guam": "gu",
    "hawaii": "hi",
    "idaho": "id",
    "illinois": "il",
    "indiana": "in",
    "iowa": "ia",
    "kansas": "ks",
    "kentucky": "ky",
    "louisiana": "la",
    "maine": "me",
    "maryland": "md",
    "massachusetts": "ma",
    "michigan": "mi",
    "minnesota": "mn",
    "mississippi": "ms",
    "missouri": "mo",
    "montana": "mt",
    "nebraska": "ne",
    "nevada": "nv",
    "new hampshire": "nh",
    "new jersey": "nj",
    "new mexico": "nm",
    "new york": "ny",
    "north carolina": "nc",
    "north dakota": "nd",
    "northern mariana is": "mp",
    "ohio": "oh",
    "oklahoma": "ok",
    "oregon": "or",
    "pennsylvania": "pa",
    "puerto rico": "pr",
    "rhode island": "ri",
    "south carolina": "sc",
    "south dakota": "sd",
    "tennessee": "tn",
    "texas": "tx",
    "utah": "ut",
    "vermont": "vt",
    "virginia": "va",
    "virgin islands": "vi",
    "washington": "wa",
    "west virginia": "wv",
    "wisconsin": "wi",
    "wyoming": "wy",
}


# for key, value in abbreviations.items():
#     property_words.append(key.lower())
#     property_words.append(value.lower())


def getRow(row):
    url = f"{api}/WebPages/web_case_detail_middlesex.aspx?Q_PK_ID={row['ID']}"
    row["URL"] = url
    print(f"Processing record ({row['ID']})")
    if os.path.isfile(f"{html_dir}/{row['Docket']}-{row['ID']}.html"):
        with open(f"{html_dir}/{row['Docket']}-{row['ID']}.html", "r", encoding='utf-8') as f:
            res = f.read()
    else:
        res = requests.get(url).text
        with open(f"{html_dir}/{row['Docket']}-{row['ID']}.html", "w", encoding='utf-8') as f:
            f.write(res)
    soup = BeautifulSoup(res, 'html.parser')
    waitForWebsite(soup)
    for label in soup.find_all("label", {"for": True}):
        val = soup.find("input", {"id": label["for"], "value": True})
        if val:
            row[label.text.strip()[:-1]] = val["value"]
    for table in soup.find_all("table", {"class": "dxgvTable", "id": True}):
        table_id = table["id"]
        if table_id in table_header_map:
            table_id = table_header_map[table_id]
        row[table_id] = []
        if "No data to display" in table.text:
            continue
        trs = table.find_all("tr", recursive=False)
        ths = [td.text.strip() for td in trs[0].find_all("td", recursive=False)]
        for tr in trs[1:]:
            row_tr = {}
            tds = tr.find_all("td", recursive=False)
            for th, td in zip(ths, tds):
                row_tr[th] = td.text.strip()
            row[table_id].append(row_tr)
    row['Full Name'] = row['Name']
    del row['Name']
    # print(json.dumps(row, indent=4, ensure_ascii=False))
    return row


def processRecord(row):
    id_ = row["ID"]
    docket = row["Docket"]
    #  "8/23/2023"
    row['Filed'] = datetime.strptime(row['Filed'], '%m/%d/%Y').strftime('%Y-%m-%d') if row['Filed'] != "" else ""
    row['Issued'] = datetime.strptime(row['Issued'], '%m/%d/%Y').strftime('%Y-%m-%d') if row['Issued'] != "" else ""
    row['DOD'] = datetime.strptime(row['DOD'], '%m/%d/%Y').strftime('%Y-%m-%d') if row['DOD'] != "" else ""
    row['DOB'] = datetime.strptime(row['DOB'], '%m/%d/%Y').strftime('%Y-%m-%d') if row['DOB'] != "" else ""
    file = f"{json_folder}/{docket}-{id_}.json"
    if os.path.exists(file):
        # print(f"Already scraped ({file})")
        # return
        with open(file, "r", encoding='utf-8') as f:
            row = json.load(f)
        print(f"Already scraped ({row['ID']})")

    else:
        row = getRow(row)
    # print(f"Processing {row}")
    row['HOUSE ASSET'] = "No"
    asset_count = 0
    total_asset_value = 0
    tags = [
        f'zz_NJMS_{datetime.strptime(row["Date Filed"], "%m/%d/%Y").strftime("%Y-%m")}',
        f'LP Bot NJBS {datetime.now().strftime("%Y-%m")} 🟦🤖',
        "zz1-NJ-Middlesex Co",
        "LP Bot NJBS 🟦🤖"
    ]

    if 'Address' in row:
        if "Zip" not in row:
            row['Zip'] = ""
        if "State" not in row:
            row['State'] = ""
        if "City" not in row:
            row['City'] = ""
        if row['State'] == "New Jersey":
            row['State'] = "NJ"
        row['SIFT Mailing FULL ADDR'] = f"{row['Address']}, {row['City']}, {row['State']} {row['Zip']}"
        row['SIFT Mailing Address'] = row['Address']
        row['SIFT Mailing City'] = row['City']
        row['SIFT Mailing State'] = row['State']
        row['SIFT Mailing Zip'] = row['Zip']
        del row['Address']
        del row['City']
        del row['State']
        del row['Zip']
    elif 'SIFT Mailing FULL ADDR' not in row:
        print(f"Unable to grab row address for ({row['ID']})")
    assets = row["Assets"].copy()
    property_assets = []
    non_property_assets = []
    for idx, asset in enumerate(assets):
        asset_row = row.copy()
        prop_asset = False
        asset_tags = tags.copy()
        if "Amount" in asset and asset['Amount'] != "":
            try:
                asset_value = float(asset["Amount"].replace("$", "").replace(",", ""))
            except:
                print(f"Unable to parse ({asset['Amount']})")
                asset_value = 0
            total_asset_value += asset_value
            if asset_value > 100_000:
                asset_tags.append("LP Bot NJBS $100K+💲🤖")
        if "Description" in asset and (asset["Description"] == "Home" or "shares" in asset["Description"].lower()):
            if "LP Bot NJBS ❌Unnamed❌🏠🤖" not in tags:
                tags.append("LP Bot NJBS ❌Unnamed❌🏠🤖")
            if "LP Bot NJBS ❌Unnamed❌🤖" not in asset_tags:
                asset_tags.append("LP Bot NJBS ❌Unnamed❌🤖")
        if "Description" not in asset:
            non_property_assets.append(asset)
            continue

        if isAddress(asset["Description"]):
            row['HOUSE ASSET'] = "Yes"
            asset_row['HOUSE ASSET'] = "Yes"
            if "LP Bot NJBS ASSEST🏠🤖" not in tags:
                tags.append("LP Bot NJBS ASSEST🏠🤖")
            if "LP Bot NJBS ASSEST🏠🤖" not in asset_tags:
                asset_tags.append("LP Bot NJBS ASSEST🏠🤖")
            print(f"Processing asset ({asset['Description']})")
            address = asset["Description"].split(" remaining")[0]
            if "Authorization" in address:
                continue
            for word in ["Property", "located at", "Located at"]:
                address = address.replace(word, "").strip()
            if "  " in address:
                address = address.split("  ")[1].strip()
            address_file = sanitize_filename(address)
            address_path = f"{asset_dir}/{asset_row['Docket']}-{asset_row['ID']}-{address_file}.json"
            if os.path.exists(address_path):
                continue
            asset_row["Asset Full Address"] = address
            asset_data = {"Asset Full Address": address}
            if len(address.split(",")) == 3:
                asset_data["Asset Address"] = address.split(",")[0]
                asset_data["Asset City"] = address.split(",")[1].strip()
                asset_data["Asset State"] = address.split(",")[2].strip().split(" ")[0]
            else:
                print(f"Unable to grab asset address for ({address})")
            googleAddress = getGoogleAddress(address)
            asset_data["Asset Normalized Full Address"] = googleAddress
            if googleAddress and asset_data["Asset Normalized Full Address"] and len(googleAddress.split(",")) == 3:
                asset_data["Asset Normalized Address"] = googleAddress.split(",")[0]
                asset_data["Asset Normalized City"] = googleAddress.split(",")[1].strip()
                asset_data["Asset Normalized State"] = googleAddress.split(",")[2].strip().split(" ")[0]
                asset_data["Asset Normalized Zip"] = googleAddress.split(",")[2].strip().split(" ")[1]
            else:
                print(f"Unable to grab asset normalized address for ({address})")
            if googleAddress:
                property_assets.append(asset_data)
                asset_row.update(asset_data)

                asset_count += 1

                asset_row["Tags"] = ", ".join(asset_tags)
                with open(address_path, "w", encoding='utf-8') as f:
                    json.dump(asset_row, f, indent=4, ensure_ascii=False)
            else:
                non_property_assets.append(asset_data)
                print(f"Unable to grab normalized address for ({address})")
        else:
            non_property_assets.append(asset)
    if total_asset_value > 100_000:
        tags.append("LP Bot NJBS $100K+💲🤖")
    if asset_count > 0:
        tags.append(f"LP Bot NJBS ASSEST🏠🤖")
        if asset_count > 1:
            row['HOUSE ASSET'] = "Multi"
    row["Tags"] = ", ".join(tags)
    # del row['Assets']
    row['Assets'] = property_assets + non_property_assets
    with open(f"{json_folder}/{row['Docket']}-{row['ID']}.json", "w", encoding='utf-8') as f:
        json.dump(row, f, indent=4, ensure_ascii=False)


def getGoogleAddress(address):
    if address in googleAddress:
        print(f"Found address in cache ({address})")
        return googleAddress[address]
    # if test:
    #     print('Returning default address')
    #     return address
    url = f"https://www.google.com/search?q={address}"
    print(f"Getting Google Address ({address}) {url}")
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
         "Chrome/104.0.0.0 Safari/537.36"
    soup = BeautifulSoup(requests.get(url, headers={'user-agent': ua}).text, 'lxml')
    if "unusual traffic from this computer" in soup.text:
        print("Google blocked us")
        return None
    try:
        div = soup.find("div", {"class": "vk_sh vk_bk"})
        address = f'{div.find("div").text}, ' \
                  f'{div.find("span").text}'
        print(f"Found {address}")
        googleAddress[address] = address
        with open("GoogleAddress.json", "w", encoding='utf-8') as f:
            json.dump(googleAddress, f, indent=4, ensure_ascii=False)
        return address
    except:
        googleAddress[address] = None
        print(f"No address found {url}")
        with open("google-address.html", "w", encoding='utf8') as outfile:
            outfile.write(soup.prettify())
        with open("google-failed-address.txt", 'a') as f:
            f.write(f"{address}\n")
        # print(soup)
        return None


def waitForWebsite(soup, driver=None):
    while soup.find("title").text == "An item with the same key has already been added." or soup.find('input', {
        'id': '__VIEWSTATE'}) is None:
        print(datetime.now(), f"Website is down!! Goto {api}/default.aspx")
        time.sleep(3)
        res = requests.get(f'{api}/default.aspx')
        soup = BeautifulSoup(res.text, 'html.parser')
        print(soup.find("title").text)
    if driver:
        driver.get(f'{api}/default.aspx')
        time.sleep(3)


def gotoNextPage(driver):
    click(driver,
          "//a[@onclick=\"ASPx.GVPagerOnClick('ContentPlaceHolder1_ASPxGridView_search','PBN');\"]")
    time.sleep(5)


def processPage(driver, config):
    lastname = config['lastname']
    colname = config['colname']
    date = config['date']
    print(f"Processing ({lastname}) ({colname})")
    # url = f'{api}/default.aspx'
    # print(soup.find("b", {"class": "dxp-lead dxp-summary"}).text)
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    for tr in soup.find_all("tr", class_="dxgvDataRow"):
        id_ = tr.find("img", {"alt": True})["alt"]
        row = {
            "ID": id_,
        }
        for td in tr.find_all("td", {"class": "dxgv", "column": True}):
            if td["column"] in row_header_map:
                row[row_header_map[td["column"]]] = td.text.strip()
        if row[colname] == "":
            print(f"Found record ({row[colname]}) with no date")
            return True
        if datetime.strptime(row[colname], '%m/%d/%Y') <= datetime.strptime(date, '%m/%d/%Y'):
            print(f"Found record ({row[colname]}) before ({date})")
            return True
        if test:
            print(json.dumps(row, ensure_ascii=False))
        else:
            try:
                processRecord(row)
            except:
                traceback.print_exc()
                print(f"Unable to process record ({row['ID']})")
    gotoNextPage(driver)
    config['status'] = getElement(driver, '//b[@class="dxp-lead dxp-summary"]').text
    print(f"Status: {config['status']}")
    time.sleep(1)


def main():
    logo()
    print("Loading...")
    driver = getChromeDriver()
    # res = requests.get(f'{api}/default.aspx')
    driver.get(f'{api}/default.aspx')
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    waitForWebsite(soup)
    for x in [asset_dir, json_folder, html_dir]:
        if not os.path.exists(x):
            os.makedirs(x)

    config = {}
    # if test:
    #     config['colname'] = "Filed"
    #     config['date'] = "10/10/2022"
    if os.path.isfile("config.json"):
        with open("config.json", "r") as f:
            config = json.load(f)
    else:
        colname_choice = input("Enter column name:\n1. Filed\n2. Issue\n3. DOD\n4. DOB: ")
        if colname_choice == "1":
            colname = "Filed"
        elif colname_choice == "2":
            colname = "Issued"
        elif colname_choice == "3":
            colname = "DOD"
        elif colname_choice == "4":
            colname = "DOB"
        else:
            print("Invalid choice")
            exit()
        config['colname'] = colname
        config['date'] = input("Enter date (mm/dd/yyyy): ")
        config['lastname'] = "a"
    while True:
        try:
            for lastname in ascii_lowercase:
                if config['lastname'] > lastname:
                    continue
                config['lastname'] = lastname
                driver.get(f'{api}/default.aspx')
                waitForWebsite(BeautifulSoup(driver.page_source, 'html.parser'), driver)
                sendkeys(driver,
                         "//input[@id='ContentPlaceHolder1_ASPxSplitterDefaultMain_ASPxTextBox_search_entry_I']",
                         f"{lastname}\n")
                time.sleep(5)
                if "No data to display".lower() in driver.page_source.lower():
                    print(f"No data to display for ({lastname})")
                    continue
                click(driver, '//td[@id="ContentPlaceHolder1_ASPxGridView_search_col7"]')
                time.sleep(5)
                click(driver, '//td[@id="ContentPlaceHolder1_ASPxGridView_search_col7"]')
                time.sleep(5)
                while True:
                    if processPage(driver, config):
                        print(f"Done with ({config})")
                        break
                    with open("config.json", "w") as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
            driver.get(f'{api}/default.aspx')
            break
        except:
            traceback.print_exc()
            time.sleep(1)
    os.remove("config.json")
    print("==================")
    print("Finished scraping")
    print("==================")
    input("Press enter to exit")


def pprint(msg):
    try:
        print(f"{datetime.now()}".split(".")[0], msg)
    except:
        traceback.print_exc()


def click(driver, xpath, js=False):
    if js:
        driver.execute_script("arguments[0].click();", getElement(driver, xpath))
    else:
        WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath))).click()


def getElement(driver, xpath) -> WebElement:
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))


def getElements(driver, xpath) -> list[WebElement]:
    return WebDriverWait(driver, timeout).until(EC.presence_of_all_elements_located((By.XPATH, xpath)))


def sendkeys(driver, xpath, keys, js=False):
    if js:
        driver.execute_script(f"arguments[0].value='{keys}';", getElement(driver, xpath))
    else:
        getElement(driver, xpath).send_keys(keys)


def getChromeDriver(proxy=None) -> WebDriver:
    options = webdriver.ChromeOptions()
    if debug:
        # print("Connecting existing Chrome for debugging...")
        options.debugger_address = "127.0.0.1:9221"
    else:
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument('--user-data-dir=C:/Selenium1/SurrogateSearch')
    if not images:
        # print("Turning off images to save bandwidth")
        options.add_argument("--blink-settings=imagesEnabled=false")
    if headless:
        # print("Going headless")
        options.add_argument("--headless")
        options.add_argument("--window-size=1920x1080")
    if maximize:
        # print("Maximizing Chrome ")
        options.add_argument("--start-maximized")
    if proxy:
        # print(f"Adding proxy: {proxy}")
        options.add_argument(f"--proxy-server={proxy}")
    if incognito:
        # print("Going incognito")
        options.add_argument("--incognito")
    return webdriver.Chrome(options=options, service=Service(chromedriver_autoupdater.install()))


def getFirefoxDriver() -> WebDriver:
    options = webdriver.FirefoxOptions()
    if not images:
        # print("Turning off images to save bandwidth")
        options.set_preference("permissions.default.image", 2)
    if incognito:
        # print("Enabling incognito mode")
        options.set_preference("browser.privatebrowsing.autostart", True)
    if headless:
        # print("Hiding Firefox")
        options.add_argument("--headless")
        options.add_argument("--window-size=1920x1080")
    return webdriver.Firefox(options)


row_header_map = {
    "full_name": "Name",
    "instr_num": "Docket",
    "ix_data_2": "Case Desc",
    "name_1_township": "Town",
    "ix_date_1": "Filed",
    "ix_date_5": "Issued",
    "ix_date_2": "DOD",
    "ix_date_4": "DOB",
    "sec_data_view": "SC"
}
table_header_map = {
    "ContentPlaceHolder1_ASPxPageControl1_ASPxGridView2_DXMainTable": "Parties",
    "ContentPlaceHolder1_ASPxPageControl1_ASPxGridView1_DXMainTable": "Assets",
    "ContentPlaceHolder1_ASPxPageControl1_ASPxSplitter_image_docs_DocImgGridView_DXMainTable": "Image",
    "ContentPlaceHolder1_ASPxPageControl1_ASPxGridView_docket_DXMainTable": "Post Issue"
}


def logo():
    print(r"""

___  ___ _      _      _  _                          _____                       _          
|  \/  |(_)    | |    | || |                        /  __ \                     | |         
| .  . | _   __| |  __| || |  ___  ___   ___ __  __ | /  \/  ___   _   _  _ __  | |_  _   _ 
| |\/| || | / _` | / _` || | / _ \/ __| / _ \\ \/ / | |     / _ \ | | | || '_ \ | __|| | | |
| |  | || || (_| || (_| || ||  __/\__ \|  __/ >  <  | \__/\| (_) || |_| || | | || |_ | |_| |
\_|  |_/|_| \__,_| \__,_||_| \___||___/ \___|/_/\_\  \____/ \___/  \__,_||_| |_| \__| \__, |
                                                                                       __/ |
                                                                                      |___/ 
================================================================================================
            Middlesex county NJ Bankruptcy Scraper by github.com/evilgenius786
================================================================================================
[+] Automated
________________________________________________________________________________________________
""")


def isAddress(description):
    # if re.search(r'\b\d{4}\b', description):
    #     return False
    if "#" in description:
        return False
    with open("car-manufacturers.txt") as f:
        for line in f:
            if line.strip().lower() in description.lower():
                return False
    # if re.search(r' \d{6}$', description):
    #     return True
    description = description.split(" remaining")[0]
    if "Authorization" in description or "VIN" in description:
        return False
    for word in ["Property", "located at", "Located at"]:
        description = description.replace(word, "").strip()
    if "  " in description:
        description = description.split("  ")[1].strip()

    for x in property_words:
        if x.lower() in description.lower():
            return True
    for word in non_property_words:
        if word.lower() in description.lower():
            # print(f"Found non-property word ({word}) in ({description})")
            return False
    for state, abbrv in usa_states.items():
        if state in description:
            return True
        if f" {abbrv}," in description or f" {abbrv} " in description or f" {abbrv}." in description or f",{abbrv} " in description:
            return True
    for word1, word2 in abbreviations.items():
        if word1 in description:
            return True
        if f" {word2}," in description or f" {word2} " in description or f" {word2}." in description:
            return True
    if re.search(r' \d{5}$',description):
        return True
    if getGoogleAddress(description):
        return True
    return False


if __name__ == '__main__':
    # print(isAddress("157B Pelham Lane, Monroe NJ 08831"))
    # exit()
    # processRecord({"ID": "5370861", "Docket": "267015", "Name": "Baldeon Gladys"})
    # with open('addresses.txt') as afile:
    #     for a in afile:
    #         addr = a.strip().lower()
    #         print(isAddress(addr), "|", addr)
    while True:
        try:
            main()
            break
        except:
            traceback.print_exc()
            time.sleep(60)
