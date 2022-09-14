import os.path

import json

import requests
from bs4 import BeautifulSoup

s = requests.Session()


def getOcean(district, block, lot):
    headers = {'user-agent': 'Mozilla/5.0'}
    with open("ocean.json") as f:
        districts = json.load(f)
    district_num = districts[district.upper()]
    print(f"Fetching records for Ocean/{district}/{block}/{lot}")
    url = 'https://tax.co.ocean.nj.us/frmTaxBoardTaxListSearch.aspx'
    soup = BeautifulSoup(s.get(url, headers=headers).content, 'lxml')
    data = {
        '__VIEWSTATE': soup.find("input", {"id": "__VIEWSTATE"})["value"],
        '__VIEWSTATEGENERATOR': soup.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"],
        '__EVENTVALIDATION': soup.find("input", {"id": "__EVENTVALIDATION"})["value"],
        'ctl00$LogoFreeholders$FreeholderHistory$FreeholderAccordion_AccordionExtender_ClientState': '-1',
        'ctl00$MainContent$cmbDistrict': district_num,
        'ctl00$MainContent$txtBlock': block,
        'ctl00$MainContent$txtLot': lot,
        'ctl00$MainContent$btnSearch': 'Search'
    }
    response = requests.post('https://tax.co.ocean.nj.us/frmTaxBoardTaxListSearch', headers=headers, data=data)
    soup = BeautifulSoup(response.content, 'lxml')
    ahrefs = soup.find("table", {"id": "MainContent_m_DataTable"}).find_all("a", {"target": "_blank"})
    print(f"Found {len(ahrefs)} records")
    href=ahrefs[0]["href"]
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
    print(json.dumps(data, indent=4))
    with open(f"json/Ocean-{district}-{block}-{lot}.json", "w") as ofile:
        json.dump(data, ofile, indent=4)



def main():
    if not os.path.isdir("json"):
        os.mkdir("json")
    getOcean("BARNEGAT",'1', '1')


if __name__ == '__main__':
    main()
