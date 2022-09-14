import csv
import datetime
import os.path
import time
import traceback
from time import sleep

import PyPDF2
import gspread
import requests
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

import json

t = 1
timeout = 10
fieldnames = ['Docket Number', 'Case Caption', 'Court', 'Venue', 'Case Initiation Date', 'Case Type', 'Case Status',
              'Case Track', 'Judge', 'Disposition Date', 'Case Disposition', 'CaseActions']
# valid = {
#     "Case Status": "Active",
#     "Case Type": [
#         "In Rem Tax Foreclosure",
#         "In Personam Tax Foreclosure"
#     ],
#     "Docket Text": [
#         "fixing amount/time/place",
#         "Motion for final judgment",
#         "MISCELLANEOUS MOTION",
#         "Abandoned Property"
#     ],
#     "Venue": ["Bergen", "Essex", "Hudson", "Middlesex", "Monmouth", "Morris", "Passaic", "Somerset", "Union"],
# }
download_dir = rf"{os.getcwd()}\downloads"
notrequired = []
nrfile = 'notrequired.txt'
jdir = "json"
scrapedcsv = "NJ-Courts.csv"
# outcsv = "Out.csv"
changeddir = "changed"
ss = 'ss'
debug = False
headless = False
images = True
maximize = False
incognito = False
drivers = []
nj_url = 'https://portal.njcourts.gov/CIVILCaseJacketWeb/pages/civilCaseSearch.faces'
disclaimer = "https://portal.njcourts.gov/webcivilcj/CIVILCaseJacketWeb/pages/publicAccessDisclaimer.faces"

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

sheet = "https://docs.google.com/spreadsheets/d/1tAgPaFU1J5ObQWIl6AnQ69MauIsIOEP3BY6x_yGeRCI"
sheet_headers = "https://docs.google.com/spreadsheets/d/1ZPr8vrUAnnJZY1wUEBmpGNnNFP8ieEf4qKXqfMNghyM"

count = 1


def getNJactb(county, district, block, lot, district_number=None):
    try:
        print(f"Fetching records for {county}/{district}/{block}/{lot}")
        with open("njactb.json", "r") as jfile:
            disctricts = json.load(jfile)
        if district_number is None:
            try:
                if district.upper() not in disctricts[county.upper()].keys():
                    district = district.split()[0]
                district_number = disctricts[county.upper()][district.upper()]
            except:
                print(f"Invalid District {county}/{district}/{block}/{lot}")
                return None
        else:
            print(f"Got municipality code {district_number}!!")

        headers = {'User-Agent': 'Mozilla/5.0'}
        req_data = {
            'ms_user': 'monm',
            'passwd': 'data',
            'srch_type': '1',
            'select_cc': district_number,
            'district': district_number,
            'adv': '1',
            'out_type': '1',
            'ms_ln': '50',
            'p_loc': '',
            'owner': '',
            'block': block,
            'lot': lot,
            'qual': ''
        }
        response = requests.post('http://tax1.co.monmouth.nj.us/cgi-bin/inf.cgi', headers=headers, data=req_data,
                                 verify=False)
        soup = BeautifulSoup(response.text, 'lxml')
        if len(soup.find_all("a")) > 0:
            print(f"Found {len(soup.find_all('a'))} record(s) for {block}/{lot}/{district}.")
            url = f'https://tax1.co.monmouth.nj.us/cgi-bin/{soup.find_all("a")[0]["href"]}'
            print(f"Fetching data from {url}")
            content = requests.get(url).text
            soup = BeautifulSoup(content, 'lxml')
            data = {"URL": url}
            table = soup.find_all('table')
            for key, val in zip(table[0].find_all("font", {"color": "BLACK"}),
                                soup.find_all("font", {"color": "FIREBRICK"})):
                if len(key.text.strip()) > 0 and len(val.text.strip()) > 0:
                    data[key.text.strip().replace(":", "")] = val.text.strip().replace("&nbsp", "")
            ths = [td.text.strip() for td in table[1].find("tr").find_all("td")]
            data["Sr1a"] = []
            for tr in table[1].find_all("tr")[1:]:
                row = {}
                for td, th in zip(tr.find_all("td"), ths):
                    row[th] = td.text.strip() if td.find(
                        "a") is None else f'https://tax1.co.monmouth.nj.us/cgi-bin/{td.find("a")["href"]}'
                data["Sr1a"].append(row)
            data["TAX-LIST-HISTORY"] = []
            ths = [td.text.strip() for td in table[2].find_all("tr")[1].find_all("td")]
            trs = table[2].find_all("tr")[2:-1]
            for i in range(0, len(trs), 4):
                row = {}
                for td, th in zip(trs[i].find_all("td"), ths):
                    if th == "Land/Imp/Tot":
                        row[th] = [td.text.strip()]
                        row[th].append(trs[i + 1].find_all("td")[2].text.strip())
                        row[th].append(trs[i + 2].find_all("td")[2].text.strip())
                        row[th] = " | ".join(row[th])
                    elif td.text.strip() != "&nbsp":
                        row[th] = td.text.replace("&nbsp", "").strip()
                data["TAX-LIST-HISTORY"].append(row)
            # print(json.dumps(data, indent=4))
            data['GoogleAddress'] = getGoogleAddress(data['Prop Loc'], data['City State'])
            with open(f"./StateTax/{county}-{district}-{block}-{lot}-NJATCB.json", "w") as jfile:
                json.dump(data, jfile, indent=4)
            return data
        else:
            print("No data found!")
            return None
    except:
        print(f"Error {county}/{district}/{block}/{lot}")
        traceback.print_exc()
        return None


