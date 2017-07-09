import pymongo

from .client import GithubClient


class Github(object):
    """
    Returns raw json objects from github v3
    Uses mongo-db for caching.
    /github/cache/
        user/{"login"}                      : user object identified by "login"
        org/{"login"}                       : organisation object
        repo/{"login", "name"}              : repository object per owner login and repo name
        repos/{"login"}                     : list of repositories per user/org
        events/{"login"}                    : list of events per user/org
        members/{"login"}                   : list of members per org
        contributors/{"login", "name"}      : list of contributors per user/org and short repo name
    """
    def __init__(self, use_cache=True, use_network=True):
        self._db_client = pymongo.MongoClient()
        self._cache = self._db_client["github"]["cache"]
        self.use_cache = use_cache
        self.use_network = use_network
        self._net_client = None
        self._ignore_cach = set()

    def __del__(self):
        del self._cache
        del self._db_client

    def clear_cache(self, table, db_query=None):
        """
        removes the cache for the given entry. 
        e.g.: clear_cache("user", {"login": "Johannes"})
        """
        if db_query is not None:
            self._cache[table].delete_many(db_query)
        else:
            self._cache[table].drop()

    def is_user(self, login_name):
        """Returns true if `login_name` is the login of a regular git user"""
        if self.is_organisation(login_name):
            return False
        if self.get_user(login_name):
            return True
        return False

    def is_organisation(self, login_name):
        """Returns true if `login_name` is the login of a regular git organisation"""
        if self.get_organisation(login_name):
            return True
        return False

    def get_user(self, login_name):
        """Returns the user json object, or None"""
        return self._get_cached_url(
            "users/%s" % login_name,
            "user", {"login": login_name}
        )

    def get_organisation(self, login_name):
        """
        Returns the organisation json object, or None.
        Note that organisations and users are almost the same.
        Keydifferences are like: organisations have a `member_url` entry
        """
        return self._get_cached_url(
            "orgs/%s" % login_name,
            "org", {"login": login_name}
        )

    def get_events(self, login_name):
        """
        Returns a list of events for the organisation or user, or None
        """
        def _transform(event):
            if "actor" in event:
                del event["actor"]  # remove the redundant user entry
            if "org" in event:
                del event["org"]
            return event
        return self._get_cached_list_url(
            "%s/%s/events" % (
                "orgs" if self.is_organisation(login_name) else "users", login_name),
            "events", {"login": login_name},
            transform=_transform
        )

    def get_organisation_members(self, login_name):
        """
        Returns a list of user objects, or None
        """
        orgdata = self.get_organisation(login_name)
        if orgdata is not None:
            mem_url = orgdata.get("members_url", "").split("{")[0]
            if mem_url:
                return self._get_cached_list_url(
                    mem_url,
                    "members", {"login": login_name}
                )
        return None

    def get_repos(self, login_name):
        repolist = self.get_repo_list(login_name)
        if repolist is not None:
            repos = []
            for repoitem in repolist:
                repo = self.get_repo(repoitem["full_name"])
                if repo is not None:
                    repos.append(repo)
            return repos
        return None

    def get_repo_list(self, login_name):
        """
        Returns a list of repository identifier objects for a user or organisation, or None
        The returned objects will contain the fields `login`, `name`, `fullname`, `fork`
        """
        return self._get_cached_list_url(
            "%s/%s/repos" % (
                "orgs" if self.is_organisation(login_name) else "users", login_name),
            "repos", {"login": login_name},
            transform=self._get_repo_info
        )

    def get_repo(self, login_or_full_name, name=None):
        """
        Returns a single repository object
        :param login_or_full_name: either "owner/reponame" or "owner"
        :param name: either "reponame" or None
        :return: A repository json object, or None
        """
        def _transform(r):
            for key in ("source", "parent"):
                if key in r:
                    r[key] = self._get_repo_info(r[key])
            return r
        if name is None:
            assert "/" in login_or_full_name
            login_name, name = login_or_full_name.split("/")
        else:
            login_name = login_or_full_name
        return self._get_cached_url(
            "repos/%s/%s" % (login_name, name),
            "repo", {"login": login_name, "name": name},
            transform=_transform
        )

    def get_repo_contributors(self, repo_or_full_name):
        """
        Returns list of contributers to a repository, or None
        :param repo_or_full_name: either a repository json object or a full name, e.g. "owner/name"
        """
        if isinstance(repo_or_full_name, str):
            repo = self.get_repo(repo_or_full_name)
            full_name = repo_or_full_name
        else:
            repo = repo_or_full_name
            full_name = repo["full_name"]
        if repo is None:
            return None
        return self._get_cached_list_url(
            "repos/%s/%s/contributors" % tuple(full_name.split("/")),
            "contributors",
            {"login": full_name.split("/")[0], "name": full_name.split("/")[1]},
            lambda r: {key: r[key] for key in ("login", "id", "contributions")},
        )

    def get_url(self, api_path, params=None):
        ret = self._get_url(api_path, params)
        if isinstance(ret, dict) and list(ret.keys()) == ["list"]:
            return ret["list"]
        return ret

    def _store_cache(self, table, obj, replace_filter=None):
        if replace_filter is not None:
            if self._cache[table].replace_one(replace_filter, obj).matched_count > 0:
                print("replace-cache: %s %s" % (table, replace_filter))
                return
        print("store-cache: %s %s" % (table, replace_filter))
        self._cache[table].insert_one(obj)

    @staticmethod
    def _get_repo_info(repo):
        login = repo.get("owner", {}).get("login")
        name = repo.get("name", "")
        return {
            "login": login,
            "name": name,
            "full_name": login + "/" + name,
            "fork": repo.get("fork", False),
        }

    def _get_cache(self, table, query):
        data = self._cache[table].find_one(query)
        if data is None:
            pass  # print("cache-not-found: %s %s" % (table, query))
        else:
            print("read-cache: %s %s" % (table, query))
        return data

    def _get_url(self, url, params=None, transform=None):
        if self._net_client is None:
            self._net_client = GithubClient()
        data = self._net_client.get(url, params)
        if isinstance(data, list):
            if transform is not None:
                data = [transform(y) for y in data]
            return {"list": data}
        if GithubClient.is_error(data):
            return {"ERROR": data["message"]}
        return transform(data) if transform is not None else data

    def _get_cached_url(self, url, table, db_query, transform=None):
        if not self.use_cache and not self.use_network:
            return None
        use_cache = self.use_cache
        data = self._get_cache(table, db_query) if use_cache else None
        if data is None and self.use_network:
            data = self._get_url(url, transform=transform)
            data.update(db_query)
            self._store_cache(table, data, db_query)
        if data and "ERROR" in data:
            return None
        return data

    def _get_cached_list_url(self, url, table, db_query, transform=None):
        data = self._get_cached_url(url, table, db_query, transform)
        return data["list"] if data and "list" in data is not None else None

