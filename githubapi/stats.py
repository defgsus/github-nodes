
class Stats(object):

    def __init__(self, name, attr):
        self.name = name
        self.objects = []
        self.stats_sum = dict(attr)

    def dump(self):
        ret = ""
        if len(self.objects) > 1:
            ret += "num %s: %s\n" % (self.name, len(self.objects))
        else:
            ret += "%s\n" % self.name
        for key in sorted(self.stats_sum):
            ret += "%20s: %s\n" % (key, self.stats_sum[key])
        print(ret)
        return ret

    def add_object(self, obj):
        assert isinstance(obj, dict)
        self.objects.append(obj)
        for key in self.stats_sum:
            cur_val = self.stats_sum[key]
            if isinstance(cur_val, (int, float)):
                self.stats_sum[key] += obj.get(key, 0)
            elif isinstance(cur_val, list):
                self.stats_sum[key].append(obj.get(key))
            else:
                if len(self.objects) == 1:
                    self.stats_sum[key] = obj.get(key)
                else:
                    self.stats_sum[key] = [cur_val, obj.get(key)]

    def add_objects(self, objs):
        for i in objs:
            self.add_object(i)


class RepoStats(Stats):
    def __init__(self, name=None):
        super().__init__(name or "repositories", {
            'stargazers_count': 0,
            'open_issues_count': 0,
            'watchers_count': 0,
            'forks_count': 0,
            'size': 0,
        })


class OrganisationStats(Stats):
    def __init__(self, name=None):
        super().__init__(name or "organisations", {
            'name': '',
            'url': '',
            'location': '',
            'blog': '',
            'description': '',
            'public_repos': 0,
            'followers': 0,
            'following': 0,
            'public_gists': 0,
            'created_at': '',
            'updated_at': '',
        })

class UserStats(Stats):
    def __init__(self, name=None):
        super().__init__(name or "users", {
            'name': '',
            'url': '',
            'location': '',
            'company': '',
            'bio': '',
            'blog': '',
            'followers': 0,
            'following': 0,
            'public_repos': 0,
            'created_at': '',
            'updated_at': '',
        })