def getOcean(district, block, lot):
    try:
        print(f"Fetching records for Ocean/{district}/{block}/{lot}")
        headers = {'user-agent': 'Mozilla/5.0'}
        with open("ocean.json") as f:
            districts = json.load(f)
        district_num = districts[district.upper()]
        url = 'https://tax.co.ocean.nj.us/frmTaxBoardTaxListSearch.aspx'
        s = requests.Session()
        soup = BeautifulSoup(s.get(url, headers=headers).content, 'lxml')
        req_data = {
            '__VIEWSTATE': soup.find("input", {"id": "__VIEWSTATE"})["value"],
            '__VIEWSTATEGENERATOR': soup.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"],
            '__EVENTVALIDATION': soup.find("input", {"id": "__EVENTVALIDATION"})["value"],
            'ctl00$LogoFreeholders$FreeholderHistory$FreeholderAccordion_AccordionExtender_ClientState': '-1',
            'ctl00$MainContent$cmbDistrict': district_num,
            'ctl00$MainContent$txtBlock': block,
            'ctl00$MainContent$txtLot': lot,
            'ctl00$MainContent$btnSearch': 'Search'
        }
        response = requests.post('https://tax.co.ocean.nj.us/frmTaxBoardTaxListSearch', headers=headers, data=req_data)
        soup = BeautifulSoup(response.content, 'lxml')
        ahrefs = soup.find("table", {"id": "MainContent_m_DataTable"}).find_all("a", {"target": "_blank"})
        print(f"Found {len(ahrefs)} records")
        href = ahrefs[0]["href"]
        print(f"Working on url ({block}/{lot}) {href}")
        content = requests.get(href).content
        soup = BeautifulSoup(content, 'lxml')
        data = {"url": href}
        for table in soup.find("table", {"id": "MainContent_PulledContentTable"}).find_all("table"):
            if table.find_all("tr")[1].find("td", {"class": "PageTxtBlue"}):
                name = table.find("tr").text.strip()
                data[name] = {}
                for tr in table.find_all("tr")[1:]:
                    tds = tr.find_all("td")
                    for i in range(0, len(tds) - 1, 2):
                        if tds[i].text != "" and tds[i + 1].text != "":
                            data[name][tds[i].text.strip()] = tds[i + 1].text.strip()
            else:
                name = table.find("tr").text.strip()
                data[name] = []
                ths = [th.text.strip() for th in table.find_all("tr")[1].find_all("td")]
                for tr in table.find_all("tr")[2:]:
                    row = {}
                    for td, th in zip(tr.find_all("td"), ths):
                        row[th] = td.text.strip()
                    data[name].append(row)
        # print(json.dumps(data, indent=4))

        with open(f"StateTax/Ocean-{district}-{block}-{lot}.json", "w") as ofile:
            json.dump(data, ofile, indent=4)
        return data
    except:
        print(f"Error {district}/{block}/{lot}")
        traceback.print_exc()
        return None


