from core.views import initRequest
from django.shortcuts import render_to_response
from django.utils.cache import patch_response_headers
import urllib.request
from urllib.error import HTTPError, URLError
from core.settings.config import IDDS_HOST
import json
import logging

_logger = logging.getLogger('bigpandamon')

SELECTION_CRITERIA = '/monitor_request_relation'


def query_idds_server(request_id, **kwargs):
    response = []
    idds_server_host = IDDS_HOST
    if 'idds_instance' in kwargs and kwargs['idds_instance'] == 'gcp':
        try:
            from core.settings.config import IDDS_HOST_GCP
            idds_server_host = IDDS_HOST_GCP
        except:
            _logger.exception('Failed to import IDDS_HOST_GCP')
    url = f"{idds_server_host}{SELECTION_CRITERIA}/{request_id}/null"
    try:
        response = urllib.request.urlopen(url).read()
    except (HTTPError, URLError) as e:
        print('Error: {}'.format(e.reason))
    stats = json.loads(response)
    return stats


def fill_nodes_edges(current_node):
    nodes, edges = [], []
    nodes.append(current_node['work']['workload_id'])
    last_edge = {'start': None, 'finish': current_node['work']['workload_id']}
    if 'next_works' in current_node:
        for work in current_node.get('next_works'):
            nodes_sub, edges_sub, last_edge_sub = fill_nodes_edges(work)
            last_edge_sub['start'] = current_node['work']['workload_id']
            nodes.extend(nodes_sub)
            edges.extend(edges_sub)
            edges.append(last_edge_sub)
    return nodes, edges, last_edge


def daggraph(request):
    valid, response = initRequest(request)
    if not valid:
        return response
    requestid = int(request.session['requestParams']['requestid'])
    kwargs = {}
    if request.path and '_gcp' in request.path:
        kwargs['idds_instance'] = 'gcp'
    stats = query_idds_server(requestid, **kwargs)
    nodes_dag_vis = []
    edges_dag_vis = []
    if len(stats) > 0:
        relation_map = stats[0]['relation_map']
        if len(relation_map) > 0:
            relation_map = relation_map[0]
            nodes, edges, last_edge = fill_nodes_edges(relation_map)
            for node in nodes:
                nodes_dag_vis.append(
                    {'group': 'nodes',
                     'data': {'id': str(node),
                              }
                     }
                )

            for edge in edges:
                edges_dag_vis.append({
                  'group': 'edges',
                  'data': {
                    'id': str(edge['start']) + '_to_' + str(edge['finish']),
                    'target': str(edge['finish']),
                    'source': str(edge['start'])
                    }
                })

    DAG = []
    DAG.extend(nodes_dag_vis)
    DAG.extend(edges_dag_vis)
    data = {
        'DAG': DAG
    }
    response = render_to_response('DAGgraph.html', data, content_type='text/html')
    patch_response_headers(response, cache_timeout=request.session['max_age_minutes'] * 60)
    return response