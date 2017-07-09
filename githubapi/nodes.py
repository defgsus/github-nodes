import math
from .api import Github


class GithubNodes(object):
    """
    Node/Edge container feeding from github queries
    """

    # edge types
    E_MEMBER_OF = "member"
    E_CONTRIBUTES_TO = "contributes"
    E_OWNS = "owns"
    E_FORKED = "forked"
    E_PUSHED_TO = "pushed"
    E_COMMENTED_ON = "commented"
    E_FORK_OF = "forkof"

    class Node:
        """
        Node in the graph
        obj represents the github data
        """
        def __init__(self, id, obj, _p):
            self.id = id
            self.obj = obj
            self._p = _p
        def __hash__(self): return hash(self.id)
        def __repr__(self): return self.id
        def is_user(self): return self.id.startswith("u:")
        def is_org(self): return self.id.startswith("o:")
        def is_repo(self): return self.id.startswith("r:")
        def is_error(self): return "error" in self.obj
        def edges_in(self): return [self._p.edges[e] for e in self._p.edges if self._p.edges[e].to_node == self]
        def edges_out(self): return [self._p.edges[e] for e in self._p.edges if self._p.edges[e].from_node == self]
        def edges(self): return self.edges_in() + self.edges_out()
        def __getitem__(self, item): return self.obj[item]
        def get(self, key, defaultval=None): return self.obj.get(key, defaultval)

    class Edge:
        def __init__(self, from_node, to_node, type, strength=None):
            self.from_node = from_node
            self.to_node = to_node
            self.types = { type }
            self.strength = 1. if strength is None else strength
        def __hash__(self): return hash((self.from_node, self.to_node))
        def __repr__(self): return "(%s %s %s)" % (self.from_node, "/".join(self.types), self.to_node)
        def is_owner(self): return GithubNodes.E_OWNS in self.types
        def is_contributer(self): return GithubNodes.E_CONTRIBUTES_TO in self.type
        def is_member(self): return GithubNodes.E_MEMBER_OF in self.types

    def __init__(self, github_api=None, follow_depth=1):
        self.git = github_api or Github()
        self.nodes = dict()
        self.edges = dict()
        self.follow_depth = follow_depth
        self.follow_forks = False

    def dump(self):
        print("NODES:\n", list(self.nodes.values()))
        print("EDGES:\n", list(self.edges.values()))

    def add_user_or_org(self, login, follow_depth=None):
        if "u:" + login in self.nodes:
            return self.nodes["u:" + login]
        if "o:" + login in self.nodes:
            return self.nodes["o:" + login]
        if self.git.is_organisation(login):
            return self.add_organisation(login, follow_depth)
        else:
            return self.add_user(login, follow_depth)

    def add_user(self, login_or_user, follow_depth=None):
        user_node, created = self._add_node(
            "u:", login_or_user,
            lambda: login_or_user["login"],
            lambda: self.git.get_user(login_or_user),
        )
        if not created:
            return user_node

        follow_depth = self.follow_depth if follow_depth is None else follow_depth
        if follow_depth > 0:
            follow_depth = follow_depth - 1
            self._add_repos(user_node, follow_depth)
            self._add_events(user_node, follow_depth)

        return user_node

    def add_repo(self, repo_or_full_name, follow_depth=None):
        def _get_repo():
            assert "/" in repo_or_full_name
            repo_user, repo_name = repo_or_full_name.split("/")
            repo = self.git.get_repo(repo_user, repo_name)
            # replace with source if it's a fork
            if repo and repo.get("fork") and "source" in repo:
                repo = self.git.get_repo(repo["source"]["full_name"])
            if repo is None:
                repo = {
                    "full_name": repo_name,
                    "error": "not found",
                }
            return repo

        repo_node, created = self._add_node(
            "r:", repo_or_full_name,
            lambda: repo_or_full_name["full_name"],
            _get_repo,
        )
        if not created:
            return repo_node

        follow_depth = self.follow_depth if follow_depth is None else follow_depth
        if follow_depth > 0:
            follow_depth = follow_depth - 1

            if "owner" in repo_node.obj:
                if repo_node["owner"].get("type", "") == "Organization":
                    owner = self.add_organisation(repo_node["owner"]["login"], follow_depth)
                else:
                    owner = self.add_user(repo_node["owner"]["login"], follow_depth)
                if owner is not None:
                    self._add_edge(
                        owner,
                        repo_node,
                        GithubNodes.E_FORKED if repo_node.get("fork") else GithubNodes.E_OWNS)

            # TODO: sometimes this objects is incomplete??
            if "id" in repo_node.obj:
                contribs = self.git.get_repo_contributors(repo_node.obj)
                if contribs:
                    sum_contribs = max(1., sum(c["contributions"] for c in contribs))
                    for user in contribs:
                        contributor_node = self.add_user(user["login"], follow_depth)
                        if contributor_node:
                            norm_contribs = user["contributions"] / sum_contribs
                            self._add_edge(
                                contributor_node,
                                repo_node,
                                GithubNodes.E_CONTRIBUTES_TO,
                                norm_contribs)
        return repo_node

    def add_organisation(self, login_or_org, follow_depth=None):
        org_node, created = self._add_node(
            "o:", login_or_org,
            lambda: login_or_org["login"],
            lambda: self.git.get_organisation(login_or_org),
        )
        if not created:
            return org_node

        follow_depth = self.follow_depth if follow_depth is None else follow_depth
        if follow_depth > 0:
            follow_depth = follow_depth - 1

            self._add_repos(org_node, follow_depth)
            self._add_events(org_node, follow_depth)

            members = self.git.get_organisation_members(org_node["login"])
            if members:
                for user in members:
                    self._add_edge(
                        self.add_user_or_org(user["login"], follow_depth),
                        org_node,
                        GithubNodes.E_MEMBER_OF)
        return org_node

    def _add_repos(self, user_node, follow_depth):
        repos = self.git.get_repo_list(user_node["login"])
        if repos:
            #repos = [r for r in repos if not r.get("fork", False)]
            for repoitem in repos:
                if repoitem.get("fork") and not self.follow_forks:
                    continue
                repo = self.git.get_repo(repoitem["full_name"])
                if repo:
                    self._add_edge(
                        user_node,
                        self.add_repo(repo, follow_depth),
                        GithubNodes.E_FORKED if repo.get("fork") else GithubNodes.E_OWNS
                    )

    def _add_events(self, user_node, follow_depth):
        event_mapping = {
            "PushEvent": GithubNodes.E_PUSHED_TO,
            "IssueCommentEvent": GithubNodes.E_COMMENTED_ON,
        }
        events = self.git.get_events(user_node["login"])
        if events:
            for event in events:
                if event["type"] in event_mapping.keys():
                    if "repo" in event:
                        repo_name = event["repo"]["name"]
                        repo_node = self.add_repo(repo_name, follow_depth - 1)
                        self._add_edge(user_node, repo_node, event_mapping[event["type"]])

    def _add_node(self, node_id_prefix, obj_or_str, id_fallback, obj_fallback):
        if isinstance(obj_or_str, str):
            node_id = node_id_prefix + obj_or_str
            if node_id in self.nodes:
                return self.nodes[node_id], False
            obj = obj_fallback()
        else:
            node_id = node_id_prefix + id_fallback()
            if node_id in self.nodes:
                return self.nodes[node_id], False
            obj = obj_or_str
        if obj is None:
            return None, False

        node = GithubNodes.Node(node_id, obj, self)
        self.nodes[node_id] = node
        return node, True

    def _add_edge(self, from_node, to_node, type, strength=None):
        key = (from_node.id, to_node.id)
        if strength is None:
            strength = 1.
            if type in (GithubNodes.E_FORKED, GithubNodes.E_COMMENTED_ON):
                strength = .1
        # if edge exists just update values
        if key in self.edges:
            self.edges[key].types.add(type)
            #self.edges[key].strength = max(self.edges[key].strength, strength)
            self.edges[key].strength += strength
            return self.edges[key]
        edge = GithubNodes.Edge(from_node, to_node, type, strength)
        self.edges[key] = edge
        return edge