def getArcGis(county, district, block, lot):
    try:
        print(f"Fetching ARCGIS records for {county}/{district}/{block}/{lot}")
        with open("arcgis.json") as f:
            districts = json.load(f)
        try:
            for dist in districts[county.upper()]:
                if dist.startswith(district.upper().split()[0]):
                    district = dist
            if district.upper() not in districts[county.upper()]:
                print(f"District not found! {county}/{district}/{block}/{lot}")
                return None
        except KeyError:
            print(f"Invalid county/district: {county}/{district}")
            return None
        countyMunicipality = f"{county.upper()} - {district.title()}"
        params = (
            ('f', 'json'),
            ('env:outSR', '102100'),
            ('countyMunicipality', countyMunicipality),
            ('block', block),
            ('queryType', 'Exact Match'),
            ('lot', lot),
        )
        url = 'https://mapsdep.nj.gov/arcgis/rest/services/Tasks/BlockLotFinder/GPServer/BlockLotFinder/execute'
        res = requests.get(url, params=params).json()
        if 'results' not in res.keys():
            print(f"No results found for {county}-{district}-{block}/{lot}")
            # print(json.dumps(res, indent=4))
            return None
        attrib = res['results'][0]['value']['features'][0]['attributes']
        for a in [k for k in attrib.keys()]:
            if attrib[a] is None:
                del attrib[a]
        # print(json.dumps(attrib, indent=4))
        with open(f"ArcGis/{county}-{district}-{block}-{lot}-ARCGIS.json", 'w') as outfile:
            json.dump(attrib, outfile, indent=4)
        return attrib
    except:
        print(f"Error {county}/{district}/{block}/{lot}")
        traceback.print_exc()
        return None


def isValidDocket(data):
    return True
    # for txt in valid["Docket Text"]:
    #     if txt.lower() in str(data).lower():
    #         return True
    # return False


def isValid(data):
    return True
    # if data["Case Status"].lower() != valid['Case Status'].lower():
    #     pprint(f"Case Status not active ({data['Case Status']})")
    #     return False
    # for ct in valid['Case Type']:
    #     if ct.lower() in data['Case Type'].lower():
    #         return True
    # pprint(f"Not required ({data['Docket Number']})")
    # return False


def processNjCourts():
    num = range(int(input("Enter starting number: ")), int(input("Enter ending number: ")) + 1)
    year = range(int(input("Enter starting year: ")), int(input("Enter ending year: ")) + 1)
    driver = getChromeDriver()
    if "portal.njcourts.gov" not in driver.current_url:
        driver.get(nj_url)
        if "Enter user ID and password" in driver.page_source:
            driver.delete_all_cookies()
            driver.get(disclaimer)
        time.sleep(3)
        checkDisclaimer(driver)
    for y in year:
        for n in num:
            if f"{y}-{n}" in notrequired:
                pprint(f"Number {n} Year {y} not required!")
                continue
            try:
                time.sleep(1)
                checkMax(driver)
                sptries = 1
                while "Search By Docket Number" not in driver.page_source:
                    pprint("Waiting for search page...")
                    sptries += 1
                    while "Enter user ID and password" in driver.page_source:
                        driver.delete_all_cookies()
                        driver.get(disclaimer)
                        time.sleep(1)
                        pprint("Reloading...")
                        checkDisclaimer(driver)
                    if sptries % 10 == 0:
                        driver.get(nj_url)
                        sptries = 1
                    sleep(1)
                fillInfo(driver, n, y)
                if "Case not found" in driver.page_source:
                    pprint("Case not found")
                else:
                    tries = 0
                    req = True
                    found = False
                    for i in range(60):
                        while "Case Caption" not in driver.page_source:
                            if "Case Caption" in driver.page_source:
                                break
                            pprint("Waiting for result page...")
                            time.sleep(1)
                            try:
                                driver.find_element(By.XPATH, '//*[@id="searchByDocForm:searchBtnDummy"]').click()
                            except:
                                traceback.print_exc()
                            tries += 1
                            if "captcha-solver-info" in driver.page_source or tries % 10 == 0:
                                try:
                                    driver.refresh()
                                    req = fillInfo(driver, n, y)
                                except:
                                    pass
                                tries = 1
                            elif "You have been logged off as your user session expired" in driver.page_source:
                                pprint("You have been logged off as your user session expired.")
                                click(driver, '//a[text()=" here"]')
                            sleep(1)
                    if not found:
                        driver.quit()
                        driver = getChromeDriver()
                    elif req:
                        getData(BeautifulSoup(driver.page_source, 'lxml'), driver, n, y)
            except:
                traceback.print_exc()
                pprint(f"Error {y} {n}")
            driver.get(nj_url)


