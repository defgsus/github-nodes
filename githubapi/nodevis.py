import math, os


class NodeVis(object):

    def __init__(self, nodes):
        self.nodes = nodes
        self.rest_length = 20.

    def vis_nodes(self):
        ret = []
        for node in self.nodes.nodes.values():
            entry = {
                "id": node.id,
                "label": node.get("name") or node.get("full_name") or node.get("login") or node["id"],
            }
            if node.is_user() or node.is_org():
                entry.update({
                    "shape": "circularImage",
                    "image": node.get("avatar_url"),
                    "font": {"vadjust": -10},
                    "color": "#bcf",
                })
            if node.is_repo():
                entry.update({
                    "shape": "box",
                    "color": "#cec",
                })
            if node.is_error():
                entry.update({
                    "color": "#f0f0f0",
                })
            ret.append(entry)
        return ret

    def vis_edges(self):
        ret = []
        for edge in self.nodes.edges.values():
            num1 = len(edge.from_node.edges())
            num2 = len(edge.to_node.edges())
            length = self.rest_length * (1.+1.5*(math.sqrt(num1) + math.sqrt(num2)))
            length = max(length, length / (.5 + edge.strength))
            color = "#eee"
            if edge.is_member():
                color = "#bcf"
            if edge.is_owner():
                color = "#cec"
            entry = {
                "from": edge.from_node.id,
                "to": edge.to_node.id,
                "label": "/".join(sorted(edge.types)),
                "font": {"size": 7},
                "length": length,
                "color": color,
            }
            ret.append(entry)
        return ret

    def vis_infos(self):
        infos = dict()
        for node in self.nodes.nodes.values():
            info = []
            def _addinfo(*ids):
                for i in ids:
                    if i in node.obj and node[i]:
                        info.append("%s: %s" % (i, node[i]))
            if node.is_error():
                info += ["error: %s" % node.id]
            _addinfo("created_at", "updated_at")
            if node.is_user():
                info += ["user: %s" % (node.get("name") or node.get("full_name") or node.get("login") or node["id"])]
            if node.is_org():
                info += ["organisation: %s" % node["name"]]
            if node.is_user() or node.is_org():
                _addinfo("id", "login", "type", "hireable", "location", "company", "email", "bio",
                         "public_repos", "private_repos", "disk_usage", "following", "followers")
            if node.is_repo():
                info += ["repo: %s" % node["full_name"]]
                _addinfo("fork", "stargazers_count", "open_issues_count", "forks_count", "size", "description")
            for i in ("html_url", "blog"):
                if i in node.obj and node[i]:
                    info = ['<a href="%s">%s</a>' % (node[i], node[i])] + info
            infos[node.id] = "<br/>".join(info)
        return infos

    def write_html(self, fn):
        html = self.get_html()
        with open(fn, "w") as f:
            f.write(html)
        print("file://" + os.path.abspath(fn), " size:", len(html) // 1024, "kb")

    def get_html(self):
        html = """
        <!doctype html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>gitnodes</title>

          <script type="text/javascript" src="vis.js"></script>
          <link href="vis-network.min.css" rel="stylesheet" type="text/css" />

          <style type="text/css">
            #network {
              width: 100%%;
              height: 640px;
              border: 1px solid lightgray;
            }
          </style>
        </head>
        <body>

        <div id="network"></div>
        <div id="info-box"></div>

        <script type="text/javascript">
            var nodes = new vis.DataSet(%(nodes)s);
            var edges = new vis.DataSet(%(edges)s);
            var info = %(info)s;

            var container = document.getElementById('network');
            var data = { nodes: nodes, edges: edges };
            var options = {
                nodes: {borderWidth: 1},
                "edges": {
                    "smooth": {
                        "type": "continuous",
                        "forceDirection": "vertical",
                        "roundness": 0.65
                    }
                },
                interaction: {hover: true},
                layout: {
                    //improvedLayout: false
                    //, hierarchical: {enabled: true} 
                }
            }

            var network = new vis.Network(container, data, options);
            network.on("click", function(event) {
                for (var i in event.nodes) {
                    var id = event.nodes[i];
                    var elem = document.getElementById("info-box");
                    elem.innerHTML = info[id] ? info[id] : "-";
                    var node = nodes.get(id);
                    node.physics = !node.physics;
                    nodes.update(node);
                    break;
                }
            });
        </script>    
        </body>
        </html>
        """ % {
            "nodes": self.vis_nodes(),
            "edges": self.vis_edges(),
            "info": self.vis_infos(),
        }
        return html
