import requests
from bs4 import BeautifulSoup
from requests_toolbelt.multipart.encoder import MultipartEncoder
from pydantic import BaseModel
from pydantic.main import ModelMetaclass
from datetime import datetime
import typing
from urllib.parse import urlparse
import inspect

class WebworkObjMeta(ModelMetaclass):
    _instances = {}
    _associated_clients= {}

    def __call__(cls, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = {}
        
        link = kwargs.get("link", None)
        if link is None:
            raise Exception("link is required")

        no_save = kwargs.pop("__no_save", None)
        if no_save is not None:
            return super().__call__(**kwargs)
        
        if link not in cls._instances[cls]:
            client = kwargs.pop('__webworkclient')
            cls._associated_clients[link] = client
            
            cls._instances[cls][link] = super().__call__(**kwargs)
            ins = cls._instances[cls][link]
        else:
            ins = cls._instances[cls][link]
            # updates the instance
            ins.update(**kwargs)
        return ins
        

class Webwork2Obj(BaseModel, metaclass=WebworkObjMeta):
    link : str
    name : str
    
    @property
    def _client(self):
        return self.__class__._associated_clients[self.link]
    
    def update(self, **kwargs):
        json_data = self.dict()
        json_data.update(kwargs)
        newcls = self.__class__(**json_data, __no_save=True)
        self.__dict__.update(newcls.__dict__)
        
class Section(Webwork2Obj):
    open : bool
    close : datetime = None
    
    def __init__(self, link: str, name, raw : str,**kwargs):
        # status string passed in as Open, closes 12/10/2022 at 11:59pm EST.
        # split on "closes" and then split on "at"
        splitted = raw.split(",")
        if raw == "Over time, closed." or  raw == "Completed.":
            close = None
            open = False
        else:
            open = splitted[0].strip() == "Open"
            close_split = splitted[1].strip()
            # remove complete by or close
            close_split =close_split.replace("complete by", "")
            close_split =close_split.replace("closes", "")
            close_split = close_split.strip()
            close = datetime.strptime(close_split, "%m/%d/%Y at %I:%M%p EST.")
        super().__init__(link=link, name=name, open=open, close=close, **kwargs)

    def get_problems(self):
        res = self._client._make_request(self.link)
        soup = BeautifulSoup(res.text, "html.parser")

        problems_body = soup.find("div", {"class" : "body span8"})
        if problems_body == None:
            return []
        
        problem_table = problems_body.find("table", {"class" : "problem_set_table problem_table"})
        
        problems = []
        for row in problem_table.find_all("tr")[1:]:
            """
            <th>Name</th>
            <th>Attempts</th>
            <th>Remaining</th>
            <th>Worth</th>
            <th>Status</th>"""
            cols = row.find_all("td")
            name = cols[0].find("a").text
            link = cols[0].find("a")["href"]
            attempts = int(cols[1].text)
            
            if cols[2].text.lower() == "unlimited":
                remaining = -1
            else:
                remaining = int(cols[2].text)
            worth = int(cols[3].text)
            percent = float(cols[4].text.strip("%"))
            problems.append(
                Problem(
                    link=self._client.base_url+link, 
                    name=name, 
                    attempts=attempts, 
                    remaining=remaining, 
                    worth=worth, 
                    percent_score=percent, 
                    __webworkclient=self._client
            ))
            
        return problems

        

class Problem(Webwork2Obj):
    attempts : int
    remaining : int
    worth : int
    percent_score : int
    actual_score : float
    
    def __init__(self, **kwargs) -> None:
        kwargs["actual_score"] = kwargs["percent_score"] * kwargs["worth"] / 100
        
        super().__init__(
            **kwargs,
        )

class Webwork2Client:
    def __init__(self, target :str) -> None:
        self.target = target
        self._cookie = None
        # get domain
        parsed = urlparse(target)
        self.base_url= f"{parsed.scheme}://{parsed.netloc}"

        
    def _make_request(
        self,
        url,  
        request_func = requests.get,
        query_key = False, 
        query_user = False,
        **kwargs
    ) -> requests.Response:
        if (query_key or query_user) and self._cookie is not None:
            querys = {}
            # get the first cookie from the cookie jar
            for v in self._cookie._cookies.values():
                for c in v.values():
                    for x in c.values():
                        cookie = x
                        break
                    break
                
            if query_key:
                # %09 to %09
                querys["key"] = cookie.value.split("%09")[1]
            if query_user:
                querys["user"] = cookie.value.split("%09")[0]
                querys["effectiveUser"] = cookie.value.split("%09")[0]
            
            kwargs["params"] = querys
        
        res = request_func(url, cookies=self._cookie,**kwargs)
        # get the cookie
        self._cookie = res.cookies
        return res
        
    def login(self, username, password):
        mp_encoder = MultipartEncoder(
        fields={
            "effectiveUser" : username,
            "user": username,
            "passwd": password,
        }
        )
        res = self._make_request(
            self.target, headers={'Content-Type': mp_encoder.content_type}, data=mp_encoder, request_func=requests.post
        )
        return res.status_code == 200

    def _check_ready(self):
        if self._cookie is None:
            raise Exception("Not logged in")
    
    def get_sections(self) -> typing.List[Section]: 
        self._check_ready()
        
        res = self._make_request(self.target, query_key=True, query_user=True, request_func=requests.post)
        soup = BeautifulSoup(res.text, "html.parser")
        # find class body span8 problem_set_body
        target = soup.find("div", {"class": "body span8"})
        # find problem_set_table table small-table-text
        table = target.find("table", {"class": "problem_set_table"})
        # tbody
        
        sections = []
        for tr in table.find_all("tr")[1:]:
            # td
            tds = tr.find_all("td")[1:]
            # link
            link_td =tds[0]
            
            link = link_td.find("a")["href"]
            # get title from td
            name = link_td.text
            
            # get raw status text from last
            raw = tds[-1].text

            sections.append(Section(link=self.base_url+link, name=name, raw=raw, __webworkclient=self))
        
        return sections