def processBlockLot(data, row):
    print(f"Working on {row}")
    if row['county'] in ["Burlington", "Camden"]:
        data["StateTax"] = {}
    elif row['county'] == "Ocean":
        data["StateTax"] = getOcean(row['district'], row['block'], row['lot'])
    else:
        data["StateTax"] = getNJactb(row['county'], row['district'], row['block'], row['lot'])
    data['ArcGis'] = getArcGis(row['county'], row['district'], row['block'], row['lot'])


def SearchBlockLot():
    if os.path.isfile("block-lot.csv"):
        with open("block-lot.csv", 'r') as infile:
            reader = csv.DictReader(infile)
            data = {}
            for row in reader:
                processBlockLot(data, row)
    else:
        print("No block-lot.csv file found")


def initialize():
    global notrequired
    logo()
    for directory in [jdir, changeddir, 'StateTax', 'ArcGis',
                      # "notreq", ss
                      ]:
        if not os.path.isdir(directory):
            os.mkdir(directory)
    if not os.path.isfile(nrfile):
        with open(nrfile, 'w') as nfile:
            nfile.write("")
    if not os.path.isfile(scrapedcsv):
        with open(scrapedcsv, 'w', newline='', encoding='utf8') as sfile:
            csv.DictWriter(sfile, fieldnames=fieldnames).writeheader()
    with open(nrfile) as nfile:
        notrequired = nfile.read().splitlines()


def main():
    initialize()
    option = input("1 to get cases from NJ Courts\n2 to search state/district/block/lot:")
    if option == "1":
        processNjCourts()
        CategorizeJson()
        uploadCSV(sheet_headers, scrapedcsv)
    elif option == "2":
        SearchBlockLot()
    else:
        print("Invalid option")


def checkMax(driver):
    while "maximum number of concurrent users." in driver.page_source:
        pprint("Case Jacket Public Access has reached the maximum number "
               "of concurrent users. Please try again later.")
        driver.get(nj_url)
        time.sleep(1)


def fillInfo(driver, n, y):
    if f"{y}-{n}" in notrequired:
        pprint(f"Number {n} Year {y} not required!")
        return False
    pprint(f"Number {n} Year {y}")
    sendkeys(driver, '//*[@id="searchByDocForm:idCivilDocketNum"]', n)
    sendkeys(driver, '//*[@id="searchByDocForm:idCivilDocketYear"]', y)
    time.sleep(1)
    if waitCaptcha(driver):
        sendkeys(driver, '//*[@id="searchByDocForm:idCivilDocketNum"]', n)
        sendkeys(driver, '//*[@id="searchByDocForm:idCivilDocketYear"]', y)
        time.sleep(1)
    try:
        driver.find_element(By.XPATH, '//*[@id="searchByDocForm:searchBtnDummy"]').click()
    except:
        pprint("Search page captcha manually solved!")
    time.sleep(2)
    return True


def checkDisclaimer(driver):
    time.sleep(1)
    while "Disclaimer" in driver.page_source:
        time.sleep(1)
        waitCaptcha(driver)
        try:
            driver.find_element(By.XPATH, '//*[@id="disclaimerform:button"]').click()
        except:
            pprint("Disclaimer captcha manually solved!")
        time.sleep(1)


