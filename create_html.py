import os

from githubapi import Github, GithubNodes, NodeVis

git = Github(use_cache=True, use_network=True)
nodes = GithubNodes(git)

nodes.add_repo("defgsus/github-nodes", 2)

vis = NodeVis(nodes)
vis.write_html("./index.html")
