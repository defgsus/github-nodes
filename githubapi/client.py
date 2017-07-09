import requests
import json
import time
import re


class GithubClient(object):

    def __init__(self, auth=None):
        """Just inits class, no connection.
        auth can be a username:token tupple"""
        if auth is None:
            try:
                from .github_credentials import USERNAME, TOKEN
                auth = (USERNAME, TOKEN)
            except ImportError:
                pass
        self._auth = auth
        self._session = None
        self._response = None
        self.base_url = "https://api.github.com/"
        self._last_request_time = -1.
        # logged-in users have 5000 per hour
        self.num_requests_per_hour = 5000

    #def __del__(self):
    #    if self._session is not None:
    #        self._session.close()

    def session(self):
        if self._session is None:
            self._session = requests.session()
            self._session.headers.update({"Accept": "application/vnd.github.v3+json"})
            if self._auth:
                self._session.auth = self._auth
                resp = self._session.get(self.base_url + "user")
                if resp.status_code != 200:
                    raise RuntimeError("Login failure: %s" % resp.content)
                resp = json.loads(resp.content.decode("utf-8"))
                if "login" not in resp:
                    raise RuntimeError("Login failure: %s" % resp.content)
                print("logged in as %s" % resp["login"])
        return self._session

    @property
    def headers(self):
        """Return the last response header fields or None"""
        return self._response.headers if self._response is not None else None

    def get(self, url, params=None):
        """
        Returns the json object for the particular url.
        url is like "users/name"
        If result is a list, all pages will be queried.
        Use is_error() on result to check for api errors.
        """
        wait_sec = 10
        url = self.base_url + (url[1:] if url.startswith("/") else url)
        while True:
            data = self._get(url, params)
            if self.is_error(data):
                msg = data["message"]
                if msg.startswith("API rate limit"):
                    print("api rate limit reached, waiting %ss" % wait_sec)
                    time.sleep(wait_sec)
                    wait_sec *= 2.
                    continue
            break
        if isinstance(data, list):
            self._get_more_list(data)
        return data

    def _get(self, url, params=None):
        """Pure json response object. Use is_error() to check result"""
        print("session-get: %s" % url + (" %s" % params if params else ""))
        self.wait()
        resp = self.session().get(url, params=params)
        self._response = resp
        if resp.status_code not in (200, 204, 205):
            return {"documentation_url": "", "message": "GET failure: %s %s" % (resp.status_code, resp.content)}
        if resp.status_code == 204:
            return {"documentation_url": "", "message": "No Content"}
        return json.loads(resp.content.decode("utf-8"))

    def _get_more_list(self, data):
        """Looks for pagination in response headers and adds more objects to list in data"""
        while "Link" in self.headers:
            links = self.headers["Link"]
            match = re.search(r'<([^>]*)>;\srel="next"', links)
            if match:
                nextdata = self._get(match.groups()[0])
                if not isinstance(nextdata, list):
                    # assume error
                    data.clear()
                    data.append(nextdata)
                    break
                data += nextdata
                continue
            break

    @staticmethod
    def is_error(obj):
        return isinstance(obj, dict) and "message" in obj and "documentation_url" in obj

    def wait(self):
        wait_sec = 3600. / self.num_requests_per_hour
        while time.time() - self._last_request_time < wait_sec:
            time.sleep(wait_sec)
        self._last_request_time = time.time()