def getData(soup, driver, n, y):
    data = {
        "Docket Number": soup.find('span', {"id": "CaseNumberTitlePanel"}).text.split(":")[1].strip(),
        "Case Caption": soup.find('span', {"id": "idCaseTitle"}).text,
    }
    for td in soup.find("table", {"id": "caseSummaryPanel_F"}).find_all("td"):
        try:
            data[td.find('span', {"class": "ValueField"}).text.strip().replace(":", "")] = td.find('span', {
                "class": "LabelField"}).text.strip()
        except:
            # print("error", td)
            pass
    tabs_data = {}
    downloadPdf(driver)
    for li in soup.find('ul', {"role": "tablist"}).find_all("li", {"role": "tab"}):
        tab = li.text.split('\u00a0')[0].strip()
        tabs_data[tab] = []
        li_div = soup.find('div', {"id": li["aria-controls"]})
        for h3 in li_div.find_all('h3', {"role": "tab"}):
            h3_div = soup.find('div', {"id": h3["aria-controls"]})
            h3_txt = h3.find('span', {"class": "LabelField"}).text
            tab_data = {"Label": h3_txt.strip()}
            for val, label in zip(h3_div.find_all('span', {"class": "ValueField"}),
                                  h3_div.find_all('span', {"class": "LabelField"})):
                tab_data[val.text.strip().replace(":", "")] = label.text.strip()
            if tab == "Properties":
                county = tab_data["County"]
                district = tab_data["Municipality"].split("-")[1].strip()
                label = tab_data["Label"].split()
                block = label[1]
                lot = label[-1]
                if county in ["Burlington", "Camden"]:
                    tab_data["StateTax"] = {}
                elif county == "Ocean":
                    tab_data["StateTax"] = getOcean(district, block, lot)
                else:
                    tab_data["StateTax"] = getNJactb(county, district, block, lot,
                                                     tab_data["Municipality"].split("-")[0].strip())
                tab_data['ArcGis'] = getArcGis(county, district, block, lot)
                tab_data['CourtNormalizedAddress'] = getGoogleAddress(tab_data["Street Address"], county, district)
                tab_data[
                    'CourtAddress'] = f"{tab_data['Street Address']},{tab_data['Municipality']}, {tab_data['County']}"

                tab_data["Label"] = tab_data["Label"].replace(":", "")
            tabs_data[tab].append(tab_data)
    if tabs_data["Properties"]:
        property0 = tabs_data["Properties"][0]
        data['StateTaxOwner'] = property0['StateTax']['Owner']
        data['CourtAddress'] = property0['CourtAddress']
        data['CourtNormalizedAddress'] = property0['CourtNormalizedAddress']
        state_tax_addr = f"{property0['StateTax']['Street']}, {property0['StateTax']['City State']}"
        data['StateTaxAddress'] = state_tax_addr
        data['StateTaxNormalizedAddress'] = getGoogleAddress(state_tax_addr)
    data["Tabs"] = tabs_data
    data['CaseActions'] = []
    table = soup.find('table', {"id": "caseActionTbId2"})
    ths = [th.text for th in table.find_all('th')]
    for tr in table.find_all('tr'):
        tds = [td.text for td in tr.find_all("td")]
        case = {}
        for i in range(len(ths)):
            try:
                case[ths[i].strip().replace(":", "")] = tds[i].strip()
            except:
                pass
        if case != {}:
            data['CaseActions'].append(case)
    # pprint(json.dumps(data, indent=4))
    jf = f"./{jdir}/{y}-{n}.json"
    if isValid(data):
        if isValidDocket(data):
            if os.path.isfile(jf):
                with open(jf) as jfile:
                    jdata = json.load(jfile)
                if jdata == data:
                    pprint("Nothing changed!")
                else:
                    pprint("Data changed!")
                    changefile = f"./{changeddir}/{y}-{n}--{str(datetime.datetime.now()).replace(':', '-')}.json"
                    with open(changefile, 'w') as jfile:
                        json.dump(data, jfile, indent=4)
                    with open(jf, 'w') as jfile:
                        json.dump(data, jfile, indent=4)
                    createCsv(data)
            # try:
            #     driver.find_element(By.TAG_NAME, 'body').screenshot(f"./{ss}/{data['Docket Number']}.png")
            # except:
            #     pass
            else:
                with open(jf, 'w') as jfile:
                    json.dump(data, jfile, indent=4)
                createCsv(data)
        else:
            pprint(f"Not required docket {data['Docket Number']}")
            with open(jf.replace(jdir, "notreq") + ".json", 'w') as jfile:
                json.dump(data, jfile, indent=4)
    else:
        with open(nrfile, 'a') as nfile:
            nfile.write(f"{y}-{n}\n")
        notrequired.append(f"{y}-{n}")
        pprint(f"Not required {data['Docket Number']}")
        with open(jf.replace(jdir, "notreq") + ".json", 'w') as jfile:
            json.dump(data, jfile, indent=4)
    downloaded = False
    for i in range(10):
        time.sleep(1)
        if os.path.isfile(rf"{download_dir}\CivilCaseJacket.pdf"):
            downloaded = True
            break
        print(f"Downloading CivilCaseJacket.pdf ({i})...")
    if downloaded:
        print(f"CivilCaseJacket.pdf downloaded!, renaming to {y}-{n}.pdf")
        os.rename(rf"{download_dir}/CivilCaseJacket.pdf", rf"{download_dir}/{y}-{n}.pdf")
    else:
        print("Error downloading CivilCaseJacket.pdf")
    return data


def createCsv(data):
    with open(scrapedcsv, 'a', newline='', encoding='utf8') as sfile:
        csv.DictWriter(sfile, fieldnames=fieldnames, extrasaction='ignore').writerow(data)


def uploadCSV(sht, csv_file):
    # global count
    # if count % 5 == 0:
    pprint("Uploading CSV..")
    credentials = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', SCOPES)
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_url(sht)
    with open(csv_file, 'r') as file_obj:
        content = file_obj.read()
        client.import_csv(spreadsheet.id, data=content)
    pprint(f"{csv_file} uploaded to {sht}")
    # count += 1


def create():
    spreadsheet_details = {
        'properties': {
            'title': 'NJ-Court'
        }
    }
    credentials = service_account.Credentials.from_service_account_file('client_secret.json', scopes=SCOPES)
    spreadsheet_service = build('sheets', 'v4', credentials=credentials)
    drive_service = build('drive', 'v3', credentials=credentials)
    sht = spreadsheet_service.spreadsheets().create(body=spreadsheet_details, fields='spreadsheetId').execute()
    sheetId = sht.get('spreadsheetId')
    pprint('Spreadsheet ID: {0}'.format(sheetId))
    permission1 = {
        'type': 'user',
        'role': 'writer',
        'emailAddress': '786hassan777@gmail.com'
    }
    drive_service.permissions().create(fileId=sheetId, body=permission1).execute()
    # print(sheetId)


def CategorizeJson():
    casetypes = ['Residential', 'Personam', 'Rem', 'Commercial', 'STRICT', 'Condominium', 'Time Share', 'FAIR']
    for file in os.listdir(jdir):
        if file.endswith(".json"):
            with open(f"./{jdir}/{file}") as jfile:
                data = json.load(jfile)
            found = False
            for casetype in casetypes:
                if casetype.lower() in data['Case Type'].lower():
                    found = True
                    print(f"'{casetype}' found in ({data['Case Type']}) ({data['Docket Number']})")
                    if not os.path.isdir(f"./{jdir}/{casetype}"):
                        os.mkdir(f"./{jdir}/{casetype}")
                    with open(f"./{jdir}/{casetype}/{file}", 'w') as jfile:
                        json.dump(data, jfile, indent=4)
            if not found:
                print(f"Nothing found ({data['Case Type']}) ({data['Docket Number']})")
                if not os.path.isdir(f"./{jdir}/Other"):
                    os.mkdir(f"./{jdir}/Other")
                with open(f"./json/Other/{file}", 'w') as nfile:
                    json.dump(data, nfile, indent=4)


def waitCaptcha(driver):
    time.sleep(5)
    fillagain = False
    captchacount = 1
    while "Captcha solved!" not in driver.page_source and "captcha-solver-info" in driver.page_source:
        pprint(f"Solving captcha ({captchacount})....")
        captchacount += 1
        if captchacount > 60:
            pprint("Reloading...")
            driver.refresh()
            sleep(3)
            captchacount = 1
            fillagain = True
        sleep(1)
    sleep(1)
    return fillagain


def pprint(msg):
    m = f'{str(datetime.datetime.now()).split(".")[0]} | {msg}'
    print(m)
    # with open("logs.txt", 'a') as logfile:
    #     logfile.write(m + "\n")


def logo():
    os.system('color 0a')
    print(r"""
           _  __    __  _____                 __     
          / |/ /__ / / / ___/___  __ __ ____ / /_ ___
         /    // // / / /__ / _ \/ // // __// __/(_-<
        /_/|_/ \___/  \___/ \___/\_,_//_/   \__//___/
===============================================================
                   NJ Court data scraper by:
                http://github.com/evilgenius786
===============================================================
[+] Automated
[+] Solves captcha using 2captcha
[+] JSON output
[+] CSV output
[+] Alert on new data
[+] Error handling
_______________________________________________________________
""")


def click(driver, xpath, js=False):
    if js:
        driver.execute_script("arguments[0].click();", getElement(driver, xpath))
    else:
        WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath))).click()


def getText(driver, xpath):
    try:
        return getElement(driver, xpath).text.strip()
    except:
        return ""


def getElement(driver, xpath):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))


def sendkeys(driver, xpath, keys, js=False):
    if js:
        driver.execute_script(f"arguments[0].value='{keys}';", getElement(driver, xpath))
    else:
        ele = getElement(driver, xpath)
        ele.clear()
        ele.send_keys(keys)


def getChromeDriver(proxy=None):
    options = webdriver.ChromeOptions()
    if debug:
        # print("Connecting existing Chrome for debugging...")
        options.debugger_address = "127.0.0.1:9222"
    else:

        print("PDF Download directory: " + download_dir)
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
        options.add_experimental_option('prefs', {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True
        })
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument('--user-data-dir=C:/selenium/ChromeProfile')
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
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def getFirefoxDriver():
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


def ValidityTest():
    for file in os.listdir("./test1"):
        with open(f"./test1/{file}") as jfile:
            data = json.load(jfile)
            # pprint(json.dumps(data, indent=4))
            if isValid(data):
                if isValidDocket(data):
                    print(f"Valid {file}")
                else:
                    print(f"Valid but Not required docket {file}")
            else:
                print(f"Not required {file}")


def check():
    initialize()
    print("Testing mode...")
    n = "22"
    y = "22"
    driver = getChromeDriver()
    getData(BeautifulSoup(driver.page_source, 'lxml'), driver, n, y)
    # print(json.dumps(data, indent=4))
    # with open(f'{y}-{n}.json', 'w') as jfile:
    #     json.dump(data, jfile, indent=4)


def getGoogleAddress(street, county="", district=""):
    addr = f"{street} {county} {district}"
    url = f"https://www.google.com/search?q={addr}"
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"
    soup = BeautifulSoup(requests.get(url, headers={'user-agent': ua}).text, 'lxml')
    try:
        return soup.find("div", class_="vk_sh vk_bk").text
    except:
        print(f"No address found {url}")
        print(soup)
        return ""


def TranslateCodeToMunicipality(code):
    with open("Municipality.json") as jfile:
        data = json.load(jfile)
        if code in data:
            return data[code]
        else:
            print("Code not found!!")
            return code


def pdftoText(file):
    with open(file, 'rb') as pdfFileObj:
        pdfReader = PyPDF2.PdfFileReader(pdfFileObj)
        text = ""
        for page in range(pdfReader.numPages):
            pageObj = pdfReader.getPage(page)
            text += (pageObj.extractText())
        print(text)


def downloadPdf(driver):
    if os.path.isfile(rf"{download_dir}/CivilCaseJacket.pdf"):
        print("Deleting old PDF!!")
        os.remove(rf"{download_dir}/CivilCaseJacket.pdf")
    # driver = getChromeDriver()
    table = driver.find_element(By.XPATH, "//table[@id='caseActionTbId2']")
    for tr in table.find_elements(By.XPATH, './/tr[@role="row"]')[1:]:
        # print(tr.text)
        if tr.find_element(By.XPATH, './/td[@class="caseActCol3"]').text.startswith("Complaint"):
            # print(tr.find_element(By.XPATH, './/td[@class="caseActCol3"]').text)
            tr.find_element(By.XPATH, './/td[@class="caseActCol2"]/a').click()
            time.sleep(1)
            form = driver.find_element(By.XPATH, '//form[@id="documentDetails"]')
            form.find_element(By.XPATH, './/input[@type="checkbox"]').click()
            time.sleep(3)
            driver.find_element(By.XPATH, '//input[@id="documentDetails:savePrintButton"]').click()
            time.sleep(1)


if __name__ == "__main__":
    # downloadPdf(getChromeDriver())
    # check()
    # pdftoText("CivilCaseJacket.pdf")
    main()
    # for pdf_file in os.listdir("downloads"):
    #     if pdf_file.endswith(".pdf"):
    #         pdftoText(f"downloads/{pdf_file}")